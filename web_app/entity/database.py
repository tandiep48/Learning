"""
entity/database.py
------------------
Shared SQLAlchemy engine, declarative Base, and session factory.

This module is intentionally kept separate from the existing psycopg2-based
db.py so that both layers can coexist without interference.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

load_dotenv()

# ---------------------------------------------------------------------------
# Build the connection URL from the same .env vars used by db.py
# ---------------------------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "chinese")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "admin")

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# The app serves websockets under `gunicorn -k eventlet`: one OS thread runs many
# cooperative greenlets. A shared, capped QueuePool (pool_size/max_overflow) is a
# trap there — a greenlet blocked in psycopg2 holds a pooled connection without
# yielding, so under load the pool starves and every request times out (504).
#
# NullPool opens and closes a real connection per checkout (like the former
# psycopg2-per-request model): no shared cap to starve, no connections pinned
# across greenlets. Combined with the psycogreen patch in app.py (which makes
# psycopg2 yield to the eventlet hub), DB calls no longer freeze the worker.
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    echo=False,           # set True during development to log SQL
)

# ---------------------------------------------------------------------------
# Base class for all ORM models
# ---------------------------------------------------------------------------
Base = declarative_base()

# ---------------------------------------------------------------------------
# Session factory
# scoped_session ties the session to the current thread / greenlet so that
# Flask routes never share a session accidentally.
# ---------------------------------------------------------------------------
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)


def get_session():
    """
    Yield a SQLAlchemy session and close it when done.

    Usage (in repository methods):
        with get_session() as session:
            ...
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        SessionLocal.remove()
