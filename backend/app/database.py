import sqlite3
import os
import json
from contextlib import contextmanager
from app.config import settings

def get_db_path() -> str:
    return os.environ.get("DATAPIPELINE_DB", settings.DATAPIPELINE_DB)

@contextmanager
def get_db_connection():
    db_path = get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True) if os.path.dirname(db_path) else None
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipelines (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                source_type TEXT NOT NULL,
                target_table TEXT NOT NULL,
                config_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id TEXT PRIMARY KEY,
                pipeline_id TEXT NOT NULL,
                status TEXT NOT NULL,
                input_count INTEGER NOT NULL,
                output_count INTEGER NOT NULL,
                filtered_count INTEGER NOT NULL,
                execution_time_ms REAL NOT NULL,
                quality_score REAL NOT NULL,
                summary_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS warehouse_records (
                id TEXT PRIMARY KEY,
                pipeline_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                data_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_pipe ON pipeline_runs(pipeline_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wh_run ON warehouse_records(run_id);")

        cursor.execute("SELECT count(*) FROM pipelines")
        if cursor.fetchone()[0] == 0:
            pipe1_cfg = {
                "drop_null_fields": ["order_id", "unit_price"],
                "dedup_key": "order_id",
                "mask_fields": ["customer_email", "customer_phone"],
                "derivations": [
                    {"target": "total_revenue", "operation": "multiply", "fields": ["quantity", "unit_price"]},
                    {"target": "gross_margin", "operation": "subtract", "fields": ["total_revenue", "cost"]}
                ],
                "schema_rules": {
                    "required_fields": ["order_id", "customer_email", "total_revenue"],
                    "numeric_fields": ["quantity", "unit_price", "total_revenue"]
                }
            }

            pipe2_cfg = {
                "drop_null_fields": ["sensor_id", "reading_val"],
                "dedup_key": "telemetry_id",
                "mask_fields": [],
                "derivations": [
                    {"target": "reading_normalized", "operation": "multiply", "fields": ["reading_val", "calibration_factor"]}
                ],
                "schema_rules": {
                    "required_fields": ["sensor_id", "reading_val"],
                    "numeric_fields": ["reading_val"]
                }
            }

            cursor.execute("""
                INSERT INTO pipelines (id, name, description, source_type, target_table, config_json)
                VALUES 
                ('pipe-orders', 'E-Commerce Orders ETL', 'Cleanses retail orders, anonymizes customer PII, derives revenue metrics and deduplicates order IDs', 'JSON_STREAM', 'wh_fact_orders', ?),
                ('pipe-iot', 'Industrial IoT Sensor Normalization', 'Processes vibration and temperature telematics, filters null events and normalizes calibration', 'CSV_BATCH', 'wh_fact_iot_telemetry', ?)
            """, (json.dumps(pipe1_cfg), json.dumps(pipe2_cfg)))
            conn.commit()
