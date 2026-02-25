# Ecommerce Service

A REST API backend for an e-commerce platform built with Python, Flask, and PostgreSQL. This project is being built incrementally to learn and practice backend engineering fundamentals and advanced concepts.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.x |
| Framework | Flask 2.3.3 |
| ORM | SQLAlchemy 2.x |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |
| Auth | JWT (`flask-jwt-extended`) |
| Validation | Pydantic 2, Marshmallow |
| Task Queue | Celery |
| Testing | pytest, pytest-flask |
| Containerisation | Docker + Docker Compose |

---

## Project Structure

```
ecommerce-service/
├── sql/
│   └── migrations/         # Raw SQL migration files (0001_init.sql, ...)
├── src/
│   ├── main.py             # Flask app + all routes (products, cart)
│   ├── app.py              # App factory (create_app) + /health endpoint
│   ├── db.py               # DB engine, SessionLocal, Base, get_db()
│   ├── seed.py             # Seed script for development data
│   ├── models/             # SQLAlchemy ORM models
│   │   ├── user.py         # User
│   │   ├── product.py      # Category, Product, ProductVariant, Inventory
│   │   ├── order.py        # Address, Order, OrderItem
│   │   └── cart.py         # Cart, CartItem
│   └── app/                # Modular app package (services, schemas, repos)
│       ├── models/         # ORM models (app-package style)
│       ├── services/       # Business logic layer
│       ├── repositories/   # Data access layer
│       ├── schemas/        # Pydantic/Marshmallow schemas
│       ├── core/           # Config, dependencies, exceptions
│       └── utils/          # Helpers, validators, formatters
├── docker-compose.yml      # PostgreSQL + Redis services
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container definition
├── AGENTS.md               # Guide for AI coding agents
└── .env                    # Local environment variables (gitignored)
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- `psql` (optional, for running migrations manually)

### 1. Clone and set up the environment

```bash
git clone https://github.com/shikharr22/ecommerce-service.git
cd ecommerce-service

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://dev:devpass@localhost:5432/ecommerce_dev
```

### 3. Start the database and Redis

```bash
docker-compose up -d
```

This starts:
- **PostgreSQL 15** on port `5432` — database auto-initialised from `sql/migrations/`
- **Redis 7** on port `6379`

### 4. Apply migrations (if not auto-applied)

```bash
psql $DATABASE_URL -f sql/migrations/0001_init.sql
```

### 5. Seed development data

```bash
python src/seed.py
```

Populates: 3 categories, 4 products with variants and inventory, 2 users (alice, bob), and a sample order.

### 6. Run the development server

```bash
# Via Python
python src/main.py

# Or via Flask CLI
flask --app src/app.py run --debug
```

The API will be available at `http://localhost:5000`.

---

## API Endpoints

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness + DB connectivity check |

### Products

| Method | Path | Description |
|---|---|---|
| GET | `/products` | List products (pagination, filtering, search) |
| GET | `/products/:id` | Get product with variants and inventory |

**Query parameters for `GET /products`:**

| Param | Type | Description |
|---|---|---|
| `limit` | int | Page size (default 20, max 100) |
| `after` | int | Cursor — last product ID from previous page |
| `category_id` | int | Filter by category |
| `q` | string | Search by title (min 2 chars) |
| `min_price_cents` | int | Minimum variant price in cents |
| `max_price_cents` | int | Maximum variant price in cents |
| `has_inventory` | bool | Filter by stock availability |

### Cart

All cart endpoints require the `X-User-Id` header (user ID as an integer).

| Method | Path | Description |
|---|---|---|
| GET | `/carts/me` | Get current user's cart with items |
| POST | `/carts/me/items` | Add an item to the cart |
| PATCH | `/carts/me/items/:id` | Update item quantity (set to 0 to remove) |
| DELETE | `/carts/me/items/:id` | Remove an item from the cart |

**Example — add to cart:**
```bash
curl -X POST http://localhost:5000/carts/me/items \
  -H "Content-Type: application/json" \
  -H "X-User-Id: 1" \
  -d '{"variant_id": 1, "quantity": 2}'
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

Key design decisions:
- All prices stored as **integer cents** (no floats)
- All timestamps stored as **TIMESTAMPTZ** (UTC)
- Order statuses use **CHECK constraints**, not Postgres ENUMs
- Inventory tracks `available` and `reserved` separately
- Hard deletes throughout — no soft deletes

---

## Testing

```bash
# Run all tests
pytest

# Run a single file
pytest tests/test_products.py

# Run a single test
pytest tests/test_products.py::test_get_product_by_id

# With coverage
pytest --cov=src
```

---

## Development Phases

| Phase | Status | Description |
|---|---|---|
| 1 | Done | DB layer, ORM models, app factory, seed data |
| 2 | Planned | Full REST API (products, orders, cart) |
| 3 | Planned | Authentication (JWT + bcrypt) |
| 4 | Planned | Testing (pytest + pytest-flask) |
| 5 | Planned | Advanced concepts (caching, background jobs, pagination, locking) |
