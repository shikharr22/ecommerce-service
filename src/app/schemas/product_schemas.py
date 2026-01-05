from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas.common_schemas import PaginationRequest, PaginationResponse, MoneyField


class ProductVariantBase(BaseModel):
    """Base product variant data"""
    variant_sku: str = Field(min_length=1, max_length=100, description="Variant SKU")
    price: MoneyField = Field(description="Variant price")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Variant attributes (color, size, etc.)")


class ProductVariantResponse(ProductVariantBase):
    """Product variant in API responses"""
    variant_id: int = Field(description="Unique variant identifier")
    available: int = Field(ge=0, description="Available inventory")
    reserved: int = Field(ge=0, description="Reserved inventory")
    in_stock: bool = Field(description="Whether variant is in stock")
    available_quantity: int = Field(ge=0, description="Actually available quantity")
    
    class Config:
        schema_extra = {
            "example": {
                "variant_id": 123,
                "variant_sku": "SHIRT-RED-M",
                "price": {
                    "cents": 2999,
                    "currency": "USD"
                },
                "attributes": {
                    "color": "red",
                    "size": "M",
                    "material": "cotton"
                },
                "available": 10,
                "reserved": 2,
                "in_stock": True,
                "available_quantity": 8
            }
        }


class ProductBase(BaseModel):
    """Base product information"""
    sku: str = Field(min_length=1, max_length=100, description="Product SKU")
    title: str = Field(min_length=1, max_length=500, description="Product title")
    description: str = Field(max_length=2000, description="Product description")
    category_id: int = Field(description="Product category identifier")


class ProductSummaryResponse(BaseModel):
    """Lightweight product for list endpoints"""
    product_id: int = Field(description="Unique product identifier")
    product_sku: str = Field(description="Product SKU")
    title: str = Field(description="Product title")
    min_price: Optional[MoneyField] = Field(default=None, description="Minimum price across variants")
    variant_count: int = Field(ge=0, description="Number of variants")
    total_available: int = Field(ge=0, description="Total available inventory")
    in_stock: bool = Field(description="Whether product has available inventory")
    
    class Config:
        schema_extra = {
            "example": {
                "product_id": 456,
                "product_sku": "SHIRT-001",
                "title": "Classic Cotton T-Shirt",
                "min_price": {
                    "cents": 1999,
                    "currency": "USD"
                },
                "variant_count": 12,
                "total_available": 45,
                "in_stock": True
            }
        }


class ProductDetailResponse(ProductBase):
    """Complete product details"""
    id: int = Field(description="Unique product identifier")
    created_at: datetime = Field(description="Product creation timestamp")
    variants: List[ProductVariantResponse] = Field(description="Product variants")
    min_price: Optional[MoneyField] = Field(default=None, description="Minimum price")
    max_price: Optional[MoneyField] = Field(default=None, description="Maximum price")
    total_available_quantity: int = Field(ge=0, description="Total available inventory")
    in_stock: bool = Field(description="Whether product has available inventory")
    variant_count: int = Field(ge=0, description="Number of variants")
    
    class Config:
        schema_extra = {
            "example": {
                "id": 456,
                "sku": "SHIRT-001",
                "title": "Classic Cotton T-Shirt",
                "description": "Comfortable, high-quality cotton t-shirt perfect for everyday wear.",
                "category_id": 1,
                "created_at": "2026-01-01T12:00:00Z",
                "min_price": {"cents": 1999, "currency": "USD"},
                "max_price": {"cents": 2999, "currency": "USD"},
                "total_available_quantity": 45,
                "in_stock": True,
                "variant_count": 12,
                "variants": [
                    {
                        "variant_id": 123,
                        "variant_sku": "SHIRT-RED-M",
                        "price": {"cents": 2999, "currency": "USD"},
                        "attributes": {"color": "red", "size": "M"},
                        "available": 10,
                        "reserved": 2,
                        "in_stock": True,
                        "available_quantity": 8
                    }
                ]
            }
        }


class ProductListRequest(PaginationRequest):
    """Request parameters for listing products"""
    category_id: Optional[int] = Field(default=None, description="Filter by category")
    search: Optional[str] = Field(default=None, min_length=2, max_length=100, description="Search query")
    min_price_cents: Optional[int] = Field(default=None, ge=0, description="Minimum price filter in cents")
    max_price_cents: Optional[int] = Field(default=None, ge=0, description="Maximum price filter in cents")
    has_inventory: Optional[bool] = Field(default=None, description="Filter by inventory availability")
    
    @root_validator
    def validate_price_range(cls, values):
        """Ensure min_price <= max_price"""
        min_price = values.get('min_price_cents')
        max_price = values.get('max_price_cents')
        
        if min_price is not None and max_price is not None:
            if min_price > max_price:
                raise ValueError('min_price_cents cannot be greater than max_price_cents')
        
        return values
    
    class Config:
        schema_extra = {
            "example": {
                "limit": 20,
                "after": 100,
                "category_id": 1,
                "search": "cotton shirt",
                "min_price_cents": 1000,
                "max_price_cents": 5000,
                "has_inventory": True
            }
        }


class ProductListResponse(BaseModel):
    """Response for product listing endpoints"""
    data: List[ProductSummaryResponse] = Field(description="List of products")
    pagination: PaginationResponse = Field(description="Pagination metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "data": [
                    {
                        "product_id": 456,
                        "product_sku": "SHIRT-001",
                        "title": "Classic Cotton T-Shirt",
                        "min_price": {"cents": 1999, "currency": "USD"},
                        "variant_count": 12,
                        "total_available": 45,
                        "in_stock": True
                    }
                ],
                "pagination": {
                    "limit": 20,
                    "count": 1,
                    "has_more": False,
                    "next_cursor": None
                }
            }
        }


class ProductSearchRequest(BaseModel):
    """Request for product search endpoint"""
    query: str = Field(min_length=2, max_length=100, description="Search query")
    limit: int = Field(default=20, ge=1, le=50, description="Number of results")
    
    @validator('query')
    def validate_search_query(cls, v):
        # Remove extra whitespace and validate
        v = v.strip()
        if len(v) < 2:
            raise ValueError('Search query must be at least 2 characters')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "query": "cotton shirt",
                "limit": 10
            }
        }


class InventoryUpdateRequest(BaseModel):
    """Request to update product variant inventory"""
    available: int = Field(ge=0, description="Available inventory quantity")
    reserved: int = Field(default=0, ge=0, description="Reserved inventory quantity")
    
    class Config:
        schema_extra = {
            "example": {
                "available": 25,
                "reserved": 5
            }
        }