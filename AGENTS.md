# AGENTS.md — Ecommerce Service

This document provides guidance for agentic coding agents working in this repository.

---

## Project Overview

A Python/Flask REST API backend for an e-commerce platform backed by PostgreSQL 15.

| Attribute        | Value                                  |
|------------------|----------------------------------------|
| Language         | Python 3.x                             |
| Framework        | Flask 2.3.3                            |
| ORM              | SQLAlchemy 1.4.x (legacy/1.x style)    |
| Database         | PostgreSQL 15                          |
| DB Adapter       | psycopg2-binary                        |
| Env management   | python-dotenv                          |
| Package manager  | pip (`requirements.txt`)               |
| Source root      | `src/`                                 |
| Migrations dir   | `sql/migrations/`                      |

---

## Environment Setup

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Start the database (requires Docker)
docker-compose up -d
```

The `.env` file must define `DATABASE_URL`:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ecommerce_dev
```

---

## Build / Run Commands

```bash
# Run the Flask development server (legacy entry point)
python src/main.py

# Or via Flask CLI
flask --app src/app.py run --debug
```

---

## Database Migrations

Migrations are raw SQL files in `sql/migrations/`, numbered with a 4-digit prefix:

```
sql/migrations/0001_init.sql
sql/migrations/0002_<description>.sql
```

Apply a migration:
```bash
psql $DATABASE_URL -f sql/migrations/0001_init.sql
```

Never modify existing migration files. Always add a new numbered file for schema changes.

---

## Seed Data

```bash
python src/seed.py
```

Populates categories, products, variants, inventory, users, and a sample order.
Idempotent — safe to run multiple times.

---

## Testing

No test framework is configured yet. When adding tests, use **pytest**:

```bash
pip install pytest pytest-flask

# Run all tests
pytest

# Run a single test file
pytest tests/test_orders.py

# Run a single test function
pytest tests/test_orders.py::test_create_order

# Run with verbose output
pytest -v
```

Place tests in a `tests/` directory at the project root.
Name test files `test_<module>.py` and test functions `test_<behavior>`.

---

## Code Style Guidelines

### General

- All code is **Python 3.x**. Do not write Python 2-compatible code.
- Use **4 spaces** for indentation (never tabs).
- Maximum line length: **88 characters** (Black default).

### Imports

Order imports in three groups separated by blank lines:
1. Standard library
2. Third-party packages
3. Local/project modules

```python
import os
from typing import Optional

from flask import Flask, jsonify, request
from sqlalchemy.orm import Session

from src.db import engine
```

### Naming Conventions

| Construct          | Convention             | Example                    |
|--------------------|------------------------|----------------------------|
| Variables          | `snake_case`           | `order_total`              |
| Functions          | `snake_case`           | `get_order_by_id()`        |
| Classes            | `PascalCase`           | `OrderService`             |
| Constants          | `SCREAMING_SNAKE_CASE` | `DATABASE_URL`             |
| Modules/files      | `snake_case`           | `order_service.py`         |
| SQLAlchemy models  | `PascalCase`           | `class Order(Base)`        |
| SQL tables/columns | `snake_case`           | `order_items`, `unit_price_cents` |

### Types

- Add **type annotations** to all new function signatures.
- Use `Optional[X]` for nullable values.

### Money / Pricing

- All monetary values are stored and passed as **integer cents** (`price_cents: int`).
- Never use `float` for money.
- Currency defaults to `"USD"` unless specified.

### Timestamps

- All timestamps use `TIMESTAMPTZ` in the database (UTC-stored).
- In Python, use timezone-aware datetimes: `datetime.now(timezone.utc)`.

### Error Handling

- Use Flask's `abort()` for HTTP errors with appropriate status codes.
- Return JSON error bodies with a consistent shape:
  ```json
  { "error": "Human-readable message" }
  ```
- Catch specific exceptions rather than bare `except Exception`.
- Always rollback on database errors:
  ```python
  try:
      db.session.commit()
  except Exception:
      db.session.rollback()
      raise
  ```

### Database

- Use `src/db.py` for all database access:
  - `engine` — raw SQLAlchemy engine (connection pool)
  - `get_connection()` — raw SQL via context manager
  - `SessionLocal` / `get_db()` — ORM session per request
  - `Base` — declarative base for ORM models
- ORM models live in `src/models/`.
- Raw SQL routes live in `src/main.py` using `get_connection()`.
- Never hardcode credentials — always read from `DATABASE_URL` env var.

### Flask Routes

- Keep route handlers thin — delegate logic to service functions.
- Return `jsonify(...)` for all JSON responses with explicit HTTP status codes.
- Use `X-User-Id` header for user identity (until auth is implemented in Phase 3).

---

## Project Conventions

- **Soft deletes are not used.** Deletes are hard with `ON DELETE CASCADE` or `SET NULL`.
- **Status fields** use `CHECK` constraints, not Postgres `ENUM` types.
- **Inventory**: `available` must never go below 0. During checkout: decrement
  `available`, increment `reserved`; reverse on failure.
- **SKUs** are unique across their tables.
- The `nul` file in the project root is a Windows artifact — ignore it.
