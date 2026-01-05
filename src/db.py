import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine



load_dotenv()

raw = os.getenv("DATABASE_URL") or "postgresql://dev:devpass@localhost:5432/ecommerce_dev"

# Normalize common shorthand 'postgres://' → 'postgresql+psycopg2://'
if raw.startswith("postgres://"):
    DATABASE_URL = raw.replace("postgres://", "postgresql+psycopg2://", 1)
else:
    DATABASE_URL = raw




# Engine configuration notes:
# - pool_size: number of persistent connections to keep (small for local dev)
# - max_overflow: how many extra connections can be opened temporarily
# - pool_timeout: seconds to wait when pool is exhausted
# - future=True: use SQLAlchemy 2.0 style Result APIs
# - echo: set True to print all SQL to stdout (useful for learning)
engine:Engine=create_engine(DATABASE_URL,
    echo=False,         # set True while debugging to see SQL statements
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    future=True,)

def get_connection():
    """
    Returns a Connection that can be used as a context manager.

    Usage:
        with get_connection() as conn:
            res = conn.execute(text("SELECT 1"))
            ...
            
    """
    
    return engine.connect()

def test_simple_query():
    with get_connection() as conn:
        row=conn.execute(text("SELECT now() as now")).mappings().first()
        return dict(row) if row else None