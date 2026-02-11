# app/api/router_service.py
import uuid

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import check_quota, get_current_user, get_db
from app.db import models
from app.workers.tasks import celery_app, generate_content_task

router = APIRouter(prefix="/service", tags=["service"])


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=5, max_length=5000)


class GenerateResponse(BaseModel):
    job_id: str
    status: str = "queued"
    result: str | None = None
    detail: str | None = None  # error message when status is "failed"


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    payload: GenerateRequest,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await check_quota(user, db, endpoint="generate")

    job_id = str(uuid.uuid4())
    usage = models.Usage(
        user_id=user.id,
        endpoint="generate",
        tokens_used=0,
    )
    db.add(usage)
    await db.commit()

    generate_content_task.delay(
        job_id=job_id,
        user_id=user.id,
        prompt=payload.prompt,
    )
    return GenerateResponse(job_id=job_id, status="queued")


@router.get("/status/{job_id}", response_model=GenerateResponse)
async def job_status(
    job_id: str,
    user: models.User = Depends(get_current_user),
):
    async_result = AsyncResult(job_id, app=celery_app)
    if async_result.state == "PENDING":
        return GenerateResponse(job_id=job_id, status="queued")
    if async_result.state == "SUCCESS":
        data = async_result.get()
        return GenerateResponse(
            job_id=job_id,
            status="completed",
            result=data.get("result") if isinstance(data, dict) else None,
        )
    if async_result.state == "FAILURE":
        meta = getattr(async_result, "info", None) or {}
        err = meta.get("exc", "") if isinstance(meta, dict) else ""
        if not err and getattr(async_result, "result", None):
            err = str(async_result.result)
        return GenerateResponse(
            job_id=job_id, status="failed", detail=err or None
        )
    return GenerateResponse(job_id=job_id, status=(async_result.state or "queued").lower())
