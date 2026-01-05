from flask import Flask, jsonify, abort, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from db import get_connection
from datetime import datetime
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Error handlers for consistent API responses
@app.errorhandler(400)
def handle_bad_request(error):
    logger.warning(f"Bad request: {error.description}")
    return jsonify({
        "success": False,
        "error": {
            "code": "BAD_REQUEST",
            "message": str(error.description)
        },
        "timestamp": datetime.utcnow().isoformat()
    }), 400

@app.errorhandler(404)
def handle_not_found(error):
    logger.info(f"Not found: {error.description}")
    return jsonify({
        "success": False,
        "error": {
            "code": "NOT_FOUND", 
            "message": str(error.description)
        },
        "timestamp": datetime.utcnow().isoformat()
    }), 404

@app.errorhandler(500)
def handle_internal_error(error):
    logger.error(f"Internal error: {error}\n{traceback.format_exc()}")
    return jsonify({
        "success": False,
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An internal server error occurred"
        },
        "timestamp": datetime.utcnow().isoformat()
    }), 500

@app.errorhandler(SQLAlchemyError)
def handle_database_error(error):
    logger.error(f"Database error: {error}\n{traceback.format_exc()}")
    return jsonify({
        "success": False,
        "error": {
            "code": "DATABASE_ERROR",
            "message": "A database error occurred"
        },
        "timestamp": datetime.utcnow().isoformat()
    }), 500

# Response utility for consistent success responses
def success_response(data, message=None, status=200):
    response = {
        "success": True,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    if message:
        response["message"] = message
    
    # Add request ID if available
    request_id = getattr(request, 'id', None)
    if request_id:
        response["request_id"] = request_id
        
    return jsonify(response), status

# Generate unique request ID for tracking
@app.before_request
def generate_request_id():
    import uuid
    request.id = str(uuid.uuid4())[:8]  # Short ID for logging

# Input validation decorator with enhanced error handling
def validate_json_request(required_fields=None, max_size_mb=1):
    def decorator(f):
        def wrapper(*args, **kwargs):
            # Check content type
            if not request.is_json:
                abort(400, "Request must have Content-Type: application/json")
            
            # Check content length (prevent large payloads)
            if request.content_length and request.content_length > max_size_mb * 1024 * 1024:
                abort(400, f"Request payload too large. Maximum size: {max_size_mb}MB")
            
            try:
                data = request.get_json(force=True)
            except Exception as e:
                abort(400, f"Invalid JSON format: {str(e)}")
                
            if not data:
                abort(400, "Request body cannot be empty")
            
            # Validate required fields
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data or data[field] is None]
                if missing_fields:
                    abort(400, f"Missing required fields: {', '.join(missing_fields)}")
            
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# Enhanced utility functions
def parse_int(v, default=None, min_val=None, max_val=None, field_name="value"):
    """Parse integer with validation"""
    try:
        result = int(v)
        if min_val is not None and result < min_val:
            abort(400, f"{field_name} must be at least {min_val}")
        if max_val is not None and result > max_val:
            abort(400, f"{field_name} cannot exceed {max_val}")
        return result
    except (TypeError, ValueError):
        if default is not None:
            return default
        abort(400, f"Invalid {field_name}: must be a valid integer")

def parse_bool(v, default=False):
    """Parse boolean value safely"""
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    v = str(v).lower()
    return v in ("1", "true", "t", "yes", "y", "on")

def get_current_user_id():
    """Extract and validate user ID from request headers"""
    uid = request.headers.get("X-User-Id")
    if not uid:
        logger.warning(f"Missing X-User-Id header from {request.remote_addr}")
        abort(401, "User ID missing from headers. Please provide X-User-Id header.")
    try:
        user_id = int(uid)
        if user_id <= 0:
            abort(400, "User ID must be a positive integer")
        return user_id
    except ValueError:
        logger.warning(f"Invalid X-User-Id header: {uid}")
        abort(400, "Invalid X-User-Id header format. Must be a positive integer.")

