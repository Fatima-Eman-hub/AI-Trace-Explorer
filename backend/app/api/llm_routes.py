from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.pipeline import PipelineOrchestrator
from app.api.schemas import LLMRequestCreate, LLMRequestResponse
from app.security import verify_api_key, enforce_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["LLM"])
orchestrator = PipelineOrchestrator()


@router.post(
    "/request",
    response_model=LLMRequestResponse,
    dependencies=[Depends(verify_api_key), Depends(enforce_rate_limit)],
)
def create_llm_request(
    payload: LLMRequestCreate,
    db: Session = Depends(get_db),
):
    """
    Send a prompt through the full 7-stage pipeline.

    Protected by (optional) API key auth and rate limiting - see
    app/security.py. Both are no-ops unless configured in .env.
    """
    few_shot = (
        [ex.model_dump() for ex in payload.few_shot_examples]
        if payload.few_shot_examples else None
    )
    model_parameters = (
        payload.model_parameters.model_dump() if payload.model_parameters else None
    )

    try:
        result = orchestrator.run(
            db=db,
            user_prompt=payload.user_prompt,
            model_name=payload.model_name,
            system_prompt=payload.system_prompt,
            few_shot_examples=few_shot,
            model_parameters=model_parameters,
            tags=payload.tags,
        )
    except Exception as e:
        logger.exception("Unexpected error running pipeline")
        raise HTTPException(status_code=500, detail=f"Internal pipeline error: {e}")

    return LLMRequestResponse(**result)