"""governance expansion — agent tool policies, agent budgets, decision/rule trace, config change log

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- tools: soft cost threshold ---------------------------------------
    op.add_column(
        "tools",
        sa.Column("warn_cost_threshold", sa.Float, nullable=True),
    )

    # --- agents: budgets + token limit ------------------------------------
    op.add_column("agents", sa.Column("daily_cost_limit", sa.Float, nullable=True))
    op.add_column("agents", sa.Column("monthly_cost_limit", sa.Float, nullable=True))
    op.add_column("agents", sa.Column("daily_token_limit", sa.Integer, nullable=True))
    op.add_column("agents", sa.Column("daily_cost_warn_threshold", sa.Float, nullable=True))

    # --- tool_calls: governance enrichment --------------------------------
    op.add_column("tool_calls", sa.Column("tokens_used", sa.Integer, nullable=True))
    op.add_column("tool_calls", sa.Column("rule_trace", sa.JSON, nullable=True))
    op.add_column("tool_calls", sa.Column("selected_reason", sa.Text, nullable=True))
    op.add_column("tool_calls", sa.Column("candidate_tools", sa.JSON, nullable=True))
    op.create_index(
        "ix_tool_calls_agent_id_created_at",
        "tool_calls",
        ["agent_id", "created_at"],
    )

    # --- new table: agent_tool_policies -----------------------------------
    op.create_table(
        "agent_tool_policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("agent_id", sa.String(64), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column(
            "policy_type",
            sa.Enum("ALLOW", "DENY", name="agenttoolpolicytype"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("reason", sa.Text, nullable=False, server_default=""),
        sa.Column("created_by", sa.String(64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "agent_id", "tool_name", "policy_type",
            name="uq_agent_tool_policies_agent_tool_type",
        ),
    )
    op.create_index(
        "ix_agent_tool_policies_agent_id", "agent_tool_policies", ["agent_id"]
    )
    op.create_index(
        "ix_agent_tool_policies_agent_id_enabled",
        "agent_tool_policies",
        ["agent_id", "enabled"],
    )

    # --- new table: config_change_logs ------------------------------------
    op.create_table(
        "config_change_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "entity_type",
            sa.Enum(
                "TOOL", "AGENT", "USER", "AGENT_TOOL_POLICY",
                name="governanceentitytype",
            ),
            nullable=False,
        ),
        sa.Column("entity_key", sa.String(128), nullable=False),
        sa.Column(
            "change_type",
            sa.Enum("CREATE", "UPDATE", "DELETE", name="changetype"),
            nullable=False,
        ),
        sa.Column("before", sa.JSON, nullable=True),
        sa.Column("after", sa.JSON, nullable=True),
        sa.Column("reason", sa.Text, nullable=False, server_default=""),
        sa.Column("changed_by", sa.String(64), nullable=False, server_default=""),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_config_change_logs_entity_type", "config_change_logs", ["entity_type"]
    )
    op.create_index(
        "ix_config_change_logs_entity_key", "config_change_logs", ["entity_key"]
    )
    op.create_index(
        "ix_config_change_logs_changed_at", "config_change_logs", ["changed_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_config_change_logs_changed_at", table_name="config_change_logs")
    op.drop_index("ix_config_change_logs_entity_key", table_name="config_change_logs")
    op.drop_index("ix_config_change_logs_entity_type", table_name="config_change_logs")
    op.drop_table("config_change_logs")

    op.drop_index(
        "ix_agent_tool_policies_agent_id_enabled", table_name="agent_tool_policies"
    )
    op.drop_index("ix_agent_tool_policies_agent_id", table_name="agent_tool_policies")
    op.drop_table("agent_tool_policies")

    op.drop_index("ix_tool_calls_agent_id_created_at", table_name="tool_calls")
    op.drop_column("tool_calls", "candidate_tools")
    op.drop_column("tool_calls", "selected_reason")
    op.drop_column("tool_calls", "rule_trace")
    op.drop_column("tool_calls", "tokens_used")

    op.drop_column("agents", "daily_cost_warn_threshold")
    op.drop_column("agents", "daily_token_limit")
    op.drop_column("agents", "monthly_cost_limit")
    op.drop_column("agents", "daily_cost_limit")

    op.drop_column("tools", "warn_cost_threshold")

    op.execute("DROP TYPE IF EXISTS agenttoolpolicytype")
    op.execute("DROP TYPE IF EXISTS governanceentitytype")
    op.execute("DROP TYPE IF EXISTS changetype")
