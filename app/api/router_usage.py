# app/api/router_usage.py
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db import models

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/me")
async def my_usage(
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Current period usage count (and optional quota from subscription)."""
    result = await db.execute(
        select(models.Subscription)
        .where(models.Subscription.user_id == user.id)
        .where(models.Subscription.status == "active")
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return {"usage": 0, "quota": 0, "period_end": None}

    result = await db.execute(select(models.Plan).where(models.Plan.id == sub.plan_id))
    plan = result.scalar_one_or_none()
    period_end = sub.current_period_end
    period_start = period_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(func.count(models.Usage.id))
        .where(models.Usage.user_id == user.id)
        .where(models.Usage.timestamp >= period_start)
        .where(models.Usage.timestamp <= period_end)
    )
    usage = result.scalar() or 0
    quota = plan.monthly_quota if plan else 0
    return {
        "usage": usage,
        "quota": quota,
        "period_end": period_end.isoformat() if period_end else None,
    }


@router.get("/history")
async def usage_history(
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Paginated usage records for the current user."""
    result = await db.execute(
        select(models.Usage)
        .where(models.Usage.user_id == user.id)
        .order_by(models.Usage.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "endpoint": r.endpoint,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "tokens_used": r.tokens_used,
        }
        for r in rows
    ]
