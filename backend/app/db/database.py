from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings


def _build_mysql_url() -> str:
    return (
        f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
        f"@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_db}?charset=utf8mb4"
    )


class Database:
    def __init__(self) -> None:
        self.engine: Engine = create_engine(
            _build_mysql_url(),
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )

    @contextmanager
    def connect(self):
        with self.engine.connect() as conn:
            yield conn

    def execute(self, sql: str, params: Optional[Dict[str, Any]] = None) -> int:
        with self.connect() as conn:
            result = conn.execute(text(sql), params or {})
            conn.commit()
            return int(result.rowcount)

    def fetch_one(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            result = conn.execute(text(sql), params or {})
            row = result.mappings().first()
            return dict(row) if row else None

    def fetch_all(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            result = conn.execute(text(sql), params or {})
            rows = result.mappings().all()
            return [dict(r) for r in rows]

    def fetch_value(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Any:
        with self.connect() as conn:
            result = conn.execute(text(sql), params or {})
            row = result.first()
            if row is None:
                return None
            return row[0]


_db = Database()


def db() -> Database:
    return _db


__all__ = ["db", "Database"]
