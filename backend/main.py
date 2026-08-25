from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
import asyncio
import logging

from app.config import settings
from app.database import init_db, SessionLocal
from app.seed import seed_supported_models
from app.pipeline import PipelineOrchestrator
from app.security import rate_limiter

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Trace Explorer",
    description="Real-time LLM request tracing and monitoring dashboard",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    logger.info("Starting AI Trace Explorer...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Auth enabled: {settings.auth_enabled()}")
    init_db()
    logger.info("Database ready")

    db = SessionLocal()
    try:
        seed_supported_models(db)
    finally:
        db.close()


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down AI Trace Explorer")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "environment": settings.environment, "debug": settings.debug}


@app.get("/", tags=["Root"])
async def root():
    return {
        "name": "AI Trace Explorer",
        "version": "0.1.0",
        "description": "Real-time LLM request tracing and monitoring",
        "docs": "/docs",
        "endpoints": {"health": "/health", "api": "/api/v1", "websocket": "/ws/llm/request"},
    }


# ==================== WEBSOCKET: real-time pipeline streaming ====================

_ws_orchestrator = PipelineOrchestrator()


@app.websocket("/ws/llm/request")
async def ws_llm_request(websocket: WebSocket):
    """
    Real-time version of POST /api/v1/llm/request.

    Protocol: client connects, sends ONE JSON message with the request
    payload (same shape as the REST endpoint's body). Server then sends
    one message per pipeline stage THE INSTANT it completes:
        {"type": "stage", "stage": {...}}
    and finally either:
        {"type": "done", "result": {...}}   (same shape as REST response)
        {"type": "error", "error": "..."}
    then closes the connection.

    This is genuinely real-time - unlike the REST endpoint (which blocks
    until all 7 stages finish and returns everything at once), each
    "stage" message arrives the moment that stage's real work is done.
    """
    await websocket.accept()

    try:
        payload = await websocket.receive_json()
    except Exception:
        await websocket.send_json({"type": "error", "error": "Expected a JSON payload on connect."})
        await websocket.close(code=1003)
        return

    # Optional auth/rate-limit checks, mirroring the REST endpoint
    client_key = payload.get("api_key")
    if settings.auth_enabled() and client_key != settings.api_key:
        await websocket.send_json({"type": "error", "error": "Missing or invalid API key."})
        await websocket.close(code=1008)
        return

    client_ip = websocket.client.host if websocket.client else "unknown"
    try:
        rate_limiter.check(client_ip, settings.rate_limit_per_minute)
    except Exception as e:
        await websocket.send_json({"type": "error", "error": str(getattr(e, "detail", e))})
        await websocket.close(code=1008)
        return

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    db = SessionLocal()

    def on_stage(stage_summary):
        # Called from the worker THREAD (pipeline.run is sync/blocking),
        # so we hop back onto the event loop thread-safely to enqueue it.
        loop.call_soon_threadsafe(queue.put_nowait, {"type": "stage", "stage": stage_summary})

    async def run_pipeline():
        try:
            result = await run_in_threadpool(
                _ws_orchestrator.run,
                db,
                payload.get("user_prompt"),
                payload.get("model_name"),
                payload.get("system_prompt"),
                None,
                payload.get("model_parameters"),
                payload.get("tags"),
                on_stage,
            )
            await queue.put({"type": "done", "result": result})
        except Exception as e:
            logger.exception("WebSocket pipeline run failed")
            await queue.put({"type": "error", "error": str(e)})

    task = asyncio.create_task(run_pipeline())

    try:
        while True:
            msg = await queue.get()
            await websocket.send_json(msg)
            if msg["type"] in ("done", "error"):
                break
    except WebSocketDisconnect:
        logger.info("Client disconnected mid-pipeline")
    finally:
        task.cancel()
        db.close()
        try:
            await websocket.close()
        except Exception:
            pass


# ==================== API ROUTES ====================

from app.api import llm_routes, trace_routes, model_routes, analytics_routes

app.include_router(llm_routes.router, prefix="/api/v1")
app.include_router(trace_routes.router, prefix="/api/v1")
app.include_router(model_routes.router, prefix="/api/v1")
app.include_router(analytics_routes.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )