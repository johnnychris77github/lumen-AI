from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.settings import settings


def _get_db_url() -> str:
    # Try a few likely names on the Settings object
    for attr in ("DATABASE_URL", "DB_URL", "SQLALCHEMY_DATABASE_URI"):
        val = getattr(settings, attr, None)
        if val:
            return val

    # Fallback: local SQLite file inside the container
    return "sqlite:///./lumenai.db"


DATABASE_URL = _get_db_url()

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)

Base = declarative_base()
