from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from decimal import Decimal

@dataclass
class CartItem:
    """Represents an item in a shopping cart"""
    cart_item_id: int
    variant_id: int
    variant_sku: str
    product_id: int
    product_sku: str
    product_title: str
    price_cents: int  # Price at time of adding to cart
    quantity: int
    
    @property
    def price_dollars(self) -> Decimal:
        """Convert price to dollars"""
        return Decimal(self.price_cents) / 100
    
    @property
    def subtotal_cents(self) -> int:
        """Calculate subtotal in cents"""
        return self.price_cents * self.quantity
    
    @property
    def subtotal_dollars(self) -> Decimal:
        """Calculate subtotal in dollars"""
        return Decimal(self.subtotal_cents) / 100
    
    def update_quantity(self, new_quantity: int) -> None:
        """Update item quantity with validation"""
        if new_quantity < 0:
            raise ValueError("Quantity cannot be negative")
        self.quantity = new_quantity
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "cart_item_id": self.cart_item_id,
            "variant_id": self.variant_id,
            "variant_sku": self.variant_sku,
            "product_id": self.product_id,
            "product_sku": self.product_sku,
            "product_title": self.product_title,
            "price_cents": self.price_cents,
            "price_dollars": str(self.price_dollars),
            "quantity": self.quantity,
            "subtotal_cents": self.subtotal_cents,
            "subtotal_dollars": str(self.subtotal_dollars)
        }
        
@dataclass
class Cart:
    """Represents a user's shopping cart"""
    cart_id: int
    user_id: int
    items: List[CartItem] = field(default_factory=list)
    
    @property
    def total_items(self) -> int:
        """Total number of items in cart"""
        return len(self.items)
    
    @property
    def total_quantity(self) -> int:
        """Total quantity of all items"""
        return sum(item.quantity for item in self.items)
    
    @property
    def total_cents(self) -> int:
        """Total cart value in cents"""
        return sum(item.subtotal_cents for item in self.items)
    
    @property
    def total_dollars(self) -> Decimal:
        """Total cart value in dollars"""
        return Decimal(self.total_cents) / 100
    
    @property
    def is_empty(self) -> bool:
        """Check if cart is empty"""
        return len(self.items) == 0
    
    def get_item_by_variant(self, variant_id: int) -> Optional[CartItem]:
        """Find cart item by variant ID"""
        return next((item for item in self.items if item.variant_id == variant_id), None)
    
    def get_item_by_id(self, cart_item_id: int) -> Optional[CartItem]:
        """Find cart item by cart item ID"""
        return next((item for item in self.items if item.cart_item_id == cart_item_id), None)
    
    def add_item(self, item: CartItem) -> None:
        """Add item to cart"""
        self.items.append(item)
    
    def remove_item(self, cart_item_id: int) -> bool:
        """Remove item from cart by ID"""
        original_length = len(self.items)
        self.items = [item for item in self.items if item.cart_item_id != cart_item_id]
        return len(self.items) < original_length
    
    def clear(self) -> None:
        """Remove all items from cart"""
        self.items.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "cart_id": self.cart_id,
            "user_id": self.user_id,
            "total_items": self.total_items,
            "total_quantity": self.total_quantity,
            "total_cents": self.total_cents,
            "total_dollars": str(self.total_dollars),
            "is_empty": self.is_empty,
            "items": [item.to_dict() for item in self.items]
        }