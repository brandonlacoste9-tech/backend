"""create initial tables

Revision ID: a1_initial
Revises:
Create Date: 2025-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id", "users", ["id"], unique=False)

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stripe_price_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("monthly_quota", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plans_id", "plans", ["id"], unique=False)
    op.create_index("ix_plans_stripe_price_id", "plans", ["stripe_price_id"], unique=True)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(64), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_id", "subscriptions", ["id"], unique=False)
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=True)
    op.create_index("ix_subscriptions_stripe_subscription_id", "subscriptions", ["stripe_subscription_id"], unique=True)

    op.create_table(
        "usages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("endpoint", sa.String(64), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usages_id", "usages", ["id"], unique=False)
    op.create_index("ix_usages_timestamp", "usages", ["timestamp"], unique=False)

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("stripe_invoice_id", sa.String(255), nullable=False),
        sa.Column("amount_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoices_id", "invoices", ["id"], unique=False)
    op.create_index("ix_invoices_stripe_invoice_id", "invoices", ["stripe_invoice_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_invoices_stripe_invoice_id", "invoices")
    op.drop_index("ix_invoices_id", "invoices")
    op.drop_table("invoices")
    op.drop_index("ix_usages_timestamp", "usages")
    op.drop_index("ix_usages_id", "usages")
    op.drop_table("usages")
    op.drop_index("ix_subscriptions_stripe_subscription_id", "subscriptions")
    op.drop_index("ix_subscriptions_user_id", "subscriptions")
    op.drop_index("ix_subscriptions_id", "subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_plans_stripe_price_id", "plans")
    op.drop_index("ix_plans_id", "plans")
    op.drop_table("plans")
    op.drop_index("ix_users_email", "users")
    op.drop_index("ix_users_id", "users")
    op.drop_table("users")
