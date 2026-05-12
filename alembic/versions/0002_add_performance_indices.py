"""add performance indices

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-12
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index for get_daily_cost aggregation (tool_name + created_at)
    op.create_index(
        "ix_tool_calls_tool_name_created_at",
        "tool_calls",
        ["tool_name", "created_at"],
    )
    # Index for approval → tool_call FK lookups
    op.create_index(
        "ix_approvals_tool_call_id",
        "approvals",
        ["tool_call_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_approvals_tool_call_id", table_name="approvals")
    op.drop_index("ix_tool_calls_tool_name_created_at", table_name="tool_calls")
