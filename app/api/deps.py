# app/api/deps.py
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from redis import asyncio as aioredis
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token
from app.db import models
from app.db.session import async_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> models.User:
    try:
        payload = decode_token(token)
        email: str | None = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    result = await db.execute(
        select(models.User).where(models.User.email == email)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Shared Redis client."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def close_redis() -> None:
    """Close the shared Redis connection (for graceful shutdown)."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def check_quota(
    user: models.User,
    db: AsyncSession,
    endpoint: str = "generate",
) -> bool:
    """Enforce plan quota and per-second rate limit. Raise 403/429 if exceeded."""
    # Lazy-load subscription/plan if not loaded
    result = await db.execute(
        select(models.Subscription)
        .where(models.Subscription.user_id == user.id)
        .where(models.Subscription.status == "active")
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active subscription",
        )

    result = await db.execute(select(models.Plan).where(models.Plan.id == subscription.plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Plan not found",
        )

    # Current period start (month of current_period_end)
    period_end = subscription.current_period_end
    # Use period_end's month as the billing period
    period_start = period_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # If we track by subscription period, we need period_start from Stripe; for simplicity use start of month of period_end
    result = await db.execute(
        select(func.count(models.Usage.id))
        .where(models.Usage.user_id == user.id)
        .where(models.Usage.timestamp >= period_start)
        .where(models.Usage.timestamp <= period_end)
    )
    usage_count = result.scalar() or 0

    if usage_count >= plan.monthly_quota:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Quota exceeded: {plan.monthly_quota} calls/month. Upgrade your plan.",
        )

    # Per-second burst limit via Redis
    redis = get_redis()
    key = f"rl:{user.id}:{endpoint}"
    ttl = 1
    cur = await redis.incr(key)
    if cur == 1:
        await redis.expire(key, ttl)
    if cur > 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded (5 req/s)",
        )

    return True
