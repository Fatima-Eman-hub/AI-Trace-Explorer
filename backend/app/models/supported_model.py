"""
SupportedModel - registry of available LLM models
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Date, Boolean, Index
from datetime import datetime, date
from app.database import Base
import uuid


class SupportedModel(Base):
    """
    Registry of all LLM models we support
    
    Examples:
    - claude-sonnet (Anthropic)
    - gpt-4 (OpenAI)
    - gemini-pro (Google)
    - llama2 (Meta)
    """
    
    __tablename__ = "supported_models"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Model Identification
    name = Column(String(100), unique=True, nullable=False, index=True)  # claude-sonnet, gpt-4, etc
    provider = Column(String(50), nullable=False)  # openai, anthropic, google, meta
    
    # Capabilities
    max_context_tokens = Column(Integer)  # e.g., 200000 for Claude Opus
    max_output_tokens = Column(Integer, nullable=True)  # Maximum tokens it can generate
    
    # Pricing (per 1000 tokens)
    input_price_per_1k = Column(Float, default=0.0)  # e.g., 0.003 USD
    output_price_per_1k = Column(Float, default=0.0)  # e.g., 0.006 USD
    
    # Status
    is_active = Column(Boolean, default=True)  # Can use this model?
    is_available = Column(Boolean, default=True)  # Is API currently available?
    
    # Metadata
    description = Column(String(500), nullable=True)  # Human-readable description
    release_date = Column(Date, nullable=True)  # When model was released
    tier = Column(String(50), nullable=True)  # premium, standard, experimental
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_provider', 'provider'),
        Index('idx_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<SupportedModel name={self.name}, provider={self.provider}>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "max_context_tokens": self.max_context_tokens,
            "max_output_tokens": self.max_output_tokens,
            "input_price_per_1k": self.input_price_per_1k,
            "output_price_per_1k": self.output_price_per_1k,
            "is_active": self.is_active,
            "is_available": self.is_available,
            "description": self.description,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "tier": self.tier,
        }
    
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for this request"""
        input_cost = (input_tokens / 1000) * self.input_price_per_1k
        output_cost = (output_tokens / 1000) * self.output_price_per_1k
        return input_cost + output_cost
