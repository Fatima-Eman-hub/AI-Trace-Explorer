"""
Trace Model - stores information about each stage in the pipeline
"""

from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import uuid


class Trace(Base):
    """
    Stores detailed information about each stage of pipeline execution
    
    Example stages:
    - prompt_builder: Format the prompt
    - tokenizer: Count tokens
    - llm_gateway: Route to correct API
    - llm_call: Call the LLM
    - response_parser: Parse response
    - evaluator: Evaluate quality
    
    For one Request, there will be multiple Traces (one per stage)
    """
    
    __tablename__ = "traces"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign Key to Request
    request_id = Column(String(36), ForeignKey("requests.id"), nullable=False, index=True)
    
    # Stage Information
    stage_name = Column(String(50), nullable=False, index=True)  # prompt_builder, tokenizer, etc
    stage_order = Column(Integer)  # 0, 1, 2, 3, ... (order of execution)
    
    # Execution Status
    status = Column(String(20), nullable=False, default="pending")  # pending, running, success, error
    error_message = Column(Text, nullable=True)
    
    # Timing
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)  # How long this stage took
    
    # Input & Output
    stage_input = Column(JSON)  # What went into this stage
    stage_output = Column(JSON)  # What came out of this stage
    
    # Extra metadata for this stage
    stage_metadata = Column(JSON, nullable=True)
    # Example: {"model_provider": "anthropic", "api_latency_ms": 215, "tokens_used": 401}
    # NOTE: named "stage_metadata" (not "metadata") because SQLAlchemy's
    # Declarative Base reserves the attribute name "metadata" internally.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    request = relationship("Request", back_populates="traces")
    
    # Indexes for faster queries
    __table_args__ = (
        Index('idx_request_stage_order', 'request_id', 'stage_order'),
        Index('idx_stage_name', 'stage_name'),
        Index('idx_stage_status', 'status'),
    )
    
    def __repr__(self):
        return f"<Trace request={self.request_id}, stage={self.stage_name}, status={self.status}>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "request_id": self.request_id,
            "stage_name": self.stage_name,
            "stage_order": self.stage_order,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "stage_input": self.stage_input,
            "stage_output": self.stage_output,
            "error_message": self.error_message,
            "metadata": self.stage_metadata,
        }