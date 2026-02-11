# app/api/router_auth.py
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db import models

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/register")
async def register(
    payload: RegisterIn,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.User).where(models.User.email == payload.email)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = models.User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()
    # Assign Free plan so user has a quota without Stripe
    plan_result = await db.execute(
        select(models.Plan).where(models.Plan.name == "Free")
    )
    free_plan = plan_result.scalar_one_or_none()
    if free_plan:
        period_end = datetime.utcnow() + timedelta(days=30)
        db.add(
            models.Subscription(
                user_id=user.id,
                plan_id=free_plan.id,
                stripe_subscription_id=f"free_{user.id}",
                status="active",
                current_period_end=period_end,
            )
        )
    await db.commit()
    await db.refresh(user)
    access = create_access_token(data={"sub": user.email})
    refresh = create_refresh_token(data={"sub": user.email})
    return TokenOut(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.User).where(models.User.email == payload.email)
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive",
        )
    access = create_access_token(data={"sub": user.email})
    refresh = create_refresh_token(data={"sub": user.email})
    return TokenOut(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    payload: RefreshIn,
    db: AsyncSession = Depends(get_db),
):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        email = data.get("sub")
        if not email:
            raise ValueError("Missing sub")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
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
    access = create_access_token(data={"sub": user.email})
    new_refresh = create_refresh_token(data={"sub": user.email})
    return TokenOut(access_token=access, refresh_token=new_refresh)
