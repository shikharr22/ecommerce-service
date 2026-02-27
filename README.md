# ecommerce-service

A backend REST API for an e-commerce platform, built with Python and Flask on top of PostgreSQL.

This is a deliberate, phase-by-phase learning project. The goal is not just to ship working endpoints — it's to understand *why* each pattern exists, where it breaks down, and what the production trade-offs are. Every design decision here has a reason behind it.

---

## What I'm Practising

This project is structured around concepts I'm actively working to understand deeply, not just use.

**Phase 1 — Foundation (complete)**
- **Connection pooling** — why opening a DB connection on every request is expensive, and how `pool_size` / `max_overflow` control behaviour under load
- **ORM vs raw SQL** — both are used deliberately. SQLAlchemy ORM for models and relationships; raw SQL via `engine.connect()` for complex queries where the ORM would obscure what's actually hitting the database
- **Application factory pattern** — `create_app()` instead of a module-level `app` singleton, so the app can be instantiated multiple times with different configs (critical for testing and avoiding circular imports)
- **DB-level constraints as a safety net** — `CHECK (price_cents >= 0)`, `CHECK (available >= 0)`, `ON DELETE CASCADE` enforced in Postgres, not just in application code. Application validation is the first line; the DB is the last.
- **Integer cents for money** — floats cannot represent all decimals exactly. `1999` means $19.99. No rounding errors, ever.
- **TIMESTAMPTZ everywhere** — all timestamps stored in UTC, timezone-aware in Python. Naive datetimes are a silent bug waiting to happen.
- **CHECK constraints over Postgres ENUMs** — adding a new order status is one `ALTER TABLE`, not `ALTER TYPE` + `ALTER TABLE`. Simpler to migrate.
- **Idempotent seed data** — `ON CONFLICT DO NOTHING` means the seed script is safe to run repeatedly. Matters in development where you reset the DB often.
- **Cascade design choices** — `ON DELETE CASCADE` for owned data (variants, cart items), `ON DELETE SET NULL` for referenced data (address → user) to preserve order history.

**Phase 2 — REST API layer (complete)**
- **Flask Blueprints** — routes split into three domain blueprints (`products_bp`, `cart_bp`, `orders_bp`), all mounted under `/api/v1/`. Keeps route files focused and makes the app easier to navigate as it grows.
- **Atomic checkout transaction** — `SELECT FOR UPDATE` on inventory rows → validate stock → decrement `available` + increment `reserved` → create order + order items → clear cart, all in one DB transaction. Any failure rolls back everything; no partial state is persisted.
- **`SELECT FOR UPDATE` / pessimistic locking** — used in checkout to prevent inventory oversell under concurrent requests. Two users checking out the last item at the same time: only one succeeds.
- **Cursor-based (keyset) pagination** — both `/products` and `/orders` paginate using `id > :after` rather than `LIMIT/OFFSET`. `OFFSET 1000` requires the DB to scan and discard 1000 rows every time; keyset skips directly to the right row via an index.
- **Request validation with Marshmallow** — `AddCartItemSchema`, `UpdateCartItemSchema`, and `CheckoutSchema` validate and coerce input before it reaches business logic. Consistent `{ error: "..." }` shape on validation failure.
- **Consistent response envelope** — all endpoints return `{ success, data, timestamp }` on success and `{ success: false, error: "..." }` on failure, enforced by global error handlers and a shared `success_response()` helper.
- **Scaffolded layered architecture** (`src/app/`) — repository pattern, Pydantic v2 schemas, typed config dataclasses, and a rich custom exception hierarchy are committed as a planned refactor target, not yet wired into the running app.

**Phase 3 — Authentication**
- JWT access + refresh token flow
- bcrypt password hashing and why iteration count matters
- `@login_required` decorator pattern

**Phase 4 — Testing**
- pytest + pytest-flask integration tests against a real test database
- Factory Boy for fixture generation
- Testing transactions and rollback behaviour

**Phase 5 — Advanced**
- Redis caching — cache-aside pattern, TTL strategy, cache invalidation
- Celery background tasks — async order confirmation emails, inventory sync
- Rate limiting
- Alembic for schema migrations (graduating from raw SQL files)
- Structured logging and Prometheus metrics

---

## Tech Stack

