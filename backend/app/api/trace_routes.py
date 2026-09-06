"""
Trace Routes - browse, inspect, search, and export past requests.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_
from typing import Optional
import math
import json
import csv
import io

from app.database import get_db
from app.models import Request, Trace, Evaluation
from app.failure_classifier import SUGGESTED_FIXES
from app.api.schemas import (
    TraceListResponse, TraceListItem, PaginationInfo,
    TraceDetailResponse, TraceStageDetail, EvaluationSummary,
)

router = APIRouter(prefix="/traces", tags=["Traces"])


@router.get("", response_model=TraceListResponse)
def list_traces(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    model: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    failure_category: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None, description="Search prompt text or model name"),
    db: Session = Depends(get_db),
):
    query = db.query(Request)

    if model:
        query = query.filter(Request.model_name == model)
    if status:
        query = query.filter(Request.status == status)
    if failure_category:
        query = query.filter(Request.failure_category == failure_category)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Request.user_prompt.ilike(like), Request.model_name.ilike(like)))

    total = query.count()
    total_pages = math.ceil(total / limit) if total > 0 else 1
    offset = (page - 1) * limit
    rows = query.order_by(desc(Request.timestamp)).offset(offset).limit(limit).all()

    items = [
        TraceListItem(
            id=r.id, timestamp=r.timestamp, model_name=r.model_name, status=r.status,
            user_prompt=r.user_prompt, total_latency_ms=r.total_latency_ms,
            input_tokens=r.input_tokens, output_tokens=r.output_tokens, cost_usd=r.cost_usd,
            failure_category=r.failure_category,
        )
        for r in rows
    ]

    return TraceListResponse(
        traces=items,
        pagination=PaginationInfo(page=page, limit=limit, total=total, pages=total_pages),
    )


@router.get("/failure-categories")
def list_failure_categories():
    """Reference list of all failure categories the classifier knows about, with their hints."""
    return [{"category": k, "suggested_fix": v} for k, v in SUGGESTED_FIXES.items()]


@router.get("/export")
def export_traces(
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    model: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Request)
    if model:
        query = query.filter(Request.model_name == model)
    if status:
        query = query.filter(Request.status == status)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Request.user_prompt.ilike(like), Request.model_name.ilike(like)))

    rows = query.order_by(desc(Request.timestamp)).all()

    if format == "json":
        data = [r.to_full_dict() for r in rows]
        content = json.dumps(data, indent=2, default=str)
        return StreamingResponse(
            io.BytesIO(content.encode()), media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=traces_export.json"},
        )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "timestamp", "model_name", "status", "failure_category", "user_prompt",
                      "total_latency_ms", "input_tokens", "output_tokens", "cost_usd"])
    for r in rows:
        writer.writerow([
            r.id, r.timestamp, r.model_name, r.status, r.failure_category or "",
            (r.user_prompt or "").replace("\n", " "),
            r.total_latency_ms, r.input_tokens, r.output_tokens, r.cost_usd,
        ])
    buffer.seek(0)
    return StreamingResponse(
        io.BytesIO(buffer.getvalue().encode()), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=traces_export.csv"},
    )


@router.get("/{trace_id}", response_model=TraceDetailResponse)
def get_trace(trace_id: str, db: Session = Depends(get_db)):
    request_row = db.query(Request).filter(Request.id == trace_id).first()
    if not request_row:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")

    stages = db.query(Trace).filter(Trace.request_id == trace_id).order_by(asc(Trace.stage_order)).all()
    stage_details = [
        TraceStageDetail(
            stage_name=s.stage_name, stage_order=s.stage_order, status=s.status,
            duration_ms=s.duration_ms, stage_input=s.stage_input, stage_output=s.stage_output,
            error_message=s.error_message,
        )
        for s in stages
    ]

    evaluation_row = db.query(Evaluation).filter(Evaluation.request_id == trace_id).first()
    evaluation_summary = None
    if evaluation_row:
        evaluation_summary = EvaluationSummary(
            hallucination_score=evaluation_row.hallucination_score,
            faithfulness_score=evaluation_row.faithfulness_score,
            answer_relevancy=evaluation_row.answer_relevancy,
            overall_quality_score=evaluation_row.overall_quality_score,
            quality_level=evaluation_row.quality_level,
            needs_review=evaluation_row.needs_review,
        )

    suggested_fix = SUGGESTED_FIXES.get(request_row.failure_category) if request_row.failure_category else None

    return TraceDetailResponse(
        id=request_row.id, timestamp=request_row.timestamp, model_name=request_row.model_name,
        status=request_row.status, user_prompt=request_row.user_prompt,
        system_prompt=request_row.system_prompt, full_response=request_row.full_response,
        total_latency_ms=request_row.total_latency_ms, input_tokens=request_row.input_tokens,
        output_tokens=request_row.output_tokens, cost_usd=request_row.cost_usd,
        error_message=request_row.error_message,
        failure_category=request_row.failure_category,
        failure_evidence=request_row.failure_evidence,
        suggested_fix=suggested_fix,
        stages=stage_details, evaluation=evaluation_summary,
    )


@router.get("/{trace_id}/export")
def export_single_trace(
    trace_id: str,
    format: str = Query(default="json", pattern="^(csv|json)$"),
    db: Session = Depends(get_db),
):
    request_row = db.query(Request).filter(Request.id == trace_id).first()
    if not request_row:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")

    stages = db.query(Trace).filter(Trace.request_id == trace_id).order_by(asc(Trace.stage_order)).all()
    evaluation_row = db.query(Evaluation).filter(Evaluation.request_id == trace_id).first()

    if format == "json":
        data = {
            **request_row.to_full_dict(),
            "stages": [s.to_dict() for s in stages],
            "evaluation": evaluation_row.to_dict() if evaluation_row else None,
        }
        content = json.dumps(data, indent=2, default=str)
        return StreamingResponse(
            io.BytesIO(content.encode()), media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=trace_{trace_id[:8]}.json"},
        )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["stage_order", "stage_name", "status", "duration_ms", "error_message"])
    for s in stages:
        writer.writerow([s.stage_order, s.stage_name, s.status, s.duration_ms, s.error_message or ""])
    buffer.seek(0)
    return StreamingResponse(
        io.BytesIO(buffer.getvalue().encode()), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=trace_{trace_id[:8]}_stages.csv"},
    )


@router.delete("/{trace_id}")
def delete_trace(trace_id: str, db: Session = Depends(get_db)):
    request_row = db.query(Request).filter(Request.id == trace_id).first()
    if not request_row:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")
    db.delete(request_row)
    db.commit()
    return {"success": True, "message": "Trace deleted successfully"}
