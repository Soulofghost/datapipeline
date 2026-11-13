import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from typing import List
from app.database import get_db_connection
from app.schemas import PipelineCreate, PipelineResponse, PipelineRunRequest, PipelineRunResponse
from app.engine.etl import run_etl_pipeline

router = APIRouter(prefix="/pipelines", tags=["Pipelines"])

SAMPLE_ORDERS_BATCH = [
    {"order_id": "ORD-501", "customer_email": "sarah.connor@cyberdyne.com", "customer_phone": "415-555-0199", "quantity": 4, "unit_price": 250.0, "cost": 600.0},
    {"order_id": "ORD-502", "customer_email": "bruce.wayne@waynecorp.com", "customer_phone": "212-555-0144", "quantity": 10, "unit_price": 49.0, "cost": 200.0},
    {"order_id": "ORD-503", "customer_email": "tony.stark@starkindustries.com", "customer_phone": "212-555-0188", "quantity": 2, "unit_price": 1200.0, "cost": 1500.0},
    {"order_id": "ORD-501", "customer_email": "sarah.connor@cyberdyne.com", "customer_phone": "415-555-0199", "quantity": 4, "unit_price": 250.0, "cost": 600.0}, # Duplicate
    {"order_id": None, "customer_email": "invalid@null.com", "customer_phone": "555-000-0000", "quantity": 1, "unit_price": 10.0, "cost": 5.0}, # Null order_id to drop
    {"order_id": "ORD-504", "customer_email": "peter.parker@dailybugle.com", "customer_phone": "718-555-0122", "quantity": 5, "unit_price": 80.0, "cost": 200.0}
]

SAMPLE_IOT_BATCH = [
    {"telemetry_id": "TEL-101", "sensor_id": "SN-TEMP-01", "reading_val": 42.5, "calibration_factor": 1.05},
    {"telemetry_id": "TEL-102", "sensor_id": "SN-VIB-02", "reading_val": 0.88, "calibration_factor": 0.98},
    {"telemetry_id": "TEL-103", "sensor_id": "SN-FLOW-03", "reading_val": 120.4, "calibration_factor": 1.00},
    {"telemetry_id": "TEL-101", "sensor_id": "SN-TEMP-01", "reading_val": 42.5, "calibration_factor": 1.05}, # Duplicate
    {"telemetry_id": "TEL-104", "sensor_id": None, "reading_val": 15.0, "calibration_factor": 1.00} # Null sensor_id to drop
]

@router.get("", response_model=List[PipelineResponse])
def get_pipelines():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pipelines ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [
            PipelineResponse(
                id=r["id"],
                name=r["name"],
                description=r["description"],
                source_type=r["source_type"],
                target_table=r["target_table"],
                config=json.loads(r["config_json"]),
                created_at=r["created_at"]
            )
            for r in rows
        ]

@router.post("", response_model=PipelineResponse, status_code=201)
def create_pipeline(req: PipelineCreate):
    pipe_id = "pipe-" + str(uuid.uuid4())[:8]
    config_str = json.dumps(req.config)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pipelines (id, name, description, source_type, target_table, config_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (pipe_id, req.name.strip(), req.description.strip(), req.source_type.upper(), req.target_table.strip(), config_str))
        conn.commit()

        cursor.execute("SELECT * FROM pipelines WHERE id = ?", (pipe_id,))
        r = cursor.fetchone()
        return PipelineResponse(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            source_type=r["source_type"],
            target_table=r["target_table"],
            config=json.loads(r["config_json"]),
            created_at=r["created_at"]
        )

@router.post("/{pipeline_id}/run", response_model=PipelineRunResponse)
def execute_pipeline(pipeline_id: str, req: PipelineRunRequest):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_id,))
        pipe_row = cursor.fetchone()
        if not pipe_row:
            raise HTTPException(status_code=404, detail="Pipeline not found.")

        config = json.loads(pipe_row["config_json"])

        # Determine input records
        if req.records and len(req.records) > 0:
            records = req.records
        else:
            records = SAMPLE_IOT_BATCH if "iot" in pipeline_id.lower() else SAMPLE_ORDERS_BATCH

        # Execute ETL stages
        etl_result = run_etl_pipeline(records, config)
        run_id = "run-" + str(uuid.uuid4())[:8]
        now_iso = datetime.now(timezone.utc).isoformat()

        # Save run record
        cursor.execute("""
            INSERT INTO pipeline_runs (
                id, pipeline_id, status, input_count, output_count,
                filtered_count, execution_time_ms, quality_score, summary_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id, pipeline_id, "COMPLETED", etl_result["input_count"], etl_result["output_count"],
            etl_result["filtered_count"], etl_result["execution_time_ms"],
            etl_result["quality_profile"]["quality_score"], json.dumps(etl_result["quality_profile"]),
            now_iso
        ))

        # Save transformed records to warehouse
        for r in etl_result["records"]:
            rec_id = "wh-" + str(uuid.uuid4())[:8]
            cursor.execute("""
                INSERT INTO warehouse_records (id, pipeline_id, run_id, data_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (rec_id, pipeline_id, run_id, json.dumps(r), now_iso))

        conn.commit()

        return PipelineRunResponse(
            id=run_id,
            pipeline_id=pipeline_id,
            status="COMPLETED",
            input_count=etl_result["input_count"],
            output_count=etl_result["output_count"],
            filtered_count=etl_result["filtered_count"],
            duplicates_dropped=etl_result["duplicates_dropped"],
            execution_time_ms=etl_result["execution_time_ms"],
            throughput_rows_per_sec=etl_result["throughput_rows_per_sec"],
            quality_score=etl_result["quality_profile"]["quality_score"],
            quality_profile=etl_result["quality_profile"],
            sample_records=etl_result["records"][:10],
            created_at=now_iso
        )

@router.get("/{pipeline_id}/runs", response_model=List[dict])
def get_pipeline_runs(pipeline_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, pipeline_id, status, input_count, output_count, filtered_count,
                   execution_time_ms, quality_score, created_at
            FROM pipeline_runs
            WHERE pipeline_id = ?
            ORDER BY created_at DESC
        """, (pipeline_id,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
