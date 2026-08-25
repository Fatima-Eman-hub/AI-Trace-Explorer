"""
Pydantic Schemas - define the exact shape of API requests and responses.

FastAPI uses these to:
1. Validate incoming request bodies (reject bad data automatically)
2. Generate the /docs Swagger UI documentation
3. Serialize outgoing responses consistently
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ==================== REQUEST SCHEMAS (what the client sends) ====================

class FewShotExample(BaseModel):
    input: str
    output: str


class ModelParameters(BaseModel):
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=1024, ge=1, le=8192)


class LLMRequestCreate(BaseModel):
    """Body for POST /api/v1/llm/request"""
    user_prompt: str = Field(..., min_length=1, max_length=10000)
    model_name: str = Field(..., examples=["claude-sonnet", "llama-3.3-70b"])
    system_prompt: Optional[str] = None
    few_shot_examples: Optional[List[FewShotExample]] = None
    model_parameters: Optional[ModelParameters] = None
    tags: Optional[List[str]] = None


# ==================== RESPONSE SCHEMAS (what the API sends back) ====================

class StageSummary(BaseModel):
    """One stage's result, included in the pipeline response."""
    stage_name: str
    status: str
    duration_ms: int
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class Metrics(BaseModel):
    input_tokens: int
    output_tokens: int
    cost_usd: float


class EvaluationSummary(BaseModel):
    """Quality scores produced by the evaluator stage."""
    hallucination_score: float
    faithfulness_score: float
    answer_relevancy: float
    overall_quality_score: float
    quality_level: str
    needs_review: bool


class LLMRequestResponse(BaseModel):
    """Response for POST /api/v1/llm/request"""
    trace_id: str
    status: str
    response: Optional[str] = None
    total_latency_ms: Optional[int] = None
    stages: List[StageSummary] = []
    metrics: Optional[Metrics] = None
    evaluation: Optional[EvaluationSummary] = None
    failed_stage: Optional[str] = None
    error: Optional[str] = None


class TraceListItem(BaseModel):
    """One row in the GET /api/v1/traces list."""
    id: str
    timestamp: Optional[datetime] = None
    model_name: str
    status: str
    user_prompt: str
    total_latency_ms: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None

    class Config:
        from_attributes = True


class PaginationInfo(BaseModel):
    page: int
    limit: int
    total: int
    pages: int


class TraceListResponse(BaseModel):
    """Response for GET /api/v1/traces"""
    traces: List[TraceListItem]
    pagination: PaginationInfo


class TraceStageDetail(BaseModel):
    """One stage row, as stored in the database, for the detail view."""
    stage_name: str
    stage_order: Optional[int] = None
    status: str
    duration_ms: Optional[int] = None
    stage_input: Optional[Dict[str, Any]] = None
    stage_output: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class TraceDetailResponse(BaseModel):
    """Response for GET /api/v1/traces/{trace_id}"""
    id: str
    timestamp: Optional[datetime] = None
    model_name: str
    status: str
    user_prompt: str
    system_prompt: Optional[str] = None
    full_response: Optional[str] = None
    total_latency_ms: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    error_message: Optional[str] = None
    stages: List[TraceStageDetail] = []
    evaluation: Optional[EvaluationSummary] = None

    class Config:
        from_attributes = True


class SupportedModelResponse(BaseModel):
    name: str
    provider: str
    max_context_tokens: Optional[int] = None
    input_price_per_1k: Optional[float] = None
    output_price_per_1k: Optional[float] = None
    is_active: bool
    description: Optional[str] = None

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """Standard error shape returned on 4xx/5xx responses."""
    error: bool = True
    code: str
    message: str
