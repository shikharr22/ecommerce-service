import logging

from flask import Blueprint, abort, request
from marshmallow import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from db import get_connection
from routes.schemas import CheckoutSchema
from routes.utils import get_current_user_id, success_response

logger = logging.getLogger(__name__)

orders_bp = Blueprint("orders", __name__)

_checkout_schema = CheckoutSchema()


@orders_bp.route("/checkout", methods=["POST"])
def checkout():
    """
    Atomic checkout flow:
      1. Load cart items with a FOR UPDATE lock on inventory rows
      2. Validate cart is not empty and all items have sufficient stock
      3. Decrement inventory.available, increment inventory.reserved
      4. Create order + order_items rows
      5. Clear the cart
    All steps run inside a single transaction — any failure rolls everything back.
    """
    user_id = get_current_user_id()

    body = {}
    if request.is_json and request.content_length:
        try:
            body = _checkout_schema.load(request.get_json(force=True) or {})
        except ValidationError as err:
            abort(400, str(err.messages))

    shipping_address_id = body.get("shipping_address_id")
    billing_address_id = body.get("billing_address_id")
    currency = body.get("currency", "USD")

    try:
        with get_connection() as conn:
            # ----------------------------------------------------------------
            # 1. Lock inventory rows for all items in this user's cart.
            #    SELECT FOR UPDATE prevents another concurrent checkout from
            #    reading the same inventory rows until this transaction commits
            #    or rolls back — eliminating the oversell race condition.
            # ----------------------------------------------------------------
            cart_items = conn.execute(
                text("""
                    SELECT
                        ci.id            AS cart_item_id,
                        ci.variant_id,
                        ci.quantity,
                        v.price_cents,
                        v.sku            AS variant_sku,
                        i.available,
                        i.reserved
                    FROM carts c
                    JOIN cart_items ci ON ci.cart_id = c.id
                    JOIN product_variants v ON v.id = ci.variant_id
                    JOIN inventory i ON i.variant_id = ci.variant_id
                    WHERE c.user_id = :uid
                    ORDER BY ci.variant_id
                    FOR UPDATE OF i
                """),
                {"uid": user_id},
            ).mappings().all()

            # ----------------------------------------------------------------
            # 2. Validate cart
            # ----------------------------------------------------------------
            if not cart_items:
                abort(400, "Cart is empty.")

            # Check each item has enough stock
            for item in cart_items:
                net = item["available"] - item["reserved"]
                if item["quantity"] > net:
                    abort(
                        400,
                        f"Insufficient stock for variant {item['variant_sku']}. "
                        f"Available: {net}, requested: {item['quantity']}.",
                    )

            # ----------------------------------------------------------------
            # 3. Reserve inventory for each item
            # ----------------------------------------------------------------
            for item in cart_items:
                conn.execute(
                    text("""
                        UPDATE inventory
                        SET available     = available - :qty,
                            reserved      = reserved + :qty,
                            last_updated_at = NOW()
                        WHERE variant_id = :vid
                    """),
                    {"qty": item["quantity"], "vid": item["variant_id"]},
                )

            # ----------------------------------------------------------------
            # 4. Create the order
            # ----------------------------------------------------------------
            total_cents = sum(item["quantity"] * item["price_cents"] for item in cart_items)

            order_row = conn.execute(
                text("""
                    INSERT INTO orders (
                        user_id, status, total_cents, currency,
                        shipping_address_id, billing_address_id,
                        created_at, metadata
                    )
                    VALUES (
                        :uid, 'created', :total, :currency,
                        :ship_addr, :bill_addr,
                        NOW(), '{}'::jsonb
                    )
                    RETURNING id
                """),
                {
                    "uid": user_id,
                    "total": total_cents,
                    "currency": currency,
                    "ship_addr": shipping_address_id,
                    "bill_addr": billing_address_id,
                },
            ).mappings().first()

            order_id = int(order_row["id"])

            # ----------------------------------------------------------------
            # 5. Insert order line items
            # ----------------------------------------------------------------
            for item in cart_items:
                subtotal = item["quantity"] * item["price_cents"]
                conn.execute(
                    text("""
                        INSERT INTO order_items (
                            order_id, variant_id, unit_price_cents, quantity, subtotal_cents
                        )
                        VALUES (:oid, :vid, :unit_price, :qty, :subtotal)
                    """),
                    {
                        "oid": order_id,
                        "vid": item["variant_id"],
                        "unit_price": item["price_cents"],
                        "qty": item["quantity"],
                        "subtotal": subtotal,
                    },
                )

            # ----------------------------------------------------------------
            # 6. Clear the cart
            # ----------------------------------------------------------------
            conn.execute(
                text("""
                    DELETE FROM cart_items
                    WHERE cart_id = (SELECT id FROM carts WHERE user_id = :uid)
                """),
                {"uid": user_id},
            )

            conn.commit()

            return success_response(
                {
                    "order_id": order_id,
                    "status": "created",
                    "total_cents": total_cents,
                    "currency": currency,
                    "item_count": len(cart_items),
                },
                "Order placed successfully.",
                201,
            )

    except SQLAlchemyError as e:
        logger.error(f"checkout db error: {e}")
        abort(500, "Database error during checkout.")
    except Exception as e:
        logger.error(f"checkout error: {e}")
        if hasattr(e, "code"):
            raise
        abort(500, "Checkout failed.")


