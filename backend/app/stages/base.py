"""
Base Stage - Foundation class for all pipeline stages

Every stage (PromptBuilder, Tokenizer, LLMCall, etc) inherits from this.
This handles the common logic: timing, error handling, saving to database.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
import time
import logging

from app.models import Trace

logger = logging.getLogger(__name__)


class StageResult:
    """
    Wraps the output of a stage execution

    Attributes:
        success: Did the stage complete without errors?
        output: The actual data produced by this stage
        error: Error message if something went wrong
        duration_ms: How long this stage took
    """

    def __init__(self, success: bool, output: Any = None, error: str = None, duration_ms: int = 0):
        self.success = success
        self.output = output
        self.error = error
        self.duration_ms = duration_ms

    def __repr__(self):
        status = "success" if self.success else "failed"
        return f"<StageResult {status} duration={self.duration_ms}ms>"


class BaseStage(ABC):
    """
    Abstract base class for all pipeline stages.

    How to create a new stage:
    1. Inherit from BaseStage
    2. Set self.stage_name in __init__
    3. Implement the run() method (your actual logic)
    4. Call execute() to run it (this handles timing/errors/saving)

    Example:
        class MyStage(BaseStage):
            def __init__(self):
                super().__init__(stage_name="my_stage")

            def run(self, input_data):
                # Your logic here
                return {"result": "processed"}

        stage = MyStage()
        result = stage.execute(db, request_id=123, stage_order=0, input_data={...})
    """

    def __init__(self, stage_name: str):
        self.stage_name = stage_name

    @abstractmethod
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Override this method with your stage's actual logic.

        Args:
            input_data: Dictionary with whatever this stage needs

        Returns:
            Dictionary with the stage's output

        Raises:
            Any exception if something goes wrong (will be caught by execute())
        """
        pass

    def execute(
        self,
        db: Session,
        request_id: str,
        stage_order: int,
        input_data: Dict[str, Any],
    ) -> StageResult:
        """
        Execute this stage with full timing, error handling, and database logging.

        This is the method you actually call - it wraps run() with:
        - Timing measurement
        - Error catching
        - Automatic Trace record creation in database

        Args:
            db: Database session
            request_id: Which request this stage belongs to
            stage_order: Order of execution (0, 1, 2, ...)
            input_data: Input for this stage

        Returns:
            StageResult with success/output/error/duration
        """
        start_time = datetime.utcnow()
        start_perf = time.perf_counter()

        trace = Trace(
            request_id=request_id,
            stage_name=self.stage_name,
            stage_order=stage_order,
            status="running",
            start_time=start_time,
            stage_input=self._safe_serialize(input_data),
        )
        db.add(trace)
        db.commit()
        db.refresh(trace)

        try:
            # Run the actual stage logic
            output = self.run(input_data)

            # Calculate duration
            duration_ms = int((time.perf_counter() - start_perf) * 1000)
            end_time = datetime.utcnow()

            # Update trace with success
            trace.status = "success"
            trace.stage_output = self._safe_serialize(output)
            trace.duration_ms = duration_ms
            trace.end_time = end_time
            db.commit()

            logger.info(f"Stage '{self.stage_name}' completed in {duration_ms}ms")

            return StageResult(success=True, output=output, duration_ms=duration_ms)

        except Exception as e:
            # Calculate duration even on failure
            duration_ms = int((time.perf_counter() - start_perf) * 1000)
            end_time = datetime.utcnow()
            error_message = str(e)

            # Update trace with error
            trace.status = "error"
            trace.error_message = error_message
            trace.duration_ms = duration_ms
            trace.end_time = end_time
            db.commit()

            logger.error(f"Stage '{self.stage_name}' failed: {error_message}")

            return StageResult(success=False, error=error_message, duration_ms=duration_ms)

    def _safe_serialize(self, data: Any) -> Optional[Dict]:
        """
        Safely convert data to JSON-storable format.
        Truncates very long strings to avoid bloating the database.
        """
        if data is None:
            return None

        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if isinstance(value, str) and len(value) > 2000:
                    result[key] = value[:2000] + "... [truncated]"
                else:
                    result[key] = value
            return result

        return {"value": str(data)[:2000]}
