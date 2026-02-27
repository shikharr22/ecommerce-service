import logging

from flask import Blueprint, abort, request
from marshmallow import ValidationError
from sqlalchemy import text

from db import get_connection
from routes.schemas import AddCartItemSchema, UpdateCartItemSchema
from routes.utils import get_current_user_id, success_response

logger = logging.getLogger(__name__)

cart_bp = Blueprint("cart", __name__)

_add_schema = AddCartItemSchema()
_update_schema = UpdateCartItemSchema()


@cart_bp.route("/me", methods=["GET"])
def get_my_cart():
    """Return the current user's cart, creating it if it doesn't exist."""
    user_id = get_current_user_id()

    try:
        with get_connection() as conn:
            # Upsert cart — safe to call every time
            conn.execute(
                text("""
                    INSERT INTO carts (user_id, created_at, updated_at)
                    VALUES (:uid, NOW(), NOW())
                    ON CONFLICT (user_id) DO NOTHING
                """),
                {"uid": user_id},
            )

            rows = conn.execute(
                text("""
                    SELECT
                        c.id            AS cart_id,
                        c.user_id,
                        ci.id           AS cart_item_id,
                        ci.quantity,
                        v.id            AS variant_id,
                        v.sku           AS variant_sku,
                        v.price_cents,
                        v.attributes,
                        p.id            AS product_id,
                        p.sku           AS product_sku,
                        p.title
                    FROM carts c
                    LEFT JOIN cart_items ci ON ci.cart_id = c.id
                    LEFT JOIN product_variants v ON ci.variant_id = v.id
                    LEFT JOIN products p ON v.product_id = p.id
                    WHERE c.user_id = :uid
                    ORDER BY ci.id
                """),
                {"uid": user_id},
            ).mappings().all()

            if not rows:
                abort(500, "Failed to create or fetch cart.")

            first = rows[0]
            items = []
            total_cents = 0

            for r in rows:
                if r["cart_item_id"] is not None:
                    line_total = r["quantity"] * r["price_cents"]
                    total_cents += line_total
                    items.append(
                        {
                            "cart_item_id": int(r["cart_item_id"]),
                            "variant_id": int(r["variant_id"]),
                            "variant_sku": r["variant_sku"],
                            "product_id": int(r["product_id"]),
                            "product_sku": r["product_sku"],
                            "product_title": r["title"],
                            "price_cents": r["price_cents"],
                            "quantity": r["quantity"],
                            "line_total_cents": line_total,
                        }
                    )

            conn.commit()

            return success_response(
                {
                    "cart_id": int(first["cart_id"]),
                    "user_id": user_id,
                    "items": items,
                    "total_items": len(items),
                    "total_quantity": sum(i["quantity"] for i in items),
                    "total_cents": total_cents,
                    "is_empty": len(items) == 0,
                }
            )

    except Exception as e:
        logger.error(f"get_my_cart error: {e}")
        if hasattr(e, "code"):
            raise
        abort(500, "Failed to fetch cart.")


@cart_bp.route("/me/items", methods=["POST"])
def add_cart_item():
    """Add a variant to the cart, or increment quantity if already present."""
    user_id = get_current_user_id()

    if not request.is_json:
        abort(400, "Content-Type must be application/json.")

    try:
        data = _add_schema.load(request.get_json(force=True))
    except ValidationError as err:
        abort(400, str(err.messages))

    variant_id: int = data["variant_id"]
    quantity: int = data["quantity"]

    try:
        with get_connection() as conn:
            # 1. Verify variant exists and has enough stock
            variant = conn.execute(
                text("""
                    SELECT v.id, v.price_cents,
                           COALESCE(i.available, 0) AS available,
                           COALESCE(i.reserved, 0)  AS reserved
                    FROM product_variants v
                    LEFT JOIN inventory i ON i.variant_id = v.id
                    WHERE v.id = :vid
                """),
                {"vid": variant_id},
            ).mappings().first()

            if not variant:
                abort(404, f"Variant {variant_id} not found.")

            net_available = variant["available"] - variant["reserved"]

            # 2. Upsert cart
            conn.execute(
                text("""
                    INSERT INTO carts (user_id, created_at, updated_at)
                    VALUES (:uid, NOW(), NOW())
                    ON CONFLICT (user_id) DO NOTHING
                """),
                {"uid": user_id},
            )
            cart = conn.execute(
                text("SELECT id FROM carts WHERE user_id = :uid"),
                {"uid": user_id},
            ).mappings().first()

            if not cart:
                abort(500, "Failed to resolve cart.")

            cart_id = int(cart["id"])

            # 3. Check if item already in cart — total must not exceed stock or 99
            existing = conn.execute(
                text("SELECT quantity FROM cart_items WHERE cart_id = :cid AND variant_id = :vid"),
                {"cid": cart_id, "vid": variant_id},
            ).mappings().first()

            new_total = quantity + (existing["quantity"] if existing else 0)

            if new_total > 99:
                abort(400, f"Total quantity would exceed 99 (current: {existing['quantity'] if existing else 0}).")
            if new_total > net_available:
                abort(400, f"Insufficient stock. Available: {net_available}, requested total: {new_total}.")

            # 4. Insert or increment
            conn.execute(
                text("""
                    INSERT INTO cart_items (cart_id, variant_id, quantity, created_at, updated_at)
                    VALUES (:cid, :vid, :qty, NOW(), NOW())
                    ON CONFLICT (cart_id, variant_id)
                    DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity,
                                  updated_at = NOW()
                """),
                {"cid": cart_id, "vid": variant_id, "qty": quantity},
            )

            conn.commit()
            return success_response(
                {"cart_id": cart_id, "variant_id": variant_id, "quantity_added": quantity},
                "Item added to cart.",
                201,
            )

    except Exception as e:
        logger.error(f"add_cart_item error: {e}")
        if hasattr(e, "code"):
            raise
        abort(500, "Failed to add item to cart.")


