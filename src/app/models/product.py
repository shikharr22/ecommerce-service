from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
import json

@dataclass
class ProductVariant:
    """Represents a product variant with pricing and inventory"""
    variant_id: int
    variant_sku: str
    price_cents: int  # Store as cents to avoid floating point issues
    attributes: Dict[str, Any]  # JSONB data: {"color": "red", "size": "L"}
    available: int
    reserved: int
    
    @property
    def price_dollars(self)->Decimal:
        return Decimal(self.price_cents/100)
    
    @property
    def available_quantity(self)->int:
        return max(0,self.available-self.reserved)
    
    @property
    def in_stock(self)->int:
        return (self.available-self.reserved)>0
    
    def get_attribute(self, key: str, default: Any = None) -> Any:
        """Safely get attribute value"""
        return self.attributes.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "variant_id": self.variant_id,
            "variant_sku": self.variant_sku,
            "price_cents": self.price_cents,
            "price_dollars": str(self.price_dollars),
            "attributes": self.attributes,
            "available": self.available,
            "reserved": self.reserved,
            "in_stock": self.in_stock,
            "available_quantity": self.available_quantity
        }

@dataclass
class Product:
    """Represents a complete product with all its variants"""
    id: int
    sku: str
    title: str
    description: str
    category_id: int
    created_at: datetime
    variants: List[ProductVariant] = field(default_factory=list)
    
    @property
    def min_price_cents(self) -> Optional[int]:
        """Get minimum price across all variants"""
        if not self.variants:
            return None
        return min(v.price_cents for v in self.variants)
    
    @property
    def max_price_cents(self) -> Optional[int]:
        """Get maximum price across all variants"""
        if not self.variants:
            return None
        return max(v.price_cents for v in self.variants)
    
    @property
    def total_available_quantity(self) -> int:
        """Get total available inventory across all variants"""
        return sum(v.available_quantity for v in self.variants)
    
    @property
    def in_stock(self) -> bool:
        """Check if product has any available inventory"""
        return any(v.in_stock for v in self.variants)
    
    @property
    def variant_count(self) -> int:
        """Number of variants for this product"""
        return len(self.variants)
    
    def get_variant_by_id(self, variant_id: int) -> Optional[ProductVariant]:
        """Find variant by ID"""
        return next((v for v in self.variants if v.variant_id == variant_id), None)
    
    def get_variants_by_attribute(self, key: str, value: Any) -> List[ProductVariant]:
        """Filter variants by attribute"""
        return [v for v in self.variants if v.get_attribute(key) == value]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "sku": self.sku,
            "title": self.title,
            "description": self.description,
            "category_id": self.category_id,
            "created_at": self.created_at.isoformat(),
            "min_price_cents": self.min_price_cents,
            "max_price_cents": self.max_price_cents,
            "total_available_quantity": self.total_available_quantity,
            "in_stock": self.in_stock,
            "variant_count": self.variant_count,
            "variants": [v.to_dict() for v in self.variants]
        }
        
@dataclass
class ProductSummary:
    """Lightweight product representation for listing endpoints"""
    product_id: int
    product_sku: str
    title: str
    min_price_cents: Optional[int]
    variant_count: int
    total_available: int
    
    @property
    def min_price_dollars(self) -> Optional[Decimal]:
        """Convert min price to dollars"""
        if self.min_price_cents is None:
            return None
        return Decimal(self.min_price_cents) / 100
    
    @property
    def in_stock(self) -> bool:
        """Check if product has available inventory"""
        return self.total_available > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "product_id": self.product_id,
            "product_sku": self.product_sku,
            "title": self.title,
            "min_price_cents": self.min_price_cents,
            "min_price_dollars": str(self.min_price_dollars) if self.min_price_dollars else None,
            "variant_count": self.variant_count,
            "total_available": self.total_available,
            "in_stock": self.in_stock
        }