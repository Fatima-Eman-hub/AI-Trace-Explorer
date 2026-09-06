"""
Analytics Schemas - shapes for the /analytics endpoints.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel


class LatencyBucket(BaseModel):
    bucket: str
    avg_latency_ms: float
    min_latency_ms: int
    max_latency_ms: int
    request_count: int


class LatencySummary(BaseModel):
    avg_latency_ms: float
    total_requests: int
    slowest_stage: Optional[str] = None
    slowest_stage_avg_ms: Optional[float] = None


class LatencyAnalyticsResponse(BaseModel):
    period: str
    data: List[LatencyBucket]
    summary: LatencySummary


class ModelCostBreakdown(BaseModel):
    requests: int
    cost_usd: float


class CostBucket(BaseModel):
    bucket: str
    cost_usd: float
    requests: int
    avg_cost_per_request: float


class CostAnalyticsResponse(BaseModel):
    period: str
    total_cost_usd: float
    by_model: Dict[str, ModelCostBreakdown]
    by_hour: List[CostBucket]


class ThroughputInfo(BaseModel):
    requests_per_hour: float
    peak_hour_count: int
    low_hour_count: int


class ErrorBreakdown(BaseModel):
    total_errors: int
    by_stage: Dict[str, int]
    by_category: Dict[str, int] = {}


class QualityMetrics(BaseModel):
    avg_hallucination: Optional[float] = None
    avg_faithfulness: Optional[float] = None
    avg_relevancy: Optional[float] = None
    excellent_count: int = 0
    good_count: int = 0
    fair_count: int = 0
    poor_count: int = 0
    needs_review_count: int = 0


class PerformanceAnalyticsResponse(BaseModel):
    period: str
    total_requests: int
    success_rate: float
    error_rate: float
    throughput: ThroughputInfo
    errors: ErrorBreakdown
    quality: QualityMetrics
