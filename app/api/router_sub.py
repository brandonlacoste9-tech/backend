# app/api/router_sub.py
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import stripe

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core import stripe_client
from app.db import models
from app.db.session import async_session

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("/plans")
async def list_plans(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Plan).where(models.Plan.is_active == True)
    )
    plans = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price_usd": float(p.price_usd),
            "monthly_quota": p.monthly_quota,
            "stripe_price_id": p.stripe_price_id,
        }
        for p in plans
    ]


@router.post("/checkout/{plan_id}")
async def checkout(
    plan_id: int,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await db.get(models.Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    session = stripe_client.create_checkout_session(
        user_email=user.email,
        price_id=plan.stripe_price_id,
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
    )
    return {"checkout_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email")
        subscription_id = session.get("subscription")
        if not customer_email or not subscription_id:
            return JSONResponse(content={"status": "ok"})

        # Retrieve subscription for current_period_end
        try:
            sub_obj = stripe.Subscription.retrieve(subscription_id)
            current_period_end = datetime.utcfromtimestamp(sub_obj.current_period_end)
            status_str = sub_obj.status
        except Exception:
            current_period_end = datetime.utcnow()
            status_str = "active"

        # Resolve price_id from session (line_items or mode)
        price_id = None
        if session.get("line_items") and session["line_items"].get("data"):
            price_id = session["line_items"]["data"][0].get("price", {}).get("id")
        if not price_id and session.get("mode") == "subscription":
            # Fallback: get from subscription expand
            try:
                sub_obj = stripe.Subscription.retrieve(
                    subscription_id, expand=["items.data.price.id"]
                )
                if sub_obj.get("items", {}).get("data"):
                    price_id = sub_obj["items"]["data"][0].get("price", {}).get("id")
            except Exception:
                pass

        async with async_session() as db:
            result = await db.execute(
                select(models.User).where(models.User.email == customer_email)
            )
            usr = result.scalar_one_or_none()
            if not usr:
                usr = models.User(
                    email=customer_email,
                    hashed_password="*",
                )
                db.add(usr)
                await db.flush()

            plan_result = await db.execute(
                select(models.Plan).where(models.Plan.stripe_price_id == price_id)
            )
            plan_obj = plan_result.scalar_one_or_none()
            if not plan_obj and price_id:
                plan_result = await db.execute(select(models.Plan).limit(1))
                plan_obj = plan_result.scalar_one_or_none()
            if not plan_obj:
                await db.commit()
                return JSONResponse(content={"status": "ok"})

            # Upsert subscription (replace if exists)
            sub_result = await db.execute(
                select(models.Subscription).where(
                    models.Subscription.user_id == usr.id
                )
            )
            existing = sub_result.scalar_one_or_none()
            if existing:
                existing.plan_id = plan_obj.id
                existing.stripe_subscription_id = subscription_id
                existing.status = status_str
                existing.current_period_end = current_period_end
            else:
                sub = models.Subscription(
                    user_id=usr.id,
                    plan_id=plan_obj.id,
                    stripe_subscription_id=subscription_id,
                    status=status_str,
                    current_period_end=current_period_end,
                )
                db.add(sub)
            await db.commit()

    return JSONResponse(content={"status": "ok"})

