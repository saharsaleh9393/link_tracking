"""Add server-side dashboard sessions and shared login admission counters only."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dashboard_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dashboard_sessions_expires_at", "dashboard_sessions", ["expires_at"])
    op.create_table(
        "dashboard_login_buckets",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("resets_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_dashboard_login_buckets_resets_at", "dashboard_login_buckets", ["resets_at"]
    )


def downgrade():
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT (SELECT count(*) FROM dashboard_sessions) + (SELECT count(*) FROM dashboard_login_buckets)"
        )
    ):
        raise RuntimeError(
            "Refusing to discard dashboard authentication state; stop services and let state expire first"
        )
    op.drop_table("dashboard_login_buckets")
    op.drop_table("dashboard_sessions")
