# app/workers/tasks.py
import requests

from celery import Celery, states
from celery.utils.log import get_task_logger

from app.core.config import settings

celery_app = Celery(
    "tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

logger = get_task_logger(__name__)

SUMMARY_INSTRUCTION = (
    "Summarise the following in 3 bullet points or under 80 words:\n\n"
)


@celery_app.task(bind=True, name="generate_content_task")
def generate_content_task(
    self,
    job_id: str,
    user_id: int,
    prompt: str,
):
    """
    Call Ollama /api/generate to produce a short summary of the given text.
    """
    try:
        logger.info("Job %s started for user %s", job_id, user_id)

        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
        body = {
            "model": settings.OLLAMA_MODEL,
            "prompt": SUMMARY_INSTRUCTION + prompt,
            "stream": False,
        }
        resp = requests.post(url, json=body, timeout=120)  # 120s for slower local models (docs: use 120s)
        if not resp.ok:
            msg = (resp.text and resp.text.strip()) or f"HTTP {resp.status_code}"
            logger.warning("Job %s Ollama error: %s", job_id, msg)
            self.update_state(state=states.FAILURE, meta={"exc": msg})
            raise RuntimeError(msg)
        data = resp.json()
        summary = data.get("response", "").strip()

        logger.info("Job %s completed", job_id)
        return {"job_id": job_id, "result": summary}
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        self.update_state(state=states.FAILURE, meta={"exc": str(exc)})
        raise
