# app/core/stripe_client.py
from __future__ import annotations

import stripe
from app.core.config import settings

stripe.api_key = settings.STRIPE_API_KEY


def create_checkout_session(
    user_email: str,
    price_id: str,
    success_url: str | None = None,
    cancel_url: str | None = None,
):
    """Returns a Stripe Checkout Session (session.url for redirect)."""
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer_email=user_email,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url or settings.STRIPE_SUCCESS_URL,
        cancel_url=cancel_url or settings.STRIPE_CANCEL_URL,
    )
    return session
