import pytest
from app.engine.etl import mask_email, mask_phone, transform_record, validate_schema, run_etl_pipeline

def test_pii_masking():
    # Email masking
    masked_email = mask_email("alexander.hamilton@treasury.gov")
    assert masked_email.startswith("a***n@")
    assert "alexander" not in masked_email

    # Phone masking
    masked_phone = mask_phone("415-555-8921")
    assert masked_phone == "***-***-8921"

def test_transform_record():
    record = {
        "user_email": "jane.doe@acme.com",
        "units": 5,
        "price": 20.0,
        "cost": 30.0
    }
    config = {
        "mask_fields": ["user_email"],
        "derivations": [
            {"target": "revenue", "operation": "multiply", "fields": ["units", "price"]},
            {"target": "profit", "operation": "subtract", "fields": ["revenue", "cost"]}
        ]
    }
    transformed = transform_record(record, config)
    assert transformed["user_email"] != "jane.doe@acme.com"
    assert transformed["revenue"] == 100.0
    assert transformed["profit"] == 70.0

def test_validate_schema():
    records = [
        {"id": "rec-1", "score": 95.0},
        {"id": "rec-2", "score": "not_a_number"}, # Type mismatch
        {"id": None, "score": 80.0} # Missing required
    ]
    schema = {
        "required_fields": ["id", "score"],
        "numeric_fields": ["score"]
    }
    profile = validate_schema(records, schema)
    assert profile["total_records"] == 3
    assert profile["valid_count"] == 1
    assert profile["invalid_count"] == 2
    assert profile["quality_score"] == 33.3

def test_run_etl_pipeline():
    raw_records = [
        {"order_id": "ORD-1", "email": "alice@company.com", "qty": 2, "price": 50.0},
        {"order_id": "ORD-1", "email": "alice@company.com", "qty": 2, "price": 50.0}, # Duplicate
        {"order_id": None, "email": "drop@null.com", "qty": 1, "price": 10.0}, # Null order_id
        {"order_id": "ORD-2", "email": "bob@enterprise.org", "qty": 4, "price": 100.0}
    ]
    pipeline_cfg = {
        "drop_null_fields": ["order_id"],
        "dedup_key": "order_id",
        "mask_fields": ["email"],
        "derivations": [
            {"target": "total", "operation": "multiply", "fields": ["qty", "price"]}
        ],
        "schema_rules": {
            "required_fields": ["order_id", "email", "total"],
            "numeric_fields": ["qty", "price", "total"]
        }
    }
    result = run_etl_pipeline(raw_records, pipeline_cfg)
    assert result["input_count"] == 4
    assert result["output_count"] == 2 # 1 null dropped, 1 duplicate dropped
    assert result["duplicates_dropped"] == 1
    assert result["quality_profile"]["quality_score"] == 100.0
    assert result["records"][0]["total"] == 100.0
    assert result["records"][1]["total"] == 400.0
