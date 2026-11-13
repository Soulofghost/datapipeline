import re
import time
from typing import List, Dict, Any, Tuple

def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return email
    user, domain = email.split("@", 1)
    if len(user) <= 2:
        masked_user = user[0] + "***"
    else:
        masked_user = user[0] + "***" + user[-1]
    return f"{masked_user}@{domain}"

def mask_phone(phone: str) -> str:
    if not phone:
        return phone
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 4:
        return f"***-***-{digits[-4:]}"
    return "***-***-****"

def transform_record(record: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(record)

    # 1. PII Anonymization
    mask_fields = config.get("mask_fields", [])
    for field in mask_fields:
        if field in row and isinstance(row[field], str):
            val = row[field]
            if "@" in val:
                row[field] = mask_email(val)
            elif any(c.isdigit() for c in val):
                row[field] = mask_phone(val)

    # 2. Field Derivations
    derivations = config.get("derivations", [])
    for d in derivations:
        target = d.get("target")
        op = d.get("operation")
        if op == "multiply" and target:
            f1, f2 = d.get("fields", [None, None])
            if f1 in row and f2 in row and row[f1] is not None and row[f2] is not None:
                try:
                    row[target] = round(float(row[f1]) * float(row[f2]), 2)
                except (ValueError, TypeError):
                    row[target] = 0.0
        elif op == "subtract" and target:
            f1, f2 = d.get("fields", [None, None])
            if f1 in row and f2 in row and row[f1] is not None and row[f2] is not None:
                try:
                    row[target] = round(float(row[f1]) - float(row[f2]), 2)
                except (ValueError, TypeError):
                    row[target] = 0.0

    return row

def validate_schema(records: List[Dict[str, Any]], schema_rules: Dict[str, Any]) -> Dict[str, Any]:
    required_fields = schema_rules.get("required_fields", [])
    numeric_fields = schema_rules.get("numeric_fields", [])

    total = len(records)
    valid_count = 0
    issues = []

    for idx, r in enumerate(records):
        row_valid = True
        # Check required fields
        for rf in required_fields:
            if rf not in r or r[rf] is None or r[rf] == "":
                row_valid = False
                issues.append(f"Row {idx}: missing required field '{rf}'")

        # Check numeric fields
        for nf in numeric_fields:
            if nf in r and r[nf] is not None:
                try:
                    float(r[nf])
                except (ValueError, TypeError):
                    row_valid = False
                    issues.append(f"Row {idx}: field '{nf}' cannot be cast to numeric")

        if row_valid:
            valid_count += 1

    quality_score = round((valid_count / total * 100.0), 1) if total > 0 else 100.0

    return {
        "total_records": total,
        "valid_count": valid_count,
        "invalid_count": total - valid_count,
        "quality_score": quality_score,
        "sample_issues": issues[:5]
    }

def run_etl_pipeline(records: List[Dict[str, Any]], pipeline_config: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.perf_counter()
    input_count = len(records)

    # Stage 1: Extraction & Null Filtering
    drop_null_fields = pipeline_config.get("drop_null_fields", [])
    stage1 = []
    for r in records:
        drop = False
        for dnf in drop_null_fields:
            if dnf not in r or r[dnf] is None or str(r[dnf]).strip() == "":
                drop = True
                break
        if not drop:
            stage1.append(r)

    # Stage 2: Deduplication
    dedup_key = pipeline_config.get("dedup_key")
    stage2 = []
    seen = set()
    duplicates_dropped = 0

    if dedup_key:
        for r in stage1:
            val = r.get(dedup_key)
            if val is not None and val in seen:
                duplicates_dropped += 1
            else:
                if val is not None:
                    seen.add(val)
                stage2.append(r)
    else:
        stage2 = stage1

    # Stage 3: Transformation (PII Masking & Field Derivation)
    transformed_records = []
    for r in stage2:
        transformed = transform_record(r, pipeline_config)
        transformed_records.append(transformed)

    # Stage 4: Schema Quality Validation
    schema_rules = pipeline_config.get("schema_rules", {})
    quality_profile = validate_schema(transformed_records, schema_rules)

    duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    throughput_rows_sec = round((input_count / (duration_ms / 1000.0)), 1) if duration_ms > 0 else input_count

    return {
        "input_count": input_count,
        "output_count": len(transformed_records),
        "filtered_count": input_count - len(transformed_records),
        "duplicates_dropped": duplicates_dropped,
        "execution_time_ms": duration_ms,
        "throughput_rows_per_sec": throughput_rows_sec,
        "quality_profile": quality_profile,
        "records": transformed_records
    }
