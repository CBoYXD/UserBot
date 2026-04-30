from __future__ import annotations

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.db.base import Base  # noqa: F401
import src.db.models  # noqa: F401 – register all models with Base


def make_engine(db_path: str) -> AsyncEngine:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    url = f'sqlite+aiosqlite:///{db_path}'
    engine = create_async_engine(url, echo=False)

    @event.listens_for(engine.sync_engine, 'connect')
    def _set_pragmas(conn, _record):
        cur = conn.cursor()
        cur.execute('pragma journal_mode=wal')
        cur.execute('pragma foreign_keys=on')
        cur.execute('pragma synchronous=normal')
        cur.close()

    return engine


def make_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
