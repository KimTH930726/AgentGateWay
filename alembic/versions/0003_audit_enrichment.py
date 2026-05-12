"""audit enrichment — trace_id, policy_reason, duration_ms

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tool_calls", sa.Column("trace_id", sa.String(64), nullable=False, server_default=""))
    op.add_column("tool_calls", sa.Column("policy_reason", sa.Text(), nullable=False, server_default=""))
    op.add_column("tool_calls", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.create_index("ix_tool_calls_trace_id", "tool_calls", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_tool_calls_trace_id", table_name="tool_calls")
    op.drop_column("tool_calls", "duration_ms")
    op.drop_column("tool_calls", "policy_reason")
    op.drop_column("tool_calls", "trace_id")
