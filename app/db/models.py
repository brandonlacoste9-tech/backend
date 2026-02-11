# app/db/models.py
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    subscription = relationship(
        "Subscription", back_populates="user", uselist=False
    )
    usages = relationship("Usage", back_populates="user")


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    stripe_price_id = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price_usd = Column(Numeric(10, 2), nullable=False)
    monthly_quota = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    stripe_subscription_id = Column(String(255), unique=True, nullable=False)
    status = Column(String(64), default="active")
    current_period_end = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="subscription")
    plan = relationship("Plan")


class Usage(Base):
    """
    Tracks paid-API calls per user in the current billing period.
    One row per request; aggregate monthly via DB view or COUNT.
    """
    __tablename__ = "usages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    endpoint = Column(String(64), nullable=False)
    tokens_used = Column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="usages")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stripe_invoice_id = Column(String(255), unique=True, nullable=False)
    amount_usd = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
