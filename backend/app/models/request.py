"""
Request Model - represents a complete LLM request with all metadata
"""

from sqlalchemy import Column, String, Text, Integer, Float, DateTime, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import uuid


class Request(Base):
    __tablename__ = "requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_prompt = Column(Text, nullable=False)
    system_prompt = Column(Text, nullable=True)
    few_shot_examples = Column(JSON, nullable=True)

    model_name = Column(String(100), nullable=False, index=True)
    model_parameters = Column(JSON, nullable=True)

    full_response = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, index=True, default="pending")
    error_message = Column(Text, nullable=True)

    # Failure classification (populated only when status == "error")
    failure_category = Column(String(50), nullable=True, index=True)
    failure_evidence = Column(Text, nullable=True)

    total_latency_ms = Column(Integer, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)

    cost_usd = Column(Float, nullable=True, default=0.0)

    user_id = Column(String(36), nullable=True)
    tags = Column(JSON, nullable=True)
    extra_metadata = Column(JSON, nullable=True)

    traces = relationship("Trace", back_populates="request", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="request", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_timestamp_model', 'timestamp', 'model_name'),
        Index('idx_status_timestamp', 'status', 'timestamp'),
        Index('idx_user_timestamp', 'user_id', 'timestamp'),
    )

    def __repr__(self):
        return f"<Request id={self.id}, model={self.model_name}, status={self.status}>"

    def to_dict(self):
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
            "failure_category": self.failure_category,
        }

    def to_full_dict(self):
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
            "failure_category": self.failure_category,
            "failure_evidence": self.failure_evidence,
        }
