import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

raw = os.getenv("DATABASE_URL") or "postgresql://postgres:postgres@localhost:5432/ecommerce_dev"

# Normalize shorthand 'postgres://' -> 'postgresql://' (required by SQLAlchemy 1.4+)
if raw.startswith("postgres://"):
    DATABASE_URL = raw.replace("postgres://", "postgresql://", 1)
else:
    DATABASE_URL = raw

# Engine manages the connection pool.
# pool_size: persistent connections to keep open
# max_overflow: extra connections allowed under peak load
# echo: set True to print all generated SQL (useful while learning)
engine: Engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
)

# SessionLocal is a factory for ORM sessions (one per request).
# autocommit=False -> we control commits explicitly
# autoflush=False  -> no automatic flush before queries
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Base is the declarative base all ORM models inherit from.
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Yields a database session and guarantees cleanup via try/finally.
    The session is closed (connection returned to pool) after every request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_connection():
    """
    Returns a raw SQLAlchemy Connection as a context manager.

    Usage:
        with get_connection() as conn:
            conn.execute(text("SELECT 1"))
    """
    return engine.connect()


def test_simple_query():
    with get_connection() as conn:
        row = conn.execute(text("SELECT now() as now")).mappings().first()
        return dict(row) if row else None