| Layer | Technology | Status |
|---|---|---|
| Language | Python 3.x | Active |
| Framework | Flask 2.3.3 | Active |
| ORM | SQLAlchemy 2.x | Active |
| Database | PostgreSQL 15 | Active |
| Validation | Marshmallow (active), Pydantic 2 (scaffolded) | Active |
| Auth | JWT (`flask-jwt-extended`), bcrypt | Phase 3 |
| Cache | Redis 7 | Phase 5 |
| Task Queue | Celery | Phase 5 |
| Migrations | Alembic | Phase 5 |
| Testing | pytest, pytest-flask, factory-boy | Phase 4 |
| Containerisation | Docker + Docker Compose | Active |

---

## Project Structure

```
ecommerce-service/
├── sql/
│   └── migrations/         # Raw SQL files, numbered sequentially
├── src/
│   ├── app.py              # create_app() factory — registers blueprints, global error handlers
│   ├── main.py             # Legacy flat-file app (Phase 1 style, kept for reference)
│   ├── db.py               # Engine, SessionLocal, Base, get_db(), get_connection()
│   ├── seed.py             # Idempotent dev seed data
│   ├── models/             # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── product.py      # Category, Product, ProductVariant, Inventory
│   │   ├── order.py        # Address, Order, OrderItem
│   │   └── cart.py         # Cart, CartItem
│   ├── routes/             # Flask Blueprints (Phase 2)
│   │   ├── products.py     # GET /api/v1/products, GET /api/v1/products/<id>
│   │   ├── cart.py         # Cart CRUD under /api/v1/carts
│   │   ├── orders.py       # Checkout + order retrieval under /api/v1/orders
│   │   ├── schemas.py      # Marshmallow request validation schemas
│   │   └── utils.py        # success_response(), parse_int(), get_current_user_id()
│   └── app/                # Scaffolded layered architecture (not yet wired in)
│       ├── core/           # Typed config dataclasses, custom exception hierarchy
│       ├── models/         # ORM models mirrored for the future service layer
│       ├── repositories/   # Repository pattern (BaseRepository, CartRepository)
│       ├── schemas/        # Pydantic v2 request/response models
│       ├── services/       # Business logic (CartService, ProductService)
│       └── utils/          # Date, formatting, validation helpers
├── docker-compose.yml      # PostgreSQL 15 + Redis 7
├── requirements.txt
└── AGENTS.md               # Guide for AI coding agents working in this repo
```

---

## Database Schema

Nine tables across four domains:

```
users
categories → products → product_variants → inventory
addresses
orders → order_items
carts → cart_items
```

---

## Getting Started

```bash
# 1. Clone and set up environment
git clone https://github.com/shikharr22/ecommerce-service.git
cd ecommerce-service
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt

# 2. Create .env
echo DATABASE_URL=postgresql://dev:devpass@localhost:5432/ecommerce_dev > .env

# 3. Start Postgres + Redis
docker-compose up -d

# 4. Apply schema
psql $DATABASE_URL -f sql/migrations/0001_init.sql

# 5. Seed data
python src/seed.py

# 6. Run
flask --app src/app.py run --debug
```

---

## Current Endpoints

All API endpoints are mounted under `/api/v1/`. The `/health` endpoint is at the root.

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness + DB connectivity check |
| GET | `/api/v1/products` | List products — cursor-based pagination, filter by `category_id`, `q` (search), `min_price_cents`, `max_price_cents`, `has_inventory`, `after` (cursor) |
| GET | `/api/v1/products/<id>` | Product detail with all variants, inventory, `min/max_price_cents`, `in_stock` |
| GET | `/api/v1/carts/me` | Current user's cart (auto-created if missing), with full line items and totals |
| POST | `/api/v1/carts/me/items` | Add item to cart (upsert); validates stock and 99-item-per-line cap |
| PATCH | `/api/v1/carts/me/items/<id>` | Update item quantity (`quantity=0` removes the item) |
| DELETE | `/api/v1/carts/me/items/<id>` | Remove item from cart |
| POST | `/api/v1/orders/checkout` | Atomic checkout — reserves inventory and creates order in one transaction |
| GET | `/api/v1/orders` | List current user's orders, most-recent-first, cursor paginated |
| GET | `/api/v1/orders/<id>` | Single order with full line items including variant and product details |

All endpoints (except `/health`) require an `X-User-Id: <integer>` header for user identity.

---

## A Note on Tooling

I used [OpenCode](https://opencode.ai) as an AI pair programmer throughout this project. It helped me implement, debug, and — more importantly — understand the *why* behind each pattern. The goal was never to copy-paste generated code, but to use it as a knowledgeable collaborator to learn faster and go deeper than I would reading docs alone.