@orders_bp.route("", methods=["GET"])
def list_orders():
    """List the current user's orders, most recent first."""
    user_id = get_current_user_id()

    limit = 20
    after = request.args.get("after")

    try:
        with get_connection() as conn:
            params: dict = {"uid": user_id, "limit": limit}
            sql = """
                SELECT id, status, total_cents, currency, created_at
                FROM orders
                WHERE user_id = :uid
            """
            if after:
                sql += " AND id < :after"
                params["after"] = int(after)
            sql += " ORDER BY created_at DESC LIMIT :limit"

            rows = conn.execute(text(sql), params).mappings().all()

            items = [
                {
                    "order_id": int(r["id"]),
                    "status": r["status"],
                    "total_cents": int(r["total_cents"]),
                    "currency": r["currency"],
                    "created_at": r["created_at"].isoformat(),
                }
                for r in rows
            ]

            has_more = False
            cursor = None
            if len(items) == limit:
                cursor = items[-1]["order_id"]
                next_row = conn.execute(
                    text("SELECT id FROM orders WHERE user_id = :uid AND id < :cursor LIMIT 1"),
                    {"uid": user_id, "cursor": cursor},
                ).mappings().first()
                has_more = next_row is not None

            return success_response(
                {
                    "items": items,
                    "pagination": {"cursor": cursor, "has_more": has_more, "count": len(items)},
                }
            )

    except Exception as e:
        logger.error(f"list_orders error: {e}")
        if hasattr(e, "code"):
            raise
        abort(500, "Failed to fetch orders.")


@orders_bp.route("/<int:order_id>", methods=["GET"])
def get_order(order_id: int):
    """Get a single order with all line items."""
    user_id = get_current_user_id()

    try:
        with get_connection() as conn:
            order = conn.execute(
                text("""
                    SELECT id, status, total_cents, currency, created_at,
                           shipping_address_id, billing_address_id
                    FROM orders
                    WHERE id = :oid AND user_id = :uid
                """),
                {"oid": order_id, "uid": user_id},
            ).mappings().first()

            if not order:
                abort(404, f"Order {order_id} not found.")

            items = conn.execute(
                text("""
                    SELECT
                        oi.id              AS order_item_id,
                        oi.variant_id,
                        oi.unit_price_cents,
                        oi.quantity,
                        oi.subtotal_cents,
                        v.sku              AS variant_sku,
                        v.attributes,
                        p.title            AS product_title,
                        p.sku              AS product_sku
                    FROM order_items oi
                    JOIN product_variants v ON v.id = oi.variant_id
                    JOIN products p ON p.id = v.product_id
                    WHERE oi.order_id = :oid
                    ORDER BY oi.id
                """),
                {"oid": order_id},
            ).mappings().all()

            return success_response(
                {
                    "order_id": int(order["id"]),
                    "status": order["status"],
                    "total_cents": int(order["total_cents"]),
                    "currency": order["currency"],
                    "created_at": order["created_at"].isoformat(),
                    "shipping_address_id": order["shipping_address_id"],
                    "billing_address_id": order["billing_address_id"],
                    "items": [
                        {
                            "order_item_id": int(i["order_item_id"]),
                            "variant_id": int(i["variant_id"]),
                            "variant_sku": i["variant_sku"],
                            "product_title": i["product_title"],
                            "product_sku": i["product_sku"],
                            "attributes": i["attributes"] or {},
                            "unit_price_cents": int(i["unit_price_cents"]),
                            "quantity": i["quantity"],
                            "subtotal_cents": int(i["subtotal_cents"]),
                        }
                        for i in items
                    ],
                }
            )

    except Exception as e:
        logger.error(f"get_order error: {e}")
        if hasattr(e, "code"):
            raise
        abort(500, "Failed to fetch order.")
