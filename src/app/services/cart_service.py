from typing import Optional
from app.repositories.cart_repository import CartRepository
from app.services.product_service import ProductService
from app.models.cart import Cart, CartItem
from app.schemas.cart_schemas import AddToCartRequest, UpdateCartItemRequest
from app.core.exceptions import (
    NotFoundError, ValidationError, BusinessLogicError, ConflictError
)
import logging

logger = logging.getLogger(__name__)


class CartService:
    """
    Shopping cart business logic service
    
    Responsibilities:
    - Enforce cart business rules
    - Coordinate with inventory management
    - Handle cart state transitions
    - Manage cart expiration
    """
    
    def __init__(self, cart_repository: CartRepository, product_service: ProductService):
        self.cart_repo = cart_repository
        self.product_service = product_service
        self.max_items_per_cart = 50  # Business rule
        self.max_quantity_per_item = 99  # Business rule
    
    def get_user_cart(self, user_id: int) -> Cart:
        """
        Get user's current cart
        
        Business Rules:
        - Create cart if it doesn't exist
        - Validate cart items against current inventory
        - Remove unavailable items automatically
        """
        logger.info(f"Fetching cart for user {user_id}")
        
        try:
            cart = self.cart_repo.get_cart_by_user_id(user_id)
            
            # Business logic: Validate cart items
            validated_cart = self._validate_cart_items(cart)
            
            logger.info(f"Retrieved cart {validated_cart.cart_id} for user {user_id} with {validated_cart.total_items} items")
            return validated_cart
            
        except Exception as e:
            logger.error(f"Error retrieving cart for user {user_id}: {str(e)}")
            raise BusinessLogicError(f"Failed to retrieve cart: {str(e)}")
    
    def add_item_to_cart(self, user_id: int, request: AddToCartRequest) -> CartItem:
        """
        Add item to cart with business validation
        
        Business Rules:
        - Validate product variant exists and is available
        - Check inventory availability
        - Enforce cart limits
        - Reserve inventory during checkout
        """
        logger.info(f"Adding item to cart - user: {user_id}, variant: {request.variant_id}, quantity: {request.quantity}")
        
        # Business validation: Check variant exists and get details
        try:
            variant = self.product_service.get_variant_by_id(request.variant_id)
        except NotFoundError:
            raise ValidationError(f"Product variant {request.variant_id} not found")
        
        # Business rule: Check inventory availability
        if not self.product_service.check_variant_availability(request.variant_id, request.quantity):
            raise BusinessLogicError(
                "Insufficient inventory available for this item",
                rule="insufficient_inventory"
            )
        
        # Get current cart to check limits
        current_cart = self.cart_repo.get_cart_by_user_id(user_id)
        
        # Business rule: Check cart item limit
        if len(current_cart.items) >= self.max_items_per_cart:
            existing_item = current_cart.get_item_by_variant(request.variant_id)
            if not existing_item:  # Adding new item would exceed limit
                raise BusinessLogicError(
                    f"Cannot add more than {self.max_items_per_cart} different items to cart",
                    rule="max_cart_items_exceeded"
                )
        
        # Business rule: Check quantity limits
        existing_item = current_cart.get_item_by_variant(request.variant_id)
        total_quantity = request.quantity
        if existing_item:
            total_quantity += existing_item.quantity
        
        if total_quantity > self.max_quantity_per_item:
            raise BusinessLogicError(
                f"Cannot add more than {self.max_quantity_per_item} of the same item",
                rule="max_item_quantity_exceeded"
            )
        
        try:
            # Add item to cart
            cart_item = self.cart_repo.add_item_to_cart(
                user_id=user_id,
                variant_id=request.variant_id,
                quantity=request.quantity
            )
            
            logger.info(f"Successfully added item {cart_item.cart_item_id} to cart for user {user_id}")
            
            # Business logic: You might want to reserve inventory here
            # for a short period (e.g., 15 minutes) to prevent overselling
            # self.product_service.reserve_inventory(request.variant_id, request.quantity)
            
            return cart_item
            
        except Exception as e:
            logger.error(f"Error adding item to cart for user {user_id}: {str(e)}")
            raise BusinessLogicError(f"Failed to add item to cart: {str(e)}")
    
    def update_cart_item(
        self, 
        user_id: int, 
        cart_item_id: int, 
        request: UpdateCartItemRequest
    ) -> Optional[CartItem]:
        """
        Update cart item quantity with business validation
        
        Business Rules:
        - Validate new quantity against inventory
        - Handle quantity 0 as item removal
        - Enforce quantity limits
        """
        logger.info(f"Updating cart item {cart_item_id} for user {user_id} to quantity {request.quantity}")
        
        # Get current cart to validate ownership and get current item
        current_cart = self.cart_repo.get_cart_by_user_id(user_id)
        current_item = current_cart.get_item_by_id(cart_item_id)
        
        if not current_item:
            raise NotFoundError("Cart item", str(cart_item_id))
        
        # Business rule: If quantity is 0, remove the item
        if request.quantity == 0:
            return self.remove_cart_item(user_id, cart_item_id)
        
        # Business rule: Check quantity limits
        if request.quantity > self.max_quantity_per_item:
            raise ValidationError(f"Quantity cannot exceed {self.max_quantity_per_item}")
        
        # Business rule: Check inventory availability for the new quantity
        if not self.product_service.check_variant_availability(current_item.variant_id, request.quantity):
            raise BusinessLogicError(
                "Insufficient inventory for requested quantity",
                rule="insufficient_inventory"
            )
        
        try:
            updated_item = self.cart_repo.update_cart_item_quantity(
                user_id=user_id,
                cart_item_id=cart_item_id,
                quantity=request.quantity
            )
            
            logger.info(f"Successfully updated cart item {cart_item_id} for user {user_id}")
            
            # Business logic: Handle inventory reservation changes
            quantity_diff = request.quantity - current_item.quantity
            if quantity_diff > 0:
                # Need more inventory
                if not self.product_service.reserve_inventory(current_item.variant_id, quantity_diff):
                    # Rollback the cart update if reservation fails
                    self.cart_repo.update_cart_item_quantity(user_id, cart_item_id, current_item.quantity)
                    raise ConflictError("Unable to reserve additional inventory")
            elif quantity_diff < 0:
                # Release some inventory
                self.product_service.release_inventory_reservation(current_item.variant_id, abs(quantity_diff))
            
            return updated_item
            
        except Exception as e:
            logger.error(f"Error updating cart item {cart_item_id} for user {user_id}: {str(e)}")
            raise BusinessLogicError(f"Failed to update cart item: {str(e)}")
    
    def remove_cart_item(self, user_id: int, cart_item_id: int) -> Optional[CartItem]:
        """
        Remove item from cart
        
        Business Rules:
        - Validate user owns the cart item
        - Release any reserved inventory
        """
        logger.info(f"Removing cart item {cart_item_id} for user {user_id}")
        
        try:
            # Get item details before removal (for inventory release)
            current_cart = self.cart_repo.get_cart_by_user_id(user_id)
            current_item = current_cart.get_item_by_id(cart_item_id)
            
            if not current_item:
                raise NotFoundError("Cart item", str(cart_item_id))
            
            removed_item = self.cart_repo.remove_cart_item(user_id, cart_item_id)
            
            if removed_item:
                logger.info(f"Successfully removed cart item {cart_item_id} for user {user_id}")
                
                # Business logic: Release reserved inventory
                self.product_service.release_inventory_reservation(
                    current_item.variant_id, 
                    current_item.quantity
                )
            
            return removed_item
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error removing cart item {cart_item_id} for user {user_id}: {str(e)}")
            raise BusinessLogicError(f"Failed to remove cart item: {str(e)}")
    
    def clear_cart(self, user_id: int) -> bool:
        """
        Remove all items from cart
        
        Business Rules:
        - Release all reserved inventory
        - Log cart clearing for audit
        """
        logger.info(f"Clearing cart for user {user_id}")
        
        try:
            # Get current cart to release reservations
            current_cart = self.cart_repo.get_cart_by_user_id(user_id)
            
            # Business logic: Release all inventory reservations
            for item in current_cart.items:
                self.product_service.release_inventory_reservation(
                    item.variant_id,
                    item.quantity
                )
            
            success = self.cart_repo.clear_cart(user_id)
            
            if success:
                logger.info(f"Successfully cleared cart for user {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error clearing cart for user {user_id}: {str(e)}")
            raise BusinessLogicError(f"Failed to clear cart: {str(e)}")
    
    def get_cart_summary(self, user_id: int) -> dict:
        """
        Get cart summary with business calculations
        
        Business Rules:
        - Calculate taxes and shipping
        - Apply discounts if applicable
        - Validate all items before checkout
        """
        logger.info(f"Getting cart summary for user {user_id}")
        
        try:
            cart = self.get_user_cart(user_id)
            
            # Business calculations
            subtotal_cents = cart.total_cents
            tax_cents = self._calculate_tax(subtotal_cents, user_id)
            shipping_cents = self._calculate_shipping(cart, user_id)
            discount_cents = self._calculate_discounts(cart, user_id)
            total_cents = subtotal_cents + tax_cents + shipping_cents - discount_cents
            
            summary = {
                "cart_id": cart.cart_id,
                "user_id": cart.user_id,
                "subtotal_cents": subtotal_cents,
                "tax_cents": tax_cents,
                "shipping_cents": shipping_cents,
                "discount_cents": discount_cents,
                "total_cents": total_cents,
                "total_items": cart.total_items,
                "total_quantity": cart.total_quantity,
                "is_empty": cart.is_empty,
                "can_checkout": self._can_checkout(cart)
            }
            
            logger.info(f"Generated cart summary for user {user_id}: total={total_cents}¢")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating cart summary for user {user_id}: {str(e)}")
            raise BusinessLogicError(f"Failed to generate cart summary: {str(e)}")
    
    # Private helper methods for business logic
    def _validate_cart_items(self, cart: Cart) -> Cart:
        """Validate all items in cart against current inventory and pricing"""
        validated_items = []
        items_removed = 0
        
        for item in cart.items:
            try:
                # Check if variant still exists and is available
                variant = self.product_service.get_variant_by_id(item.variant_id)
                
                # Business rule: Remove items that are no longer available
                if not variant.in_stock:
                    logger.warning(f"Removing unavailable item {item.cart_item_id} from cart {cart.cart_id}")
                    self.cart_repo.remove_cart_item(cart.user_id, item.cart_item_id)
                    items_removed += 1
                    continue
                
                # Business rule: Adjust quantity if insufficient inventory
                max_available = variant.available_quantity
                if item.quantity > max_available:
                    if max_available > 0:
                        logger.warning(f"Reducing quantity for item {item.cart_item_id} from {item.quantity} to {max_available}")
                        self.cart_repo.update_cart_item_quantity(cart.user_id, item.cart_item_id, max_available)
                        item.quantity = max_available
                    else:
                        logger.warning(f"Removing out-of-stock item {item.cart_item_id} from cart {cart.cart_id}")
                        self.cart_repo.remove_cart_item(cart.user_id, item.cart_item_id)
                        items_removed += 1
                        continue
                
                validated_items.append(item)
                
            except NotFoundError:
                # Product/variant was deleted - remove from cart
                logger.warning(f"Removing deleted product item {item.cart_item_id} from cart {cart.cart_id}")
                self.cart_repo.remove_cart_item(cart.user_id, item.cart_item_id)
                items_removed += 1
        
        if items_removed > 0:
            logger.info(f"Removed {items_removed} invalid items from cart {cart.cart_id}")
            # Refresh cart from database
            cart = self.cart_repo.get_cart_by_user_id(cart.user_id)
        
        return cart
    
    def _calculate_tax(self, subtotal_cents: int, user_id: int) -> int:
        """Calculate tax based on user location and business rules"""
        # Business logic: Tax calculation (simplified)
        # In reality, this would integrate with tax calculation service
        tax_rate = 0.08  # 8% tax rate
        return int(subtotal_cents * tax_rate)
    
    def _calculate_shipping(self, cart: Cart, user_id: int) -> int:
        """Calculate shipping costs based on cart and user location"""
        # Business logic: Shipping calculation
        if cart.total_cents >= 5000:  # Free shipping over $50
            return 0
        return 799  # $7.99 standard shipping
    
    def _calculate_discounts(self, cart: Cart, user_id: int) -> int:
        """Apply applicable discounts and promotions"""
        # Business logic: Discount calculation
        # This would integrate with promotion engine
        return 0  # No discounts for now
    
    def _can_checkout(self, cart: Cart) -> bool:
        """Determine if cart is ready for checkout"""
        if cart.is_empty:
            return False
        
        # Business rules for checkout readiness
        min_order_amount = 100  # $1.00 minimum order
        if cart.total_cents < min_order_amount:
            return False
        
        return True