from typing import Optional, List
from app.repositories.base import BaseRepository
from app.models.cart import Cart, CartItem
from app.core.exceptions import NotFoundError, ConflictError
import logging

logger = logging.getLogger(__name__)


class CartRepository(BaseRepository[Cart]):
    """Repository for shopping cart operations"""
    
    @property
    def table_name(self) -> str:
        return "carts"
    
    def get_by_id(self, cart_id: int) -> Cart:
        """Get cart by ID (not commonly used - usually get by user)"""
        return self.get_cart_by_user_id(cart_id)  # Assuming cart_id == user_id for simplicity
    
    def get_cart_by_user_id(self, user_id: int) -> Cart:
        """
        Get user's cart with all items
        
        Demonstrates:
        - Complex JOIN across multiple tables
        - User-centric data access patterns
        - Handling empty carts gracefully
        """
        # First, ensure cart exists for user
        cart_query = """
        INSERT INTO carts (user_id, created_at, updated_at) 
        VALUES (:user_id, NOW(), NOW())
        ON CONFLICT (user_id) DO NOTHING
        RETURNING id
        """
        self.execute_command(cart_query, {"user_id": user_id})
        
        # Get cart with items
        query = """
        SELECT 
            c.id as cart_id,
            c.user_id,
            ci.id as cart_item_id,
            ci.variant_id,
            ci.quantity,
            v.sku as variant_sku,
            v.price_cents,
            p.id as product_id,
            p.sku as product_sku,
            p.title as product_title
        FROM carts c
        LEFT JOIN cart_items ci ON ci.cart_id = c.id
        LEFT JOIN product_variants v ON v.id = ci.variant_id
        LEFT JOIN products p ON p.id = v.product_id
        WHERE c.user_id = :user_id
        ORDER BY ci.created_at DESC
        """
        
        rows = self.execute_query(query, {"user_id": user_id})
        
        if not rows:
            raise NotFoundError("Cart", f"user_id={user_id}")
        
        return self._build_cart_from_rows(rows)
    
    def add_item_to_cart(
        self, 
        user_id: int, 
        variant_id: int, 
        quantity: int
    ) -> CartItem:
        """
        Add item to cart or update quantity if item already exists
        
        Demonstrates:
        - UPSERT operations
        - Business logic in repository (debatable - could be in service)
        - Transaction handling for consistency
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be positive")
        
        # Check if item already exists in cart
        existing_item_query = """
        SELECT ci.id, ci.quantity
        FROM cart_items ci
        JOIN carts c ON c.id = ci.cart_id
        WHERE c.user_id = :user_id AND ci.variant_id = :variant_id
        """
        
        existing_item = self.execute_single_query(existing_item_query, {
            "user_id": user_id,
            "variant_id": variant_id
        })
        
        if existing_item:
            # Update existing item quantity
            new_quantity = existing_item["quantity"] + quantity
            update_query = """
            UPDATE cart_items 
            SET quantity = :quantity, updated_at = NOW()
            WHERE id = :cart_item_id
            """
            self.execute_command(update_query, {
                "quantity": new_quantity,
                "cart_item_id": existing_item["id"]
            })
            cart_item_id = existing_item["id"]
        else:
            # Insert new item
            # First get cart_id
            cart_query = "SELECT id FROM carts WHERE user_id = :user_id"
            cart_result = self.execute_single_query(cart_query, {"user_id": user_id})
            
            if not cart_result:
                raise NotFoundError("Cart", f"user_id={user_id}")
            
            insert_query = """
            INSERT INTO cart_items (cart_id, variant_id, quantity, created_at, updated_at)
            VALUES (:cart_id, :variant_id, :quantity, NOW(), NOW())
            """
            cart_item_id = self.execute_insert_returning_id(insert_query, {
                "cart_id": cart_result["id"],
                "variant_id": variant_id,
                "quantity": quantity
            })
        
        # Return the cart item with full details
        return self._get_cart_item_details(cart_item_id)
    
    def update_cart_item_quantity(
        self, 
        user_id: int, 
        cart_item_id: int, 
        quantity: int
    ) -> Optional[CartItem]:
        """Update cart item quantity or remove if quantity is 0"""
        if quantity < 0:
            raise ValidationError("Quantity cannot be negative")
        
        if quantity == 0:
            return self.remove_cart_item(user_id, cart_item_id)
        
        # Verify ownership and update
        query = """
        UPDATE cart_items 
        SET quantity = :quantity, updated_at = NOW()
        FROM carts c
        WHERE cart_items.cart_id = c.id 
        AND c.user_id = :user_id 
        AND cart_items.id = :cart_item_id
        """
        
        affected_rows = self.execute_command(query, {
            "quantity": quantity,
            "user_id": user_id,
            "cart_item_id": cart_item_id
        })
        
        if affected_rows == 0:
            raise NotFoundError("Cart item", str(cart_item_id))
        
        return self._get_cart_item_details(cart_item_id)
    
    def remove_cart_item(self, user_id: int, cart_item_id: int) -> Optional[CartItem]:
        """Remove item from user's cart"""
        # Get item details before deletion
        item = None
        try:
            item = self._get_cart_item_details(cart_item_id)
        except NotFoundError:
            pass
        
        # Delete with ownership verification
        query = """
        DELETE FROM cart_items 
        USING carts c
        WHERE cart_items.cart_id = c.id 
        AND c.user_id = :user_id 
        AND cart_items.id = :cart_item_id
        """
        
        affected_rows = self.execute_command(query, {
            "user_id": user_id,
            "cart_item_id": cart_item_id
        })
        
        if affected_rows == 0:
            raise NotFoundError("Cart item", str(cart_item_id))
        
        return item
    
    def clear_cart(self, user_id: int) -> bool:
        """Remove all items from user's cart"""
        query = """
        DELETE FROM cart_items 
        USING carts c
        WHERE cart_items.cart_id = c.id 
        AND c.user_id = :user_id
        """
        
        affected_rows = self.execute_command(query, {"user_id": user_id})
        return affected_rows > 0
    
    def get_cart_item_count(self, user_id: int) -> int:
        """Get total number of items in user's cart"""
        query = """
        SELECT COALESCE(SUM(ci.quantity), 0) as total_items
        FROM carts c
        LEFT JOIN cart_items ci ON ci.cart_id = c.id
        WHERE c.user_id = :user_id
        """
        
        result = self.execute_scalar(query, {"user_id": user_id})
        return result or 0
    
    def _build_cart_from_rows(self, rows: List[Dict[str, Any]]) -> Cart:
        """Build Cart domain object from database rows"""
        if not rows:
            raise ValueError("Cannot build cart from empty rows")
        
        first_row = rows[0]
        cart_id = first_row["cart_id"]
        user_id = first_row["user_id"]
        
        # Build cart items
        items = []
        for row in rows:
            if row["cart_item_id"] is not None:  # Cart might be empty
                items.append(CartItem(
                    cart_item_id=row["cart_item_id"],
                    variant_id=row["variant_id"],
                    variant_sku=row["variant_sku"],
                    product_id=row["product_id"],
                    product_sku=row["product_sku"],
                    product_title=row["product_title"],
                    price_cents=row["price_cents"],
                    quantity=row["quantity"]
                ))
        
        return Cart(
            cart_id=cart_id,
            user_id=user_id,
            items=items
        )
    
    def _get_cart_item_details(self, cart_item_id: int) -> CartItem:
        """Get cart item with full product details"""
        query = """
        SELECT 
            ci.id as cart_item_id,
            ci.variant_id,
            ci.quantity,
            v.sku as variant_sku,
            v.price_cents,
            p.id as product_id,
            p.sku as product_sku,
            p.title as product_title
        FROM cart_items ci
        JOIN product_variants v ON v.id = ci.variant_id
        JOIN products p ON p.id = v.product_id
        WHERE ci.id = :cart_item_id
        """
        
        row = self.execute_single_query(query, {"cart_item_id": cart_item_id})
        
        if not row:
            raise NotFoundError("Cart item", str(cart_item_id))
        
        return CartItem(
            cart_item_id=row["cart_item_id"],
            variant_id=row["variant_id"],
            variant_sku=row["variant_sku"],
            product_id=row["product_id"],
            product_sku=row["product_sku"],
            product_title=row["product_title"],
            price_cents=row["price_cents"],
            quantity=row["quantity"]
        )