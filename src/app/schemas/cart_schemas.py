from pydantic import BaseModel, Field, validator
from typing import List, Optional
from app.schemas.common_schemas import MoneyField


class CartItemBase(BaseModel):
    """Base cart item data"""
    variant_id: int = Field(description="Product variant identifier")
    quantity: int = Field(ge=1, le=99, description="Quantity (1-99)")
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be positive')
        if v > 99:
            raise ValueError('Quantity cannot exceed 99 items')
        return v


class AddToCartRequest(CartItemBase):
    """Request to add item to cart"""
    class Config:
        schema_extra = {
            "example": {
                "variant_id": 123,
                "quantity": 2
            }
        }


class UpdateCartItemRequest(BaseModel):
    """Request to update cart item quantity"""
    quantity: int = Field(ge=0, le=99, description="New quantity (0 to remove)")
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v < 0:
            raise ValueError('Quantity cannot be negative')
        if v > 99:
            raise ValueError('Quantity cannot exceed 99 items')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "quantity": 3
            }
        }


class CartItemResponse(BaseModel):
    """Cart item in API responses"""
    cart_item_id: int = Field(description="Unique cart item identifier")
    variant_id: int = Field(description="Product variant identifier")
    variant_sku: str = Field(description="Variant SKU")
    product_id: int = Field(description="Product identifier")
    product_sku: str = Field(description="Product SKU")
    product_title: str = Field(description="Product title")
    price: MoneyField = Field(description="Price when added to cart")
    quantity: int = Field(description="Quantity in cart")
    subtotal: MoneyField = Field(description="Line item subtotal")
    
    class Config:
        schema_extra = {
            "example": {
                "cart_item_id": 789,
                "variant_id": 123,
                "variant_sku": "SHIRT-RED-M",
                "product_id": 456,
                "product_sku": "SHIRT-001",
                "product_title": "Classic Cotton T-Shirt",
                "price": {"cents": 2999, "currency": "USD"},
                "quantity": 2,
                "subtotal": {"cents": 5998, "currency": "USD"}
            }
        }


class CartResponse(BaseModel):
    """Complete cart information"""
    cart_id: int = Field(description="Unique cart identifier")
    user_id: int = Field(description="User identifier")
    total_items: int = Field(ge=0, description="Number of unique items")
    total_quantity: int = Field(ge=0, description="Total quantity of all items")
    total: MoneyField = Field(description="Cart total amount")
    is_empty: bool = Field(description="Whether cart is empty")
    items: List[CartItemResponse] = Field(description="Cart items")
    
    class Config:
        schema_extra = {
            "example": {
                "cart_id": 1001,
                "user_id": 42,
                "total_items": 2,
                "total_quantity": 3,
                "total": {"cents": 8997, "currency": "USD"},
                "is_empty": False,
                "items": [
                    {
                        "cart_item_id": 789,
                        "variant_id": 123,
                        "variant_sku": "SHIRT-RED-M",
                        "product_id": 456,
                        "product_sku": "SHIRT-001",
                        "product_title": "Classic Cotton T-Shirt",
                        "price": {"cents": 2999, "currency": "USD"},
                        "quantity": 2,
                        "subtotal": {"cents": 5998, "currency": "USD"}
                    }
                ]
            }
        }


class CartSummaryResponse(BaseModel):
    """Lightweight cart information"""
    cart_id: int = Field(description="Unique cart identifier")
    user_id: int = Field(description="User identifier")
    total_items: int = Field(ge=0, description="Number of unique items")
    total_quantity: int = Field(ge=0, description="Total quantity of all items")
    total: MoneyField = Field(description="Cart total amount")
    is_empty: bool = Field(description="Whether cart is empty")
    
    class Config:
        schema_extra = {
            "example": {
                "cart_id": 1001,
                "user_id": 42,
                "total_items": 2,
                "total_quantity": 3,
                "total": {"cents": 8997, "currency": "USD"},
                "is_empty": False
            }
        }


class BulkCartUpdateRequest(BaseModel):
    """Request to update multiple cart items at once"""
    updates: List[dict] = Field(description="List of cart item updates")
    
    @validator('updates')
    def validate_updates(cls, v):
        if len(v) > 50:
            raise ValueError('Cannot update more than 50 items at once')
        
        for update in v:
            if 'cart_item_id' not in update or 'quantity' not in update:
                raise ValueError('Each update must have cart_item_id and quantity')
            
            if update['quantity'] < 0 or update['quantity'] > 99:
                raise ValueError('Quantity must be between 0 and 99')
        
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "updates": [
                    {"cart_item_id": 789, "quantity": 3},
                    {"cart_item_id": 790, "quantity": 0}  # Remove item
                ]
            }
        }