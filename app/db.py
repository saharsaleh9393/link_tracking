from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings


@lru_cache
def get_engine():
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=1,
        connect_args={
            "connect_timeout": 2,
            "options": f"-c timezone=UTC -c statement_timeout={settings.db_statement_timeout_ms}",
        },
        hide_parameters=True,
    )


def session_dependency():
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session
