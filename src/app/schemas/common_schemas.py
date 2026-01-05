from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from decimal import Decimal
from enum import Enum


class PaginationRequest(BaseModel):
    """Standard pagination parameters for list endpoints"""
    limit: int = Field(default=20, ge=1, le=100, description="Number of items to return (1-100)")
    after: Optional[int] = Field(default=None, description="Cursor for pagination - ID to start after")
    
    class Config:
        schema_extra = {
            "example": {
                "limit": 20,
                "after": 123
            }
        }


class PaginationResponse(BaseModel):
    """Standard pagination metadata for responses"""
    limit: int = Field(description="Number of items requested")
    count: int = Field(description="Number of items returned")
    has_more: bool = Field(description="Whether there are more items available")
    next_cursor: Optional[int] = Field(default=None, description="Cursor for next page")
    
    class Config:
        schema_extra = {
            "example": {
                "limit": 20,
                "count": 20,
                "has_more": True,
                "next_cursor": 145
            }
        }


class SuccessResponse(BaseModel):
    """Standard successful API response wrapper"""
    success: bool = Field(default=True, description="Whether the operation was successful")
    message: Optional[str] = Field(default=None, description="Human-readable message")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    request_id: Optional[str] = Field(default=None, description="Unique request identifier")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "timestamp": "2026-01-03T10:30:00Z",
                "request_id": "uuid-here"
            }
        }


class ErrorDetail(BaseModel):
    """Individual error detail"""
    field: Optional[str] = Field(default=None, description="Field that caused the error")
    message: str = Field(description="Error message")
    code: Optional[str] = Field(default=None, description="Error code")


class ErrorResponse(BaseModel):
    """Standard error response format"""
    success: bool = Field(default=False, description="Always false for errors")
    error: Dict[str, Any] = Field(description="Error information")
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = Field(default=None)
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input data",
                    "details": [
                        {
                            "field": "email",
                            "message": "Invalid email format",
                            "code": "INVALID_EMAIL"
                        }
                    ]
                },
                "timestamp": "2026-01-03T10:30:00Z",
                "request_id": "uuid-here"
            }
        }


class MoneyField(BaseModel):
    """Standardized money representation"""
    cents: int = Field(description="Amount in cents")
    currency: str = Field(default="USD", description="Currency code")
    
    @property
    def dollars(self) -> Decimal:
        """Convert cents to dollars"""
        return Decimal(self.cents) / 100
    
    @validator('cents')
    def validate_cents(cls, v):
        if v < 0:
            raise ValueError('Amount cannot be negative')
        return v
    
    @validator('currency')
    def validate_currency(cls, v):
        # Simple validation - in production, use proper currency codes
        if len(v) != 3:
            raise ValueError('Currency must be 3-character code')
        return v.upper()
    
    def to_display_string(self) -> str:
        """Format for display"""
        return f"${self.dollars:.2f}"
    
    class Config:
        schema_extra = {
            "example": {
                "cents": 1299,
                "currency": "USD"
            }
        }


class SortOrder(str, Enum):
    """Standard sort order options"""
    ASC = "asc"
    DESC = "desc"


class SortField(BaseModel):
    """Sort specification"""
    field: str = Field(description="Field to sort by")
    order: SortOrder = Field(default=SortOrder.ASC, description="Sort order")