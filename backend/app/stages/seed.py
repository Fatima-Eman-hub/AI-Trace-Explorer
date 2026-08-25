"""
Seed data - populates the supported_models table on first startup.
"""

from sqlalchemy.orm import Session
from app.models import SupportedModel
import logging

logger = logging.getLogger(__name__)


SEED_MODELS = [
    {
        "name": "claude-sonnet", "provider": "anthropic",
        "max_context_tokens": 200000, "max_output_tokens": 8192,
        "input_price_per_1k": 0.003, "output_price_per_1k": 0.015,
        "description": "Anthropic's balanced model - fast and capable.",
        "tier": "standard",
    },
    {
        "name": "claude-opus", "provider": "anthropic",
        "max_context_tokens": 200000, "max_output_tokens": 8192,
        "input_price_per_1k": 0.015, "output_price_per_1k": 0.075,
        "description": "Anthropic's most capable model.",
        "tier": "premium",
    },
    {
        "name": "claude-haiku", "provider": "anthropic",
        "max_context_tokens": 200000, "max_output_tokens": 8192,
        "input_price_per_1k": 0.0008, "output_price_per_1k": 0.004,
        "description": "Anthropic's fastest, cheapest model.",
        "tier": "standard",
    },
    {
        "name": "gpt-oss-120b", "provider": "groq",
        "max_context_tokens": 131000, "max_output_tokens": 32768,
        "input_price_per_1k": 0.0, "output_price_per_1k": 0.0,
        "description": "OpenAI's open-weight 120B model, served free via Groq's LPU inference.",
        "tier": "free",
    },
    {
        "name": "gpt-oss-20b", "provider": "groq",
        "max_context_tokens": 131000, "max_output_tokens": 32768,
        "input_price_per_1k": 0.0, "output_price_per_1k": 0.0,
        "description": "OpenAI's open-weight 20B model, served free via Groq's LPU inference - faster, lighter.",
        "tier": "free",
    },
]


def seed_supported_models(db: Session):
    inserted = 0
    for model_data in SEED_MODELS:
        exists = db.query(SupportedModel).filter(SupportedModel.name == model_data["name"]).first()
        if not exists:
            db.add(SupportedModel(**model_data))
            inserted += 1
    if inserted > 0:
        db.commit()
        logger.info(f"Seeded {inserted} supported model(s)")