# Health check endpoint
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Test database connection
        from db import test_simple_query
        db_result = test_simple_query()
        
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "database": "connected" if db_result else "disconnected",
            "uptime": "available"
        }
        
        return success_response(health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 503

@app.route("/products/<int:product_id>", methods=["GET"])
def get_product(product_id: int):
    """Get product details with variants and inventory"""
    logger.info(f"Fetching product {product_id}")
    
    # Validate product ID
    if product_id <= 0:
        abort(400, "Product ID must be a positive integer")
    
    sql = text("""
        SELECT 
             p.id,
             p.sku,
             p.title,
             p.description,
             p.category_id,
             p.created_at,
             v.id as variant_id,
             v.sku as variant_sku,
             v.price_cents,
             v.attributes,
             COALESCE(i.available, 0) AS available,
             COALESCE(i.reserved, 0) AS reserved 
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
                logger.info(f"Product {product_id} not found")
                abort(404, f"Product with ID {product_id} not found")
        
        # Build product response
        first = rows[0]
        product = {
            "id": first["id"],
            "sku": first["sku"],
            "title": first["title"],
            "description": first["description"],
            "category_id": first["category_id"],
            "created_at": first["created_at"].isoformat() if first["created_at"] else None,
            "variants": []
        }
        
        for r in rows:
            if r["variant_id"] is not None:
                variant = {
                    "variant_id": r["variant_id"],
                    "variant_sku": r["variant_sku"],
                    "price_cents": r["price_cents"],
                    "attributes": r["attributes"] or {},
                    "available": r["available"],
                    "reserved": r["reserved"],
                    "available_quantity": max(0, r["available"] - r["reserved"]),
                    "in_stock": (r["available"] - r["reserved"]) > 0
                }
                product["variants"].append(variant)
        
        # Add computed fields
        if product["variants"]:
            product["min_price_cents"] = min(v["price_cents"] for v in product["variants"])
            product["max_price_cents"] = max(v["price_cents"] for v in product["variants"])
            product["total_available"] = sum(v["available_quantity"] for v in product["variants"])
            product["variant_count"] = len(product["variants"])
            product["in_stock"] = any(v["in_stock"] for v in product["variants"])
        else:
            product.update({
                "min_price_cents": None,
                "max_price_cents": None,
                "total_available": 0,
                "variant_count": 0,
                "in_stock": False
            })
        
        logger.info(f"Successfully retrieved product {product_id} with {len(product['variants'])} variants")
        return success_response(product)
        
    except Exception as e:
        logger.error(f"Error fetching product {product_id}: {e}")
        if hasattr(e, 'code'):  # Flask abort errors
            raise
        abort(500, "Failed to retrieve product")


@app.route("/products", methods=["GET"])
def list_products():
    """List products with filtering and pagination"""
    logger.info(f"Listing products with params: {dict(request.args)}")
    
    # Parse and validate query parameters
    limit = parse_int(request.args.get("limit"), default=20, min_val=1, max_val=100, field_name="limit")
    after = parse_int(request.args.get("after"), default=None, min_val=1, field_name="after")
    category_id = parse_int(request.args.get("category_id"), default=None, min_val=1, field_name="category_id")
    
    # Search query validation
    search_query = request.args.get("q", "").strip()
    if search_query and len(search_query) < 2:
        abort(400, "Search query must be at least 2 characters")
    if search_query and len(search_query) > 100:
        abort(400, "Search query cannot exceed 100 characters")
    
    # Price range validation
    min_price_cents = parse_int(request.args.get('min_price_cents'), default=None, min_val=0, field_name="min_price_cents")
    max_price_cents = parse_int(request.args.get('max_price_cents'), default=None, min_val=0, field_name="max_price_cents")
    
    if min_price_cents is not None and max_price_cents is not None and min_price_cents > max_price_cents:
        abort(400, "min_price_cents cannot be greater than max_price_cents")
    
    has_inventory = parse_bool(request.args.get("has_inventory"), default=None)
    
    sql="""SELECT p.id AS product_id,
             p.sku AS product_sku,
             p.title ,
             MIN(v.price_cents) AS min_price_cents,
             COUNT(v.id) AS variant_count,
             COALESCE(SUM(i.available-i.reserved),0) AS total_available
             FROM products p
             LEFT JOIN product_variants v ON v.product_id=p.id
             LEFT JOIN inventory i ON i.variant_id=v.id
             WHERE 1=1 """
    
    params={}
    
    if after is not None:
        sql+='AND p.id>:after '
        params["after"]=after
    if category_id is not None:
        sql+='AND p.category_id=:category_id '
        params["category_id"]=category_id
        
    if q:
        sql+='AND p.title ILIKE :q '
        params["q"]=f"%{q}%"
        
    sql += """GROUP BY p.id , p.sku , p.title """
         
         
    having_clauses = []
    if min_price_cents is not None:
        having_clauses.append("MIN(v.price_cents) >= :min_price_cents")
        params["min_price_cents"] = min_price_cents
    if max_price_cents is not None:
        having_clauses.append("MIN(v.price_cents) <= :max_price_cents")
        params["max_price_cents"] = max_price_cents
    if has_inventory is True:
        having_clauses.append("COALESCE(SUM(i.available-i.reserved),0) > 0")
    elif has_inventory is False:
        having_clauses.append("COALESCE(SUM(i.available-i.reserved),0) = 0")

    if having_clauses:
        sql += " HAVING " + " AND ".join(having_clauses)

    sql += """ ORDER BY p.id
            LIMIT :limit"""
    params["limit"] = limit
    
    with get_connection() as conn:
        try:
            # Execute query with exact limit
            rows = conn.execute(text(sql), params).mappings().all()
            
            # Check for next page by trying to fetch one more record
            has_more = False
            cursor = None
            
            if len(rows) == limit:
                # Check if there are more records
                next_check_sql = sql.replace("LIMIT :limit", "LIMIT 1 OFFSET :offset")
                next_params = params.copy()
                next_params["offset"] = len(rows)
                
                next_row = conn.execute(text(next_check_sql), next_params).mappings().first()
                if next_row:
                    has_more = True
                    cursor = rows[-1]["product_id"]
            
            items = []
            for r in rows:
                items.append({
                    "product_id": int(r["product_id"]),
                    "product_sku": r["product_sku"],
                    "title": r["title"],
                    "min_price_cents": int(r["min_price_cents"]) if r["min_price_cents"] is not None else None,
                    "variant_count": r["variant_count"],
                    "total_available": r["total_available"]
                })
            
            response_data = {
                "items": items,
                "pagination": {
                    "cursor": cursor,
                    "has_more": has_more,
                    "count": len(items),
                    "limit": limit
                }
            }
            
            return success_response(response_data)
            
        except Exception as e:
            abort(500, f"Failed to fetch products: {str(e)}")
    
    
@app.route("/carts/me",methods=["GET"])
def get_my_cart():
    user_id = get_current_user_id()
    
    with get_connection() as conn:
        try:
            # Ensure cart exists for user (atomic operation)
            conn.execute(text("""INSERT INTO carts(user_id,created_at,updated_at)
                              VALUES(:uid,NOW(),NOW())
                              ON CONFLICT (user_id) DO NOTHING"""), {"uid": user_id})
            
            # Get cart with items in single query
            cart_sql = text("""SELECT 
                               c.id as cart_id,
                               c.user_id,
                               ci.id as cart_item_id,
                               ci.quantity,
                               v.id as variant_id,
                               v.sku as variant_sku,
                               v.price_cents,
                               v.attributes,
                               p.id as product_id,
                               p.sku as product_sku,
                               p.title
                               FROM carts c
                               LEFT JOIN cart_items ci ON ci.cart_id = c.id
                               LEFT JOIN product_variants v ON ci.variant_id = v.id
                               LEFT JOIN products p ON v.product_id = p.id
                               WHERE c.user_id = :uid
                               ORDER BY ci.created_at DESC""")
            
            rows = conn.execute(cart_sql, {"uid": user_id}).mappings().all()
            
            if not rows:
                abort(500, "Failed to create or fetch cart")
            
            # Build response
            first_row = rows[0]
            cart_id = first_row["cart_id"]
            
            items = []
            total_cents = 0
            
            for r in rows:
                if r["cart_item_id"] is not None:  # Cart might be empty
                    qty = r["quantity"]
                    price = r["price_cents"]
                    total_cents += qty * price
                    
                    items.append({
                        "cart_item_id": int(r["cart_item_id"]),
                        "variant_id": int(r["variant_id"]),
                        "variant_sku": r["variant_sku"],
                        "product_id": r["product_id"],
                        "product_sku": r["product_sku"],
                        "product_title": r["title"],
                        "product_price": r["price_cents"],
                        "quantity": r["quantity"]
                    })
            
            cart_data = {
                "cart_id": cart_id,
                "user_id": user_id,
                "total_items": len(items),
                "total_quantity": sum(item["quantity"] for item in items),
                "total_cents": total_cents,
                "is_empty": len(items) == 0,
                "items": items
            }
            
            conn.commit()
            return success_response(cart_data)
            
        except Exception as e:
            conn.rollback()
            if hasattr(e, 'code'):  # Flask abort errors
                raise
            abort(500, f"Failed to fetch cart: {str(e)}")

@app.route("/carts/me/items",methods=["POST"])
@validate_json_request(["variant_id", "quantity"])
def add_cart_item():
    user_id = get_current_user_id()
    data = request.get_json(force=True)
    variant_id = parse_int(data.get("variant_id"))
    quantity = parse_int(data.get("quantity"))
    
    # Validate inputs
    if not variant_id or not quantity or quantity <= 0:
        abort(400, "variant_id and quantity > 0 required")
    
    if quantity > 99:
        abort(400, "Quantity cannot exceed 99")
    
    with get_connection() as conn:
        try:
            # 1. Check variant exists and get inventory
            variant_check = conn.execute(text("""
                SELECT v.id, v.price_cents,
                       COALESCE(i.available, 0) as available, 
                       COALESCE(i.reserved, 0) as reserved
                FROM product_variants v
                LEFT JOIN inventory i ON i.variant_id = v.id
                WHERE v.id = :vid
            """), {"vid": variant_id}).mappings().first()
            
            if not variant_check:
                abort(404, "Product variant not found")
            
            # 2. Check inventory availability
            available_qty = variant_check["available"] - variant_check["reserved"]
            if available_qty < quantity:
                abort(400, f"Insufficient inventory. Available: {available_qty}, Requested: {quantity}")
            
            # 3. Get or create cart
            conn.execute(text("""INSERT INTO carts(user_id,created_at,updated_at)
                              VALUES(:uid,NOW(),NOW())
                              ON CONFLICT (user_id) DO NOTHING"""), {"uid": user_id})
            
            cart_row = conn.execute(text("""SELECT id FROM carts WHERE user_id=:uid"""), 
                                   {"uid": user_id}).mappings().first()
            
            if not cart_row:
                abort(500, "Failed to create or fetch cart")
            
            cart_id = cart_row["id"]
            
            # 4. Check if adding to existing item would exceed limits
            existing_item = conn.execute(text("""
                SELECT quantity FROM cart_items 
                WHERE cart_id = :cart_id AND variant_id = :variant_id
            """), {"cart_id": cart_id, "variant_id": variant_id}).mappings().first()
            
            total_quantity = quantity
            if existing_item:
                total_quantity += existing_item["quantity"]
                if total_quantity > 99:
                    abort(400, f"Total quantity would exceed 99. Current: {existing_item['quantity']}, Adding: {quantity}")
                
                # Check total quantity against inventory
                if total_quantity > available_qty:
                    abort(400, f"Total quantity exceeds available inventory. Available: {available_qty}, Total would be: {total_quantity}")
            
            # 5. Add/update item in cart
            conn.execute(text("""
                INSERT INTO cart_items(cart_id, variant_id, quantity, created_at, updated_at) 
                VALUES (:cart_id, :variant_id, :quantity, NOW(), NOW()) 
                ON CONFLICT(cart_id, variant_id) 
                DO UPDATE SET 
                    quantity = cart_items.quantity + EXCLUDED.quantity,
                    updated_at = NOW()
            """), {"cart_id": cart_id, "variant_id": variant_id, "quantity": quantity})
            
            conn.commit()
            return success_response({"cart_id": cart_id, "variant_id": variant_id, "quantity_added": quantity}, 
                                   "Item added to cart successfully", 201)
            
        except Exception as e:
            conn.rollback()
            if hasattr(e, 'code'):  # Flask abort errors
                raise
            abort(500, f"Failed to add item to cart: {str(e)}") 
      
@app.route("/carts/me/items/<int:cart_item_id>",methods=["PATCH"])
@validate_json_request(["quantity"])
def update_cart_item(cart_item_id):
    user_id = get_current_user_id()
    data = request.get_json(force=True)
    quantity = parse_int(data.get("quantity"))
    
    if quantity is None or quantity < 0:
        abort(400, "Quantity must be >= 0")
    
    if quantity > 99:
        abort(400, "Quantity cannot exceed 99")
    
    with get_connection() as conn:
        try:
            # 1. Verify cart and item ownership
            item_check = conn.execute(text("""
                SELECT ci.id, ci.variant_id, ci.quantity,
                       COALESCE(i.available, 0) as available,
                       COALESCE(i.reserved, 0) as reserved
                FROM cart_items ci
                JOIN carts c ON ci.cart_id = c.id
                LEFT JOIN inventory i ON i.variant_id = ci.variant_id
                WHERE ci.id = :cart_item_id AND c.user_id = :user_id
            """), {"cart_item_id": cart_item_id, "user_id": user_id}).mappings().first()
            
            if not item_check:
                abort(404, "Cart item not found")
            
            # 2. If quantity is 0, delete the item
            if quantity == 0:
                conn.execute(text("""DELETE FROM cart_items WHERE id = :cart_item_id"""), 
                           {"cart_item_id": cart_item_id})
                
                conn.commit()
                return success_response({"cart_item_id": cart_item_id}, "Item removed from cart")
            
            # 3. Check inventory for new quantity
            available_qty = item_check["available"] - item_check["reserved"]
            if quantity > available_qty:
                abort(400, f"Insufficient inventory. Available: {available_qty}, Requested: {quantity}")
            
            # 4. Update the item
            conn.execute(text("""
                UPDATE cart_items 
                SET quantity = :quantity, updated_at = NOW() 
                WHERE id = :cart_item_id
            """), {"cart_item_id": cart_item_id, "quantity": quantity})
            
            conn.commit()
            return success_response({"cart_item_id": cart_item_id, "new_quantity": quantity}, "Item updated successfully")
            
        except Exception as e:
            conn.rollback()
            if hasattr(e, 'code'):  # Flask abort errors
                raise
            abort(500, f"Failed to update cart item: {str(e)}")

@app.route("/carts/me/items/<int:cart_item_id>",methods=["DELETE"])
def delete_cart_item(cart_item_id):
    user_id = get_current_user_id()
    
    with get_connection() as conn:
        try:
            # Verify ownership and delete in single query
            result = conn.execute(text("""
                DELETE FROM cart_items 
                USING carts c
                WHERE cart_items.cart_id = c.id 
                AND c.user_id = :user_id 
                AND cart_items.id = :cart_item_id
                RETURNING cart_items.id
            """), {"user_id": user_id, "cart_item_id": cart_item_id}).mappings().first()
            
            if not result:
                abort(404, "Cart item not found")
            
            conn.commit()
            return success_response({"cart_item_id": cart_item_id}, "Item deleted successfully")
            
        except Exception as e:
            conn.rollback()
            if hasattr(e, 'code'):  # Flask abort errors
                raise
            abort(500, f"Failed to delete cart item: {str(e)}")

               
if __name__ == '__main__':
    print("🚀 Starting E-commerce API Server...")
    print("📋 Available endpoints:")
    for rule in app.url_map.iter_rules():
        if rule.rule != '/static/<path:filename>':
            methods = sorted(rule.methods - {"HEAD", "OPTIONS"})
            print(f"  {rule.rule} - {methods}")
    print("\n💡 Remember to set X-User-Id header for cart operations")
    print("🔗 API running at: http://0.0.0.0:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
    