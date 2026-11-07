"""Persist Linkspaces and freeze existing link URLs without touching click history."""

import uuid

import sqlalchemy as sa
from alembic import op

from app.config import get_settings
from app.linkspace_config import normalize_base

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
    op.create_table(
        "linkspaces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("base_url", sa.String(300), nullable=False),
        sa.Column("path_prefix", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("base_url", "path_prefix", name="uq_linkspaces_configuration"),
        sa.CheckConstraint("NOT is_default OR is_active", name="ck_linkspaces_active_default"),
    )
    op.create_index(
        "uq_linkspaces_default",
        "linkspaces",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.add_column("links", sa.Column("linkspace_id", sa.Uuid(), nullable=True))
    op.add_column("links", sa.Column("tracking_base_url", sa.String(300), nullable=True))
    op.add_column("links", sa.Column("tracking_path_prefix", sa.String(50), nullable=True))
    op.create_foreign_key(
        "links_linkspace_id_fkey", "links", "linkspaces", ["linkspace_id"], ["id"]
    )
    op.create_index("ix_links_linkspace_id", "links", ["linkspace_id"])
    space_id = uuid.uuid4()
    base = get_settings().public_base_url.rstrip("/")
    if len(base) > 300:
        raise RuntimeError("PUBLIC_BASE_URL exceeds the supported length; migration rolled back")
    try:
        configured_base = normalize_base(base)
    except ValueError:
        # Preserve older PUBLIC_BASE_URL configurations without rewriting their issued URLs.
        configured_base = base
    connection.execute(
        sa.text("""
        INSERT INTO linkspaces (id, name, base_url, path_prefix, is_active, is_default)
        VALUES (:id, 'Original links', :base, 'r', true, true)
    """),
        {"id": space_id, "base": configured_base},
    )
    connection.execute(
        sa.text("""
        UPDATE links SET linkspace_id = :id, tracking_base_url = :base, tracking_path_prefix = 'r'
    """),
        {"id": space_id, "base": base},
    )


def downgrade():
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT count(*) FROM links WHERE tracking_path_prefix != 'r' OR tracking_base_url != :base"
        ),
        {"base": get_settings().public_base_url.rstrip("/")},
    ):
        raise RuntimeError("Downgrade would discard custom URLs; preserve them before downgrading")
    op.drop_index("ix_links_linkspace_id", table_name="links")
    op.drop_constraint("links_linkspace_id_fkey", "links", type_="foreignkey")
    for name in ("tracking_path_prefix", "tracking_base_url", "linkspace_id"):
        op.drop_column("links", name)
    op.drop_table("linkspaces")
