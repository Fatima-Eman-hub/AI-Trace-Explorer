from typing import Any, Callable, Dict, List, Optional
from sqlalchemy.orm import Session
import logging

from app.models import Request, Evaluation
from app.stages import (
    PromptBuilderStage,
    TokenizerStage,
    LLMGatewayStage,
    LLMCallStage,
    ResponseParserStage,
    EvaluatorStage,
    CostCalculatorStage,
)

logger = logging.getLogger(__name__)

OnStageCallback = Optional[Callable[[Dict[str, Any]], None]]


class PipelineOrchestrator:
    def __init__(self):
        self.prompt_builder = PromptBuilderStage()
        self.tokenizer = TokenizerStage()
        self.llm_gateway = LLMGatewayStage()
        self.llm_call = LLMCallStage()
        self.response_parser = ResponseParserStage()
        self.evaluator = EvaluatorStage()
        self.cost_calculator = CostCalculatorStage()

    def run(
        self,
        db: Session,
        user_prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        few_shot_examples: Optional[List[Dict]] = None,
        model_parameters: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
        on_stage: OnStageCallback = None,
    ) -> Dict[str, Any]:
        """Run the complete pipeline for one request.

        Args:
            on_stage: optional callback invoked with each stage's summary
                dict the moment that stage finishes (success or error).
        """

        request = Request(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            few_shot_examples=few_shot_examples,
            model_name=model_name,
            model_parameters=model_parameters or {},
            status="pending",
            tags=tags or [],
        )
        db.add(request)
        db.commit()
        db.refresh(request)

        request_id = request.id
        stages_summary = []
        stage_order = 0

        def record(stage_name: str, result) -> Dict[str, Any]:
            summary = self._summarize(stage_name, result)
            stages_summary.append(summary)
            if on_stage:
                try:
                    on_stage(summary)
                except Exception:
                    logger.exception("on_stage callback raised - ignoring, pipeline continues")
            return summary

        # ===== STAGE 1: Prompt Builder =====
        result = self.prompt_builder.execute(
            db, request_id, stage_order,
            input_data={
                "user_prompt": user_prompt,
                "system_prompt": system_prompt,
                "few_shot_examples": few_shot_examples or [],
            },
        )
        record("prompt_builder", result)
        if not result.success:
            return self._fail(db, request, "prompt_builder", result.error, stages_summary)
        stage_order += 1
        formatted_prompt = result.output["formatted_prompt"]

        # ===== STAGE 2: Tokenizer =====
        result = self.tokenizer.execute(
            db, request_id, stage_order,
            input_data={"formatted_prompt": formatted_prompt, "system_prompt": system_prompt or ""},
        )
        record("tokenizer", result)
        if not result.success:
            return self._fail(db, request, "tokenizer", result.error, stages_summary)
        stage_order += 1

        # ===== STAGE 3: LLM Gateway =====
        result = self.llm_gateway.execute(
            db, request_id, stage_order,
            input_data={"model_name": model_name, "model_parameters": model_parameters or {}},
        )
        record("llm_gateway", result)
        if not result.success:
            return self._fail(db, request, "llm_gateway", result.error, stages_summary)
        stage_order += 1
        provider = result.output["provider"]
        resolved_parameters = result.output["resolved_parameters"]

        # ===== STAGE 4: LLM Call =====
        result = self.llm_call.execute(
            db, request_id, stage_order,
            input_data={
                "provider": provider, "model_name": model_name,
                "formatted_prompt": formatted_prompt, "system_prompt": system_prompt,
                "resolved_parameters": resolved_parameters,
            },
        )
        record("llm_call", result)
        if not result.success:
            return self._fail(db, request, "llm_call", result.error, stages_summary)
        stage_order += 1
        actual_input_tokens = result.output["actual_input_tokens"]
        actual_output_tokens = result.output["actual_output_tokens"]
        response_text = result.output["response_text"]
        stop_reason = result.output["stop_reason"]

        # ===== STAGE 5: Response Parser =====
        result = self.response_parser.execute(
            db, request_id, stage_order,
            input_data={"response_text": response_text, "stop_reason": stop_reason},
        )
        record("response_parser", result)
        if not result.success:
            return self._fail(db, request, "response_parser", result.error, stages_summary)
        stage_order += 1
        clean_response = result.output["clean_response"]

        # ===== STAGE 6: Evaluator =====
        result = self.evaluator.execute(
            db, request_id, stage_order,
            input_data={"user_prompt": user_prompt, "system_prompt": system_prompt, "clean_response": clean_response},
        )
        record("evaluator", result)
        if not result.success:
            return self._fail(db, request, "evaluator", result.error, stages_summary)
        stage_order += 1
        evaluation_output = result.output

        evaluation = Evaluation(
            request_id=request_id,
            hallucination_score=evaluation_output["hallucination_score"],
            faithfulness_score=evaluation_output["faithfulness_score"],
            answer_relevancy=evaluation_output["answer_relevancy"],
            overall_quality_score=evaluation_output["overall_quality_score"],
            quality_level=evaluation_output["quality_level"],
            evaluation_model=evaluation_output["evaluation_model"],
            needs_review=evaluation_output["needs_review"],
        )
        db.add(evaluation)
        db.commit()

        # ===== STAGE 7: Cost Calculator =====
        result = self.cost_calculator.execute(
            db, request_id, stage_order,
            input_data={
                "model_name": model_name,
                "actual_input_tokens": actual_input_tokens,
                "actual_output_tokens": actual_output_tokens,
            },
        )
        record("cost_calculator", result)
        if not result.success:
            return self._fail(db, request, "cost_calculator", result.error, stages_summary)
        total_cost_usd = result.output["total_cost_usd"]

        total_latency_ms = sum(s["duration_ms"] for s in stages_summary)

        request.status = "success"
        request.full_response = clean_response
        request.total_latency_ms = total_latency_ms
        request.input_tokens = actual_input_tokens
        request.output_tokens = actual_output_tokens
        request.cost_usd = total_cost_usd
        db.commit()
        db.refresh(request)

        logger.info(
            f"Pipeline completed for request {request_id}: "
            f"{total_latency_ms}ms, ${total_cost_usd}, quality={evaluation_output['quality_level']}"
        )

        return {
            "trace_id": request_id,
            "status": "success",
            "response": clean_response,
            "total_latency_ms": total_latency_ms,
            "stages": stages_summary,
            "metrics": {
                "input_tokens": actual_input_tokens,
                "output_tokens": actual_output_tokens,
                "cost_usd": total_cost_usd,
            },
            "evaluation": {
                "hallucination_score": evaluation_output["hallucination_score"],
                "faithfulness_score": evaluation_output["faithfulness_score"],
                "answer_relevancy": evaluation_output["answer_relevancy"],
                "overall_quality_score": evaluation_output["overall_quality_score"],
                "quality_level": evaluation_output["quality_level"],
                "needs_review": evaluation_output["needs_review"],
            },
        }

    def _summarize(self, stage_name: str, result) -> Dict[str, Any]:
        return {
            "stage_name": stage_name,
            "status": "success" if result.success else "error",
            "duration_ms": result.duration_ms,
            "output": result.output,
            "error": result.error,
        }

    def _fail(self, db: Session, request: Request, failed_stage: str, error: str,
               stages_summary: List[Dict]) -> Dict[str, Any]:
        request.status = "error"
        request.error_message = f"Failed at stage '{failed_stage}': {error}"
        db.commit()
        logger.error(f"Pipeline failed for request {request.id} at '{failed_stage}': {error}")
        return {
            "trace_id": request.id,
            "status": "error",
            "failed_stage": failed_stage,
            "error": error,
            "stages": stages_summary,
        }