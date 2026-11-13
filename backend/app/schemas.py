from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class PipelineCreate(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "customer-leads-etl"})
    description: str = Field(..., json_schema_extra={"example": "Enriches lead pipelines"})
    source_type: str = Field("JSON_STREAM", json_schema_extra={"example": "JSON_STREAM"})
    target_table: str = Field("wh_leads", json_schema_extra={"example": "wh_leads"})
    config: Dict[str, Any]

class PipelineResponse(BaseModel):
    id: str
    name: str
    description: str
    source_type: str
    target_table: str
    config: Dict[str, Any]
    created_at: str

class PipelineRunRequest(BaseModel):
    records: Optional[List[Dict[str, Any]]] = None

class QualityProfile(BaseModel):
    total_records: int
    valid_count: int
    invalid_count: int
    quality_score: float
    sample_issues: List[str]

class PipelineRunResponse(BaseModel):
    id: str
    pipeline_id: str
    status: str
    input_count: int
    output_count: int
    filtered_count: int
    duplicates_dropped: int
    execution_time_ms: float
    throughput_rows_per_sec: float
    quality_score: float
    quality_profile: QualityProfile
    sample_records: List[Dict[str, Any]]
    created_at: str

class ETLSystemSummary(BaseModel):
    total_pipelines: int
    lifetime_runs: int
    total_rows_processed: int
    average_quality_score: float
    average_execution_time_ms: float
