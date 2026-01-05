from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum

class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentStatus(Enum):
    """Payment status enumeration"""
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


@dataclass
class OrderItem:
    """Represents an item within an order"""
    order_item_id: int
    order_id: int
    variant_id: int
    variant_sku: str
    product_id: int
    product_sku: str
    product_title: str
    price_cents: int  # Price at time of order
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "order_item_id": self.order_item_id,
            "order_id": self.order_id,
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
class ShippingAddress:
    """Represents shipping address for an order"""
    recipient_name: str
    address_line1: str
    address_line2: Optional[str]
    city: str
    state: str
    postal_code: str
    country: str
    phone: Optional[str] = None
    
    @property
    def formatted_address(self) -> str:
        """Get formatted address string"""
        address_parts = [self.address_line1]
        if self.address_line2:
            address_parts.append(self.address_line2)
        address_parts.extend([self.city, self.state, self.postal_code, self.country])
        return ", ".join(address_parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "recipient_name": self.recipient_name,
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code,
            "country": self.country,
            "phone": self.phone,
            "formatted_address": self.formatted_address
        }
        
@dataclass
class Order:
    """Represents a customer order"""
    id: int
    user_id: int
    order_number: str  # Human-readable order number (e.g., "ORD-2026-001234")
    status: OrderStatus
    payment_status: PaymentStatus
    subtotal_cents: int
    tax_cents: int
    shipping_cents: int
    total_cents: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    items: List[OrderItem] = field(default_factory=list)
    shipping_address: Optional[ShippingAddress] = None
    notes: Optional[str] = None
    
    @property
    def subtotal_dollars(self) -> Decimal:
        """Convert subtotal to dollars"""
        return Decimal(self.subtotal_cents) / 100
    
    @property
    def tax_dollars(self) -> Decimal:
        """Convert tax to dollars"""
        return Decimal(self.tax_cents) / 100
    
    @property
    def shipping_dollars(self) -> Decimal:
        """Convert shipping to dollars"""
        return Decimal(self.shipping_cents) / 100
    
    @property
    def total_dollars(self) -> Decimal:
        """Convert total to dollars"""
        return Decimal(self.total_cents) / 100
    
    @property
    def total_items(self) -> int:
        """Total number of unique items in order"""
        return len(self.items)
    
    @property
    def total_quantity(self) -> int:
        """Total quantity of all items"""
        return sum(item.quantity for item in self.items)
    
    @property
    def is_pending(self) -> bool:
        """Check if order is pending"""
        return self.status == OrderStatus.PENDING
    
    @property
    def is_confirmed(self) -> bool:
        """Check if order is confirmed"""
        return self.status == OrderStatus.CONFIRMED
    
    @property
    def is_shipped(self) -> bool:
        """Check if order is shipped"""
        return self.status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    
    @property
    def is_delivered(self) -> bool:
        """Check if order is delivered"""
        return self.status == OrderStatus.DELIVERED
    
    @property
    def is_cancelled(self) -> bool:
        """Check if order is cancelled"""
        return self.status == OrderStatus.CANCELLED
    
    @property
    def can_be_cancelled(self) -> bool:
        """Check if order can be cancelled"""
        return self.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED]
    
    @property
    def is_paid(self) -> bool:
        """Check if order is fully paid"""
        return self.payment_status == PaymentStatus.PAID
    
    def get_item_by_variant(self, variant_id: int) -> Optional[OrderItem]:
        """Find order item by variant ID"""
        return next((item for item in self.items if item.variant_id == variant_id), None)
    
    def calculate_totals(self) -> None:
        """Recalculate order totals from items"""
        self.subtotal_cents = sum(item.subtotal_cents for item in self.items)
        # Tax and shipping would be calculated by business logic
        self.total_cents = self.subtotal_cents + self.tax_cents + self.shipping_cents
    
    def to_dict(self, include_items: bool = True) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "order_number": self.order_number,
            "status": self.status.value,
            "payment_status": self.payment_status.value,
            "subtotal_cents": self.subtotal_cents,
            "subtotal_dollars": str(self.subtotal_dollars),
            "tax_cents": self.tax_cents,
            "tax_dollars": str(self.tax_dollars),
            "shipping_cents": self.shipping_cents,
            "shipping_dollars": str(self.shipping_dollars),
            "total_cents": self.total_cents,
            "total_dollars": str(self.total_dollars),
            "total_items": self.total_items,
            "total_quantity": self.total_quantity,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "shipped_at": self.shipped_at.isoformat() if self.shipped_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "notes": self.notes,
            "is_pending": self.is_pending,
            "is_confirmed": self.is_confirmed,
            "is_shipped": self.is_shipped,
            "is_delivered": self.is_delivered,
            "is_cancelled": self.is_cancelled,
            "can_be_cancelled": self.can_be_cancelled,
            "is_paid": self.is_paid
        }
        
        if include_items:
            data["items"] = [item.to_dict() for item in self.items]
        
        if self.shipping_address:
            data["shipping_address"] = self.shipping_address.to_dict()
        
        return data


@dataclass
class OrderSummary:
    """Lightweight order representation for listing"""
    order_id: int
    user_id: int
    order_number: str
    status: OrderStatus
    payment_status: PaymentStatus
    total_cents: int
    total_items: int
    created_at: datetime
    
    @property
    def total_dollars(self) -> Decimal:
        """Convert total to dollars"""
        return Decimal(self.total_cents) / 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "order_id": self.order_id,
            "user_id": self.user_id,
            "order_number": self.order_number,
            "status": self.status.value,
            "payment_status": self.payment_status.value,
            "total_cents": self.total_cents,
            "total_dollars": str(self.total_dollars),
            "total_items": self.total_items,
            "created_at": self.created_at.isoformat()
        }