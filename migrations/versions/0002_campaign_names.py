"""Enforce case-insensitive campaign names without deleting or renaming legacy data."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TRIM = " \t\n\r\v\f\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"


def upgrade():
    connection = op.get_bind()
    # Block concurrent writes while inspecting existing names and creating the index.
    connection.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
    connection.execute(sa.text("LOCK TABLE campaigns IN SHARE ROW EXCLUSIVE MODE"))
    duplicate = connection.scalar(
        sa.text("""
        SELECT count(*) FROM (
            SELECT lower(btrim(name, :trim)) FROM campaigns
            GROUP BY lower(btrim(name, :trim)) HAVING count(*) > 1
        ) duplicates
    """),
        {"trim": TRIM},
    )
    empty = connection.scalar(
        sa.text("SELECT count(*) FROM campaigns WHERE btrim(name, :trim) = ''"), {"trim": TRIM}
    )
    if duplicate or empty:
        raise RuntimeError(
            "Campaign-name migration stopped: existing duplicate or empty names. "
            "No data was changed. Review and rename the conflicting campaigns explicitly, then rerun."
        )
    op.create_index(
        "uq_campaigns_normalized_name",
        "campaigns",
        [sa.func.lower(sa.func.btrim(sa.column("name"), TRIM))],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_campaigns_normalized_name", table_name="campaigns")
