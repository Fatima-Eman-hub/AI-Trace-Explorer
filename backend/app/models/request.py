"""
Request Model - represents a complete LLM request with all metadata
"""

from sqlalchemy import Column, String, Text, Integer, Float, DateTime, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import uuid


class Request(Base):
    """
    Stores complete information about an LLM request
    
    Fields:
    - id: Unique request ID
    - timestamp: When request was made
    - user_prompt: What user asked
    - system_prompt: Instructions for the model
    - model_name: Which model was used (claude-sonnet, gpt-4, etc)
    - full_response: Complete response from model
    - status: success, error, or timeout
    - total_latency_ms: How long the entire pipeline took
    - input_tokens: Tokens in the prompt
    - output_tokens: Tokens in the response
    - cost_usd: How much this request cost
    """
    
    __tablename__ = "requests"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Input Data
    user_prompt = Column(Text, nullable=False)
    system_prompt = Column(Text, nullable=True)
    few_shot_examples = Column(JSON, nullable=True)  # Store as JSON array
    
    # Model Info
    model_name = Column(String(100), nullable=False, index=True)  # claude-sonnet, gpt-4, etc
    model_parameters = Column(JSON, nullable=True)  # temperature, max_tokens, etc
    
    # Output Data
    full_response = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, index=True, default="pending")  # success, error, timeout
    error_message = Column(Text, nullable=True)
    
    # Performance Metrics
    total_latency_ms = Column(Integer, nullable=True)  # Total time for all stages
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    
    # Cost Tracking
    cost_usd = Column(Float, nullable=True, default=0.0)
    
    # Metadata
    user_id = Column(String(36), nullable=True)  # For multi-user support later
    tags = Column(JSON, nullable=True)  # Custom tags like ["test", "learning"]
    extra_metadata = Column(JSON, nullable=True)  # Any extra data
    # NOTE: named "extra_metadata" (not "metadata") because SQLAlchemy's
    # Declarative Base reserves the attribute name "metadata" internally.
    
    # Relationships
    traces = relationship("Trace", back_populates="request", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="request", cascade="all, delete-orphan")
    
    # Database Indexes for faster queries
    __table_args__ = (
        Index('idx_timestamp_model', 'timestamp', 'model_name'),
        Index('idx_status_timestamp', 'status', 'timestamp'),
        Index('idx_user_timestamp', 'user_id', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<Request id={self.id}, model={self.model_name}, status={self.status}>"
    
    def to_dict(self):
        """Convert to dictionary for JSON response"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "model_name": self.model_name,
            "status": self.status,
            "user_prompt": self.user_prompt[:100] + "..." if len(self.user_prompt) > 100 else self.user_prompt,
            "total_latency_ms": self.total_latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
        }
    
    def to_full_dict(self):
        """Convert to complete dictionary including full response"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "model_name": self.model_name,
            "status": self.status,
            "user_prompt": self.user_prompt,
            "system_prompt": self.system_prompt,
            "full_response": self.full_response,
            "total_latency_ms": self.total_latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "error_message": self.error_message,
        }