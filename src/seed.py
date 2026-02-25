"""
Seed script -- populates the database with realistic development data.

Run with:
    python src/seed.py

The script is idempotent for categories and products (checks before
inserting) but will add new users and orders on every run. Wipe and
re-apply the migration for a completely fresh state:
    psql $DATABASE_URL -f sql/migrations/0001_init.sql
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from src.db import engine


def seed() -> None:
    with engine.begin() as conn:
        # ------------------------------------------------------------------ #
        # Categories                                                           #
        # ------------------------------------------------------------------ #
        for name in ["Electronics", "Clothing", "Books"]:
            conn.execute(
                text(
                    "INSERT INTO categories (name) VALUES (:name) "
                    "ON CONFLICT (name) DO NOTHING"
                ),
                {"name": name},
            )
        print("  [+] Categories seeded")

        # ------------------------------------------------------------------ #
        # Products, Variants, Inventory                                        #
        # ------------------------------------------------------------------ #
        products_data = [
            {
                "sku": "ELEC-LAPTOP-001",
                "title": "ProBook Laptop 15",
                "description": "15-inch laptop, 16 GB RAM, 512 GB SSD.",
                "category": "Electronics",
                "variants": [
                    {"sku": "ELEC-LAPTOP-001-SLV", "price_cents": 129999,
                     "attributes": {"color": "silver", "storage_gb": 512}, "stock": 25},
                    {"sku": "ELEC-LAPTOP-001-BLK", "price_cents": 134999,
                     "attributes": {"color": "black", "storage_gb": 1024}, "stock": 10},
                ],
            },
            {
                "sku": "ELEC-PHONE-002",
                "title": "SmartPhone X12",
                "description": "Flagship smartphone with 6.7-inch display.",
                "category": "Electronics",
                "variants": [
                    {"sku": "ELEC-PHONE-002-128", "price_cents": 79999,
                     "attributes": {"color": "midnight", "storage_gb": 128}, "stock": 50},
                    {"sku": "ELEC-PHONE-002-256", "price_cents": 89999,
                     "attributes": {"color": "midnight", "storage_gb": 256}, "stock": 30},
                ],
            },
            {
                "sku": "CLO-TSHIRT-001",
                "title": "Classic Cotton T-Shirt",
                "description": "100% organic cotton, unisex fit.",
                "category": "Clothing",
                "variants": [
                    {"sku": "CLO-TSHIRT-001-S-WHT", "price_cents": 2999,
                     "attributes": {"size": "S", "color": "white"}, "stock": 100},
                    {"sku": "CLO-TSHIRT-001-M-WHT", "price_cents": 2999,
                     "attributes": {"size": "M", "color": "white"}, "stock": 150},
                    {"sku": "CLO-TSHIRT-001-L-BLK", "price_cents": 2999,
                     "attributes": {"size": "L", "color": "black"}, "stock": 80},
                ],
            },
            {
                "sku": "BOOK-PYFLASK-001",
                "title": "Flask Web Development",
                "description": "Building web applications with Python and Flask.",
                "category": "Books",
                "variants": [
                    {"sku": "BOOK-PYFLASK-001-PBK", "price_cents": 3999,
                     "attributes": {"format": "paperback"}, "stock": 200},
                    {"sku": "BOOK-PYFLASK-001-EBK", "price_cents": 1999,
                     "attributes": {"format": "ebook"}, "stock": 9999},
                ],
            },
        ]

        import json

        for p in products_data:
            cat_row = conn.execute(
                text("SELECT id FROM categories WHERE name = :name"),
                {"name": p["category"]},
            ).mappings().first()
            cat_id = cat_row["id"]

            conn.execute(
                text(
                    "INSERT INTO products (sku, title, description, category_id) "
                    "VALUES (:sku, :title, :desc, :cat_id) "
                    "ON CONFLICT (sku) DO NOTHING"
                ),
                {"sku": p["sku"], "title": p["title"],
                 "desc": p["description"], "cat_id": cat_id},
            )

            prod_row = conn.execute(
                text("SELECT id FROM products WHERE sku = :sku"),
                {"sku": p["sku"]},
            ).mappings().first()
            prod_id = prod_row["id"]

            for v in p["variants"]:
                conn.execute(
                    text(
                        "INSERT INTO product_variants "
                        "(sku, product_id, price_cents, attributes) "
                        "VALUES (:sku, :pid, :price, :attrs::jsonb) "
                        "ON CONFLICT (sku) DO NOTHING"
                    ),
                    {"sku": v["sku"], "pid": prod_id,
                     "price": v["price_cents"],
                     "attrs": json.dumps(v["attributes"])},
                )

                var_row = conn.execute(
                    text("SELECT id FROM product_variants WHERE sku = :sku"),
                    {"sku": v["sku"]},
                ).mappings().first()
                var_id = var_row["id"]

                conn.execute(
                    text(
                        "INSERT INTO inventory (variant_id, available, reserved) "
                        "VALUES (:vid, :avail, 0) "
                        "ON CONFLICT (variant_id) DO NOTHING"
                    ),
                    {"vid": var_id, "avail": v["stock"]},
                )

            print(f"  [+] Product: {p['title']}")

        # ------------------------------------------------------------------ #
        # Users                                                               #
        # ------------------------------------------------------------------ #
        for email in ["alice@example.com", "bob@example.com"]:
            conn.execute(
                text(
                    "INSERT INTO users (email) VALUES (:email) "
                    "ON CONFLICT (email) DO NOTHING"
                ),
                {"email": email},
            )
        print("  [+] Users seeded (alice, bob)")

        # ------------------------------------------------------------------ #
        # Sample order for Alice                                               #
        # ------------------------------------------------------------------ #
        alice = conn.execute(
            text("SELECT id FROM users WHERE email = 'alice@example.com'")
        ).mappings().first()

        laptop = conn.execute(
            text("SELECT id, price_cents FROM product_variants WHERE sku = 'ELEC-LAPTOP-001-SLV'")
        ).mappings().first()

        book = conn.execute(
            text("SELECT id, price_cents FROM product_variants WHERE sku = 'BOOK-PYFLASK-001-PBK'")
        ).mappings().first()

        if alice and laptop and book:
            total = laptop["price_cents"] * 1 + book["price_cents"] * 2
            order = conn.execute(
                text(
                    "INSERT INTO orders (user_id, status, total_cents, currency) "
                    "VALUES (:uid, 'paid', :total, 'USD') RETURNING id"
                ),
                {"uid": alice["id"], "total": total},
            ).mappings().first()

            conn.execute(
                text(
                    "INSERT INTO order_items "
                    "(order_id, variant_id, unit_price_cents, quantity, subtotal_cents) "
                    "VALUES (:oid, :vid, :price, 1, :price)"
                ),
                {"oid": order["id"], "vid": laptop["id"],
                 "price": laptop["price_cents"]},
            )
            conn.execute(
                text(
                    "INSERT INTO order_items "
                    "(order_id, variant_id, unit_price_cents, quantity, subtotal_cents) "
                    "VALUES (:oid, :vid, :price, 2, :sub)"
                ),
                {"oid": order["id"], "vid": book["id"],
                 "price": book["price_cents"],
                 "sub": book["price_cents"] * 2},
            )
            print(f"  [+] Order for alice: ${total / 100:.2f}")

    print("\nSeed completed successfully.")


if __name__ == "__main__":
    print("Seeding database...")
    seed()
