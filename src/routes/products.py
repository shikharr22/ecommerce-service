import logging
from typing import Optional

from flask import Blueprint, abort, request
from sqlalchemy import text

from db import get_connection
from routes.utils import parse_bool, parse_int, success_response

logger = logging.getLogger(__name__)

products_bp = Blueprint("products", __name__)


@products_bp.route("", methods=["GET"])
def list_products():
    """List products with cursor-based pagination, filtering, and search."""
    limit = parse_int(request.args.get("limit"), default=20, min_val=1, max_val=100, field_name="limit")
    after = parse_int(request.args.get("after"), default=None, min_val=1, field_name="after")
    category_id = parse_int(request.args.get("category_id"), default=None, min_val=1, field_name="category_id")

    search_query = request.args.get("q", "").strip()
    if search_query and len(search_query) < 2:
        abort(400, "Search query must be at least 2 characters.")
    if search_query and len(search_query) > 100:
        abort(400, "Search query cannot exceed 100 characters.")

    min_price_cents = parse_int(request.args.get("min_price_cents"), default=None, min_val=0, field_name="min_price_cents")
    max_price_cents = parse_int(request.args.get("max_price_cents"), default=None, min_val=0, field_name="max_price_cents")

    if min_price_cents is not None and max_price_cents is not None and min_price_cents > max_price_cents:
        abort(400, "min_price_cents cannot be greater than max_price_cents.")

    has_inventory_raw = request.args.get("has_inventory")
    has_inventory: Optional[bool] = parse_bool(has_inventory_raw) if has_inventory_raw is not None else None

    sql = """
        SELECT
            p.id          AS product_id,
            p.sku         AS product_sku,
            p.title,
            p.category_id,
            MIN(v.price_cents)                          AS min_price_cents,
            COUNT(v.id)                                 AS variant_count,
            COALESCE(SUM(i.available - i.reserved), 0)  AS total_available
        FROM products p
        LEFT JOIN product_variants v ON v.product_id = p.id
        LEFT JOIN inventory i ON i.variant_id = v.id
        WHERE 1=1
    """

    params: dict = {}

    if after is not None:
        sql += " AND p.id > :after"
        params["after"] = after
    if category_id is not None:
        sql += " AND p.category_id = :category_id"
        params["category_id"] = category_id
    if search_query:
        sql += " AND p.title ILIKE :q"
        params["q"] = f"%{search_query}%"

    sql += " GROUP BY p.id, p.sku, p.title, p.category_id"

    having_clauses = []
    if min_price_cents is not None:
        having_clauses.append("MIN(v.price_cents) >= :min_price_cents")
        params["min_price_cents"] = min_price_cents
    if max_price_cents is not None:
        having_clauses.append("MIN(v.price_cents) <= :max_price_cents")
        params["max_price_cents"] = max_price_cents
    if has_inventory is True:
        having_clauses.append("COALESCE(SUM(i.available - i.reserved), 0) > 0")
    elif has_inventory is False:
        having_clauses.append("COALESCE(SUM(i.available - i.reserved), 0) = 0")

    if having_clauses:
        sql += " HAVING " + " AND ".join(having_clauses)

    sql += " ORDER BY p.id LIMIT :limit"
    params["limit"] = limit

    try:
        with get_connection() as conn:
            rows = conn.execute(text(sql), params).mappings().all()

            # Cursor pagination: check if more rows exist after this page
            has_more = False
            cursor = None
            if len(rows) == limit:
                next_id = rows[-1]["product_id"]
                check_params = {**params, "after": next_id}
                # Replace the after clause or add it
                check_sql = sql.replace(" ORDER BY p.id LIMIT :limit", " AND p.id > :after ORDER BY p.id LIMIT 1")
                if "AND p.id > :after" in sql:
                    # already has an after clause, rebuild cleanly
                    pass
                next_row = conn.execute(
                    text(
                        sql.replace("LIMIT :limit", "LIMIT 1 OFFSET :offset")
                    ),
                    {**params, "offset": limit},
                ).mappings().first()
                if next_row:
                    has_more = True
                    cursor = int(rows[-1]["product_id"])

            items = [
                {
                    "product_id": int(r["product_id"]),
                    "product_sku": r["product_sku"],
                    "title": r["title"],
                    "category_id": r["category_id"],
                    "min_price_cents": int(r["min_price_cents"]) if r["min_price_cents"] is not None else None,
                    "variant_count": int(r["variant_count"]),
                    "total_available": int(r["total_available"]),
                    "in_stock": int(r["total_available"]) > 0,
                }
                for r in rows
            ]

            return success_response(
                {
                    "items": items,
                    "pagination": {
                        "cursor": cursor,
                        "has_more": has_more,
                        "count": len(items),
                        "limit": limit,
                    },
                }
            )
    except Exception as e:
        logger.error(f"list_products error: {e}")
        if hasattr(e, "code"):
            raise
        abort(500, "Failed to fetch products.")


@products_bp.route("/<int:product_id>", methods=["GET"])
def get_product(product_id: int):
    """Get a single product with all variants and inventory."""
    if product_id <= 0:
        abort(400, "Product ID must be a positive integer.")

    sql = text("""
        SELECT
            p.id,
            p.sku,
            p.title,
            p.description,
            p.category_id,
            p.created_at,
            v.id            AS variant_id,
            v.sku           AS variant_sku,
            v.price_cents,
            v.attributes,
            COALESCE(i.available, 0) AS available,
            COALESCE(i.reserved, 0)  AS reserved
        FROM products p
        LEFT JOIN product_variants v ON v.product_id = p.id
        LEFT JOIN inventory i ON i.variant_id = v.id
        WHERE p.id = :pid
        ORDER BY v.id
    """)

    try:
        with get_connection() as conn:
            rows = conn.execute(sql, {"pid": product_id}).mappings().all()

        if not rows:
            abort(404, f"Product {product_id} not found.")

        first = rows[0]
        product = {
            "id": first["id"],
            "sku": first["sku"],
            "title": first["title"],
            "description": first["description"],
            "category_id": first["category_id"],
            "created_at": first["created_at"].isoformat() if first["created_at"] else None,
            "variants": [],
        }

        for r in rows:
            if r["variant_id"] is not None:
                net = r["available"] - r["reserved"]
                product["variants"].append(
                    {
                        "id": r["variant_id"],
                        "sku": r["variant_sku"],
                        "price_cents": r["price_cents"],
                        "attributes": r["attributes"] or {},
                        "available": r["available"],
                        "reserved": r["reserved"],
                        "in_stock": net > 0,
                    }
                )

        if product["variants"]:
            product["min_price_cents"] = min(v["price_cents"] for v in product["variants"])
            product["max_price_cents"] = max(v["price_cents"] for v in product["variants"])
            product["total_available"] = sum(
                max(0, v["available"] - v["reserved"]) for v in product["variants"]
            )
            product["in_stock"] = product["total_available"] > 0
        else:
            product.update({"min_price_cents": None, "max_price_cents": None,
                            "total_available": 0, "in_stock": False})

        return success_response(product)

    except Exception as e:
        logger.error(f"get_product error: {e}")
        if hasattr(e, "code"):
            raise
        abort(500, "Failed to fetch product.")
