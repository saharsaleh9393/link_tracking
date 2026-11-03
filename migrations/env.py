from alembic import context
from sqlalchemy import text

from app.db import get_engine
from app.models import Base


def run():
    with get_engine().connect() as connection:
        partitions = set(
            connection.scalars(
                text("""
            SELECT child.relname FROM pg_inherits i
            JOIN pg_class child ON child.oid=i.inhrelid
            JOIN pg_class parent ON parent.oid=i.inhparent
            WHERE parent.relname='click_events'
        """)
            ).all()
        )
        # Introspection above opens a transaction; finish it before Alembic owns migrations.
        connection.rollback()
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            compare_type=True,
            include_name=lambda name, type_, parent_names: (
                not (type_ == "table" and name in partitions)
            ),
        )
        with context.begin_transaction():
            context.run_migrations()


run()
