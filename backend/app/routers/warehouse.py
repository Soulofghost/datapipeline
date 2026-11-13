import json
from fastapi import APIRouter, Query
from typing import List, Optional
from app.database import get_db_connection
from app.schemas import ETLSystemSummary

router = APIRouter(prefix="/warehouse", tags=["Warehouse & Telemetry"])

@router.get("/records")
def get_warehouse_records(
    pipeline_id: Optional[str] = None,
    run_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200)
):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT id, pipeline_id, run_id, data_json, created_at FROM warehouse_records WHERE 1=1"
        params = []
        if pipeline_id:
            query += " AND pipeline_id = ?"
            params.append(pipeline_id)
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        return [
            {
                "id": r["id"],
                "pipeline_id": r["pipeline_id"],
                "run_id": r["run_id"],
                "data": json.loads(r["data_json"]),
                "created_at": r["created_at"]
            }
            for r in rows
        ]

@router.get("/summary", response_model=ETLSystemSummary)
def get_system_summary():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        total_pipes = cursor.execute("SELECT count(*) FROM pipelines").fetchone()[0]
        total_runs = cursor.execute("SELECT count(*) FROM pipeline_runs").fetchone()[0]
        total_rows_row = cursor.execute("SELECT SUM(output_count) FROM pipeline_runs").fetchone()[0]
        total_rows = int(total_rows_row) if total_rows_row is not None else 0

        avg_qual_row = cursor.execute("SELECT AVG(quality_score) FROM pipeline_runs").fetchone()[0]
        avg_quality = round(float(avg_qual_row), 1) if avg_qual_row is not None else 100.0

        avg_exec_row = cursor.execute("SELECT AVG(execution_time_ms) FROM pipeline_runs").fetchone()[0]
        avg_exec = round(float(avg_exec_row), 2) if avg_exec_row is not None else 0.0

        return ETLSystemSummary(
            total_pipelines=total_pipes,
            lifetime_runs=total_runs,
            total_rows_processed=total_rows,
            average_quality_score=avg_quality,
            average_execution_time_ms=avg_exec
        )
