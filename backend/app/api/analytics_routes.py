"""
Analytics Routes - aggregate reporting over past requests.

GET /api/v1/analytics/latency      -> latency trends over time
GET /api/v1/analytics/cost         -> cost breakdown by model + over time
GET /api/v1/analytics/performance  -> throughput, error rate, quality trends

All three accept ?period= one of: 1h, 24h, 7d, 30d (default 24h).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timedelta
from typing import Dict

from app.database import get_db
from app.models import Request, Trace, Evaluation
from app.api.analytics_schemas import (
    LatencyAnalyticsResponse, LatencyBucket, LatencySummary,
    CostAnalyticsResponse, ModelCostBreakdown, CostBucket,
    PerformanceAnalyticsResponse, ThroughputInfo, ErrorBreakdown, QualityMetrics,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])

PERIOD_TO_DELTA = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _period_start(period: str) -> datetime:
    delta = PERIOD_TO_DELTA.get(period, PERIOD_TO_DELTA["24h"])
    return datetime.utcnow() - delta


def _hour_bucket_expr():
    """SQLite-compatible expression that truncates a timestamp to the hour."""
    return func.strftime("%Y-%m-%d %H:00:00", Request.timestamp)


# ==================== LATENCY ====================

@router.get("/latency", response_model=LatencyAnalyticsResponse)
def get_latency_analytics(
    period: str = Query(default="24h", pattern="^(1h|24h|7d|30d)$"),
    model: str = Query(default=None),
    db: Session = Depends(get_db),
):
    start = _period_start(period)
    bucket_expr = _hour_bucket_expr()

    query = db.query(
        bucket_expr.label("bucket"),
        func.avg(Request.total_latency_ms).label("avg_latency"),
        func.min(Request.total_latency_ms).label("min_latency"),
        func.max(Request.total_latency_ms).label("max_latency"),
        func.count(Request.id).label("request_count"),
    ).filter(
        Request.timestamp >= start,
        Request.total_latency_ms.isnot(None),
    )
    if model:
        query = query.filter(Request.model_name == model)

    rows = query.group_by(bucket_expr).order_by(bucket_expr).all()

    data = [
        LatencyBucket(
            bucket=r.bucket,
            avg_latency_ms=round(r.avg_latency or 0, 2),
            min_latency_ms=r.min_latency or 0,
            max_latency_ms=r.max_latency or 0,
            request_count=r.request_count,
        )
        for r in rows
    ]

    total_requests = sum(d.request_count for d in data)
    avg_latency = (
        round(sum(d.avg_latency_ms * d.request_count for d in data) / total_requests, 2)
        if total_requests > 0 else 0.0
    )

    # Which stage is typically the slowest? (across all traces in this period)
    stage_avg = (
        db.query(
            Trace.stage_name,
            func.avg(Trace.duration_ms).label("avg_duration"),
        )
        .join(Request, Trace.request_id == Request.id)
        .filter(Request.timestamp >= start, Trace.duration_ms.isnot(None))
        .group_by(Trace.stage_name)
        .order_by(func.avg(Trace.duration_ms).desc())
        .first()
    )

    summary = LatencySummary(
        avg_latency_ms=avg_latency,
        total_requests=total_requests,
        slowest_stage=stage_avg.stage_name if stage_avg else None,
        slowest_stage_avg_ms=round(stage_avg.avg_duration, 2) if stage_avg else None,
    )

    return LatencyAnalyticsResponse(period=period, data=data, summary=summary)


# ==================== COST ====================

@router.get("/cost", response_model=CostAnalyticsResponse)
def get_cost_analytics(
    period: str = Query(default="24h", pattern="^(1h|24h|7d|30d)$"),
    db: Session = Depends(get_db),
):
    start = _period_start(period)

    base_query = db.query(Request).filter(
        Request.timestamp >= start,
        Request.cost_usd.isnot(None),
    )

    total_cost = base_query.with_entities(func.sum(Request.cost_usd)).scalar() or 0.0

    # By model
    by_model_rows = (
        db.query(
            Request.model_name,
            func.count(Request.id).label("requests"),
            func.sum(Request.cost_usd).label("cost"),
        )
        .filter(Request.timestamp >= start, Request.cost_usd.isnot(None))
        .group_by(Request.model_name)
        .all()
    )
    by_model: Dict[str, ModelCostBreakdown] = {
        r.model_name: ModelCostBreakdown(requests=r.requests, cost_usd=round(r.cost or 0, 6))
        for r in by_model_rows
    }

    # By hour
    bucket_expr = _hour_bucket_expr()
    hourly_rows = (
        db.query(
            bucket_expr.label("bucket"),
            func.sum(Request.cost_usd).label("cost"),
            func.count(Request.id).label("requests"),
        )
        .filter(Request.timestamp >= start, Request.cost_usd.isnot(None))
        .group_by(bucket_expr)
        .order_by(bucket_expr)
        .all()
    )
    by_hour = [
        CostBucket(
            bucket=r.bucket,
            cost_usd=round(r.cost or 0, 6),
            requests=r.requests,
            avg_cost_per_request=round((r.cost or 0) / r.requests, 6) if r.requests else 0.0,
        )
        for r in hourly_rows
    ]

    return CostAnalyticsResponse(
        period=period,
        total_cost_usd=round(total_cost, 6),
        by_model=by_model,
        by_hour=by_hour,
    )


# ==================== PERFORMANCE ====================

@router.get("/performance", response_model=PerformanceAnalyticsResponse)
def get_performance_analytics(
    period: str = Query(default="24h", pattern="^(1h|24h|7d|30d)$"),
    db: Session = Depends(get_db),
):
    start = _period_start(period)
    delta = PERIOD_TO_DELTA.get(period, PERIOD_TO_DELTA["24h"])
    hours_in_period = max(delta.total_seconds() / 3600, 1)

    total_requests = db.query(func.count(Request.id)).filter(Request.timestamp >= start).scalar() or 0
    success_count = db.query(func.count(Request.id)).filter(
        Request.timestamp >= start, Request.status == "success"
    ).scalar() or 0
    error_count = db.query(func.count(Request.id)).filter(
        Request.timestamp >= start, Request.status == "error"
    ).scalar() or 0

    success_rate = round((success_count / total_requests) * 100, 2) if total_requests else 0.0
    error_rate = round((error_count / total_requests) * 100, 2) if total_requests else 0.0

    # Throughput: requests per hour bucket, to find peak/low
    bucket_expr = _hour_bucket_expr()
    hourly_counts = (
        db.query(bucket_expr.label("bucket"), func.count(Request.id).label("cnt"))
        .filter(Request.timestamp >= start)
        .group_by(bucket_expr)
        .all()
    )
    counts = [r.cnt for r in hourly_counts] or [0]
    throughput = ThroughputInfo(
        requests_per_hour=round(total_requests / hours_in_period, 2),
        peak_hour_count=max(counts),
        low_hour_count=min(counts),
    )

    # Errors by which stage failed (parsed from error_message prefix "Failed at stage 'X'")
    error_rows = (
        db.query(Request.error_message)
        .filter(Request.timestamp >= start, Request.status == "error", Request.error_message.isnot(None))
        .all()
    )
    by_stage: Dict[str, int] = {}
    for (msg,) in error_rows:
        stage = "unknown"
        if msg and "Failed at stage '" in msg:
            stage = msg.split("Failed at stage '")[1].split("'")[0]
        by_stage[stage] = by_stage.get(stage, 0) + 1

    errors = ErrorBreakdown(total_errors=error_count, by_stage=by_stage)

    # Quality metrics from Evaluation table
    eval_agg = (
        db.query(
            func.avg(Evaluation.hallucination_score),
            func.avg(Evaluation.faithfulness_score),
            func.avg(Evaluation.answer_relevancy),
        )
        .join(Request, Evaluation.request_id == Request.id)
        .filter(Request.timestamp >= start)
        .first()
    )
    avg_hall, avg_faith, avg_rel = eval_agg if eval_agg else (None, None, None)

    quality_counts = (
        db.query(Evaluation.quality_level, func.count(Evaluation.id))
        .join(Request, Evaluation.request_id == Request.id)
        .filter(Request.timestamp >= start)
        .group_by(Evaluation.quality_level)
        .all()
    )
    level_counts = {level: count for level, count in quality_counts}

    needs_review_count = (
        db.query(func.count(Evaluation.id))
        .join(Request, Evaluation.request_id == Request.id)
        .filter(Request.timestamp >= start, Evaluation.needs_review == True)
        .scalar() or 0
    )

    quality = QualityMetrics(
        avg_hallucination=round(avg_hall, 4) if avg_hall is not None else None,
        avg_faithfulness=round(avg_faith, 4) if avg_faith is not None else None,
        avg_relevancy=round(avg_rel, 4) if avg_rel is not None else None,
        excellent_count=level_counts.get("excellent", 0),
        good_count=level_counts.get("good", 0),
        fair_count=level_counts.get("fair", 0),
        poor_count=level_counts.get("poor", 0),
        needs_review_count=needs_review_count,
    )

    return PerformanceAnalyticsResponse(
        period=period,
        total_requests=total_requests,
        success_rate=success_rate,
        error_rate=error_rate,
        throughput=throughput,
        errors=errors,
        quality=quality,
    )
