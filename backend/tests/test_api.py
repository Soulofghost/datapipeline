import os
import pytest
from fastapi.testclient import TestClient

os.environ["DATAPIPELINE_DB"] = "test_datapipeline_api.db"

from app.database import init_db
from app.main import app

@pytest.fixture(scope="module", autouse=True)
def setup_api_db():
    if os.path.exists("test_datapipeline_api.db"):
        os.remove("test_datapipeline_api.db")
    init_db()
    yield
    if os.path.exists("test_datapipeline_api.db"):
        try:
            os.remove("test_datapipeline_api.db")
        except Exception:
            pass

client = TestClient(app)

def test_health_check():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "Extract" in data["stages"]

def test_list_and_create_pipelines():
    res = client.get("/api/v1/pipelines")
    assert res.status_code == 200
    pipes = res.json()
    assert len(pipes) >= 2

    # Create new pipeline
    payload = {
        "name": "ad-clicks-stream",
        "description": "Transforms ad click telemetry",
        "source_type": "JSON_STREAM",
        "target_table": "wh_ad_clicks",
        "config": {
            "drop_null_fields": ["click_id"],
            "dedup_key": "click_id",
            "mask_fields": ["ip_addr"],
            "derivations": [],
            "schema_rules": {"required_fields": ["click_id"]}
        }
    }
    create_res = client.post("/api/v1/pipelines", json=payload)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["name"] == "ad-clicks-stream"

def test_run_pipeline_and_warehouse_records():
    # Trigger run on pipe-orders
    run_res = client.post("/api/v1/pipelines/pipe-orders/run", json={})
    assert run_res.status_code == 200
    data = run_res.json()
    assert data["status"] == "COMPLETED"
    assert data["output_count"] >= 3
    assert data["quality_score"] > 80.0
    run_id = data["id"]

    # Verify warehouse records
    wh_res = client.get(f"/api/v1/warehouse/records?run_id={run_id}")
    assert wh_res.status_code == 200
    records = wh_res.json()
    assert len(records) == data["output_count"]

    # Verify pipeline runs history
    runs_res = client.get("/api/v1/pipelines/pipe-orders/runs")
    assert runs_res.status_code == 200
    assert len(runs_res.json()) >= 1

def test_warehouse_summary():
    res = client.get("/api/v1/warehouse/summary")
    assert res.status_code == 200
    summary = res.json()
    assert summary["total_pipelines"] >= 2
    assert summary["lifetime_runs"] >= 1
    assert summary["total_rows_processed"] >= 3
