"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tools",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tool_id", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("risk_level", sa.Enum("LOW", "MEDIUM", "HIGH", name="risklevel"), nullable=False),
        sa.Column("required_role", sa.String(64), nullable=False),
        sa.Column("approval_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sandbox_supported", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("daily_cost_limit", sa.Float, nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tools_tool_id", "tools", ["tool_id"])

    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("agent_id", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("allowed_domains", sa.JSON, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agents_agent_id", "agents", ["agent_id"])

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", sa.String(64), nullable=False, unique=True),
        sa.Column("roles", sa.JSON, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_user_id", "users", ["user_id"])

    op.create_table(
        "tool_calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("request_id", sa.String(64), nullable=False, unique=True),
        sa.Column("agent_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("input_data", sa.JSON, nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("risk_level", sa.Enum("LOW", "MEDIUM", "HIGH", name="risklevel"), nullable=False),
        sa.Column(
            "policy_decision",
            sa.Enum("ALLOW", "REQUIRE_APPROVAL", "DENY", name="policydecision"),
            nullable=False,
        ),
        sa.Column(
            "approval_status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", "EXECUTED", "FAILED", name="approvalstatus"),
            nullable=True,
        ),
        sa.Column(
            "execution_status",
            sa.Enum("SUCCESS", "FAILED", "SKIPPED", "SIMULATED", name="executionstatus"),
            nullable=True,
        ),
        sa.Column("estimated_cost", sa.Float, nullable=False, server_default="0"),
        sa.Column("actual_cost", sa.Float, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tool_calls_request_id", "tool_calls", ["request_id"])
    op.create_index("ix_tool_calls_agent_id", "tool_calls", ["agent_id"])
    op.create_index("ix_tool_calls_user_id", "tool_calls", ["user_id"])

    op.create_table(
        "approvals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tool_call_id", UUID(as_uuid=True), sa.ForeignKey("tool_calls.id"), nullable=False),
        sa.Column("approver_id", sa.String(64), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", "EXECUTED", "FAILED", name="approvalstatus"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("approvals")
    op.drop_table("tool_calls")
    op.drop_table("users")
    op.drop_table("agents")
    op.drop_table("tools")
    op.execute("DROP TYPE IF EXISTS risklevel")
    op.execute("DROP TYPE IF EXISTS policydecision")
    op.execute("DROP TYPE IF EXISTS approvalstatus")
    op.execute("DROP TYPE IF EXISTS executionstatus")