@cart_bp.route("/me/items/<int:cart_item_id>", methods=["PATCH"])
def update_cart_item(cart_item_id: int):
    """Update the quantity of a cart item. Setting quantity to 0 removes it."""
    user_id = get_current_user_id()

    if not request.is_json:
        abort(400, "Content-Type must be application/json.")

    try:
        data = _update_schema.load(request.get_json(force=True))
    except ValidationError as err:
        abort(400, str(err.messages))

    quantity: int = data["quantity"]

    try:
        with get_connection() as conn:
            # Verify ownership and get current inventory in one query
            item = conn.execute(
                text("""
                    SELECT ci.id, ci.variant_id, ci.quantity,
                           COALESCE(i.available, 0) AS available,
                           COALESCE(i.reserved, 0)  AS reserved
                    FROM cart_items ci
                    JOIN carts c ON ci.cart_id = c.id
                    LEFT JOIN inventory i ON i.variant_id = ci.variant_id
                    WHERE ci.id = :item_id AND c.user_id = :uid
                """),
                {"item_id": cart_item_id, "uid": user_id},
            ).mappings().first()

            if not item:
                abort(404, "Cart item not found.")

            if quantity == 0:
                conn.execute(
                    text("DELETE FROM cart_items WHERE id = :item_id"),
                    {"item_id": cart_item_id},
                )
                conn.commit()
                return success_response({"cart_item_id": cart_item_id}, "Item removed from cart.")

            net_available = item["available"] - item["reserved"]
            if quantity > net_available:
                abort(400, f"Insufficient stock. Available: {net_available}, requested: {quantity}.")

            conn.execute(
                text("UPDATE cart_items SET quantity = :qty, updated_at = NOW() WHERE id = :item_id"),
                {"qty": quantity, "item_id": cart_item_id},
            )
            conn.commit()
            return success_response(
                {"cart_item_id": cart_item_id, "new_quantity": quantity},
                "Cart item updated.",
            )

    except Exception as e:
        logger.error(f"update_cart_item error: {e}")
        if hasattr(e, "code"):
            raise
        abort(500, "Failed to update cart item.")


@cart_bp.route("/me/items/<int:cart_item_id>", methods=["DELETE"])
def delete_cart_item(cart_item_id: int):
    """Remove an item from the cart."""
    user_id = get_current_user_id()

    try:
        with get_connection() as conn:
            result = conn.execute(
                text("""
                    DELETE FROM cart_items
                    USING carts c
                    WHERE cart_items.cart_id = c.id
                      AND c.user_id = :uid
                      AND cart_items.id = :item_id
                    RETURNING cart_items.id
                """),
                {"uid": user_id, "item_id": cart_item_id},
            ).mappings().first()

            if not result:
                abort(404, "Cart item not found.")

            conn.commit()
            return success_response({"cart_item_id": cart_item_id}, "Item removed from cart.")

    except Exception as e:
        logger.error(f"delete_cart_item error: {e}")
        if hasattr(e, "code"):
            raise
        abort(500, "Failed to delete cart item.")
