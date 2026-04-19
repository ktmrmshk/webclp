import threading

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_init_lock = threading.Lock()
_db_initialized = False


def _migrate_sqlite_deleted_at() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    insp = inspect(engine)
    if not insp.has_table("clips"):
        return
    cols = {c["name"] for c in insp.get_columns("clips")}
    if "deleted_at" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE clips ADD COLUMN deleted_at DATETIME"))


def _migrate_sqlite_body_markdown() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    insp = inspect(engine)
    if not insp.has_table("clips"):
        return
    cols = {c["name"] for c in insp.get_columns("clips")}
    if "body_markdown" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE clips ADD COLUMN body_markdown TEXT NOT NULL DEFAULT ''"))


def init_db() -> None:
    """テーブル作成と SQLite マイグレーション。複数回呼んでも安全（初回のみ実処理）。"""
    global _db_initialized
    if _db_initialized:
        return
    with _init_lock:
        if _db_initialized:
            return
        from app import models  # noqa: F401

        Base.metadata.create_all(bind=engine)
        _migrate_sqlite_deleted_at()
        _migrate_sqlite_body_markdown()
        _db_initialized = True


def get_db():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
