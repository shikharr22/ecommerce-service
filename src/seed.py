from db import get_connection
from sqlalchemy import text
import json

def seed():
    with get_connection() as conn:
        # categories
        conn.execute(text("INSERT INTO categories (name) VALUES (:name) ON CONFLICT DO NOTHING"),
                     {"name": "Misc"})

        # products 6..25
        for g in range(6, 26):
            sku = f"P-{g:03d}"
            conn.execute(text("""
                INSERT INTO products (sku, title, description, category_id, created_at)
                VALUES (:sku, :title, :desc, (SELECT id FROM categories WHERE name='Misc' LIMIT 1), now())
                ON CONFLICT (sku) DO NOTHING
            """), {"sku": sku, "title": f"Product {g}", "desc": f"Auto-seeded product {g}"})

        # variants 1..3 per product
        products = conn.execute(text("SELECT id, sku FROM products WHERE sku LIKE 'P-%'")).all()
        for pid, sku in products:
            for vnum in range(1, 4):
                vsku = f"{sku}-V{vnum}"
                price = 1000 + (pid * 50) + (vnum * 10)
                attributes = {"color": ["red", "blue", "green", "black"][vnum % 4], "size": ["S", "M", "L"][min(vnum-1,2)]}
                conn.execute(text("""
                    INSERT INTO product_variants (sku, product_id, price_cents, attributes, created_at)
                    VALUES (:vsku, :pid, :price, :attrs::jsonb, now())
                    ON CONFLICT (sku) DO NOTHING
                """), {"vsku": vsku, "pid": pid, "price": price, "attrs": json.dumps(attributes)})

        # inventory for variants
        variants = conn.execute(text("SELECT id, sku FROM product_variants WHERE sku LIKE 'P-%'")).all()
        for vid, vsku in variants:
            # simple deterministic available based on sku hash
            avail = (abs(hash(vsku)) % 100)
            conn.execute(text("""
                INSERT INTO inventory (variant_id, available, reserved, last_updated_at)
                VALUES (:vid, :avail, 0, now())
                ON CONFLICT (variant_id) DO UPDATE SET available = EXCLUDED.available
            """), {"vid": vid, "avail": avail})

        # users
        users = [
            ("user1@example.com","hashed-pass-1"),
            ("user2@example.com","hashed-pass-2"),
            ("user3@example.com","hashed-pass-3")
        ]
        for email, pwd in users:
            conn.execute(text("INSERT INTO users (email, hashed_password) VALUES (:email,:pwd) ON CONFLICT (email) DO NOTHING"),
                         {"email":email, "pwd":pwd})

        conn.commit()
        print("seed_more: done")

if __name__ == "__main__":
    seed()