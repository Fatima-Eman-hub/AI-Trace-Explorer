"""
Evaluation Model - stores quality metrics for LLM responses
"""

from sqlalchemy import Column, String, Text, Float, DateTime, JSON, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import uuid


class Evaluation(Base):
    """
    Stores evaluation/quality metrics for an LLM response
    
    Metrics:
    - hallucination_score: Does model make things up? (0 = no, 1 = yes)
    - faithfulness_score: Is response consistent? (0 = no, 1 = yes)
    - answer_relevancy: Does it answer the question? (0 = no, 1 = yes)
    """
    
    __tablename__ = "evaluations"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign Key to Request
    request_id = Column(String(36), ForeignKey("requests.id"), nullable=False, index=True)
    
    # Quality Scores (0.0 to 1.0 scale)
    hallucination_score = Column(Float, nullable=True)  # 0 (no hallucination) to 1 (high hallucination)
    faithfulness_score = Column(Float, nullable=True)   # 0 (low) to 1 (high)
    answer_relevancy = Column(Float, nullable=True)     # 0 (not relevant) to 1 (very relevant)
    
    # Overall Quality
    overall_quality_score = Column(Float, nullable=True)  # Average or weighted score
    quality_level = Column(String(20), nullable=True)     # excellent, good, fair, poor
    
    # Detailed Metrics (stored as JSON for flexibility)
    detailed_metrics = Column(JSON, nullable=True)
    # Example:
    # {
    #   "entailment_score": 0.92,
    #   "similarity_score": 0.88,
    #   "semantic_consistency": 0.95,
    #   "token_overlap": 0.65
    # }
    
    # Which model was used for evaluation
    evaluation_model = Column(String(100), nullable=True)  # bert-base-uncased, etc
    
    # Flags
    needs_review = Column(Boolean, default=False)  # High hallucination or low relevancy
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    request = relationship("Request", back_populates="evaluations")
    
    # Indexes
    __table_args__ = (
        Index('idx_quality_level', 'quality_level'),
        Index('idx_needs_review', 'needs_review'),
        Index('idx_hallucination', 'hallucination_score'),
    )
    
    def __repr__(self):
        return f"<Evaluation request={self.request_id}, quality={self.quality_level}>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "request_id": self.request_id,
            "hallucination_score": self.hallucination_score,
            "faithfulness_score": self.faithfulness_score,
            "answer_relevancy": self.answer_relevancy,
            "overall_quality_score": self.overall_quality_score,
            "quality_level": self.quality_level,
            "detailed_metrics": self.detailed_metrics,
            "evaluation_model": self.evaluation_model,
            "needs_review": self.needs_review,
        }
    
    def calculate_quality_level(self):
        """Calculate quality level based on scores"""
        if self.overall_quality_score is None:
            return None
        
        score = self.overall_quality_score
        if score >= 0.9:
            return "excellent"
        elif score >= 0.75:
            return "good"
        elif score >= 0.5:
            return "fair"
        else:
            return "poor"
