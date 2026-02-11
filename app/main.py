# app/main.py
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import router_auth, router_service, router_sub, router_usage

# Exposed on /metrics; updated when /health/ollama is called (1 = healthy, 0 = unhealthy)
ollama_up_gauge = Gauge(
    "ollama_up",
    "Health of the Ollama LLM service (1 = healthy, 0 = unhealthy)",
)

logger.remove()
logger.add(sys.stderr, level="INFO")

app = FastAPI(
    title="MoneyMaker-API",
    description="Backend-only SaaS API – AI Content Generator / API-as-a-Service",
    version="0.1.0",
)

# Prometheus metrics exposed at /metrics
Instrumentator().instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router_auth.router)
app.include_router(router_sub.router)
app.include_router(router_usage.router)
app.include_router(router_service.router)


@app.on_event("shutdown")
async def shutdown() -> None:
    """Close DB engine and Redis so the process exits cleanly on SIGTERM."""
    from app.api.deps import close_redis
    from app.db.session import engine
    await close_redis()
    await engine.dispose()
    logger.info("Shutdown complete")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/ollama")
async def health_ollama():
    """
    Ping Ollama (GET /api/tags). Returns 200 if reachable, 503 otherwise.
    Updates the Prometheus gauge ollama_up (1 = healthy, 0 = unhealthy).
    """
    import httpx
    from fastapi.responses import JSONResponse
    from app.core.config import settings
    try:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url)
        if r.status_code != 200:
            ollama_up_gauge.set(0)
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "ollama": "unreachable",
                    "detail": f"Ollama returned {r.status_code}",
                },
            )
        ollama_up_gauge.set(1)
        return {"status": "ok", "ollama": "reachable"}
    except Exception as e:
        ollama_up_gauge.set(0)
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "ollama": "unreachable", "detail": str(e)},
        )


@app.get("/health/ollama/model")
async def health_ollama_model():
    """
    Check that Ollama is reachable and the configured model (OLLAMA_MODEL) is loaded.
    Returns 200 if so, 503 if Ollama is down or the model is not in the list.
    """
    import httpx
    from fastapi.responses import JSONResponse
    from app.core.config import settings
    try:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url)
        if r.status_code != 200:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "ollama": "unreachable",
                    "detail": f"Ollama returned {r.status_code}",
                },
            )
        data = r.json()
        models = data.get("models") or []
        want = settings.OLLAMA_MODEL
        loaded = any(
            m.get("name") == want or (m.get("name") or "").startswith(f"{want}:")
            for m in models
        )
        if not loaded:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "ollama": "reachable",
                    "model": "not_loaded",
                    "detail": f"Model '{want}' not found. Pull it with: ollama pull {want}",
                },
            )
        return {"status": "ok", "ollama": "reachable", "model": want}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "ollama": "unreachable", "detail": str(e)},
        )
