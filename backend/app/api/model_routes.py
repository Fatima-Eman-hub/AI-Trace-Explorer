"""
Model Routes - list which LLMs this app currently supports.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import SupportedModel
from app.api.schemas import SupportedModelResponse

router = APIRouter(prefix="/models", tags=["Models"])


@router.get("", response_model=List[SupportedModelResponse])
def list_models(db: Session = Depends(get_db)):
    """List all models registered in the supported_models table."""
    models = db.query(SupportedModel).filter(SupportedModel.is_active == True).all()
    return models
