from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class UserRole(Enum):
    """User role enumeration"""
    CUSTOMER = "customer"
    ADMIN = "admin"
    VENDOR = "vendor"


class UserStatus(Enum):
    """User status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    
@dataclass
class User:
    """Represents a user in the system"""
    id: int
    email: str
    first_name: str
    last_name: str
    role: UserRole
    status: UserStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def is_active(self) -> bool:
        """Check if user is active"""
        return self.status == UserStatus.ACTIVE
    
    @property
    def is_admin(self) -> bool:
        """Check if user has admin role"""
        return self.role == UserRole.ADMIN
    
    @property
    def is_customer(self) -> bool:
        """Check if user is a customer"""
        return self.role == UserRole.CUSTOMER
    
    @property
    def is_vendor(self) -> bool:
        """Check if user is a vendor"""
        return self.role == UserRole.VENDOR
    
    def can_access_admin_panel(self) -> bool:
        """Check if user can access admin features"""
        return self.is_active and (self.is_admin or self.is_vendor)
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = {
            "id": self.id,
            "email": self.email if include_sensitive else None,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "role": self.role.value,
            "status": self.status.value,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None
        }
        
        # Remove None values if not including sensitive data
        if not include_sensitive:
            data = {k: v for k, v in data.items() if v is not None}
        
        return data
    
@dataclass
class UserProfile:
    """Extended user profile information"""
    user_id: int
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    
    @property
    def has_complete_address(self) -> bool:
        """Check if user has a complete address"""
        required_fields = [self.address_line1, self.city, self.state, self.postal_code, self.country]
        return all(field is not None and field.strip() for field in required_fields)
    
    @property
    def formatted_address(self) -> Optional[str]:
        """Get formatted address string"""
        if not self.has_complete_address:
            return None
        
        address_parts = [self.address_line1]
        if self.address_line2:
            address_parts.append(self.address_line2)
        address_parts.extend([self.city, self.state, self.postal_code, self.country])
        
        return ", ".join(part for part in address_parts if part)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "user_id": self.user_id,
            "phone": self.phone,
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code,
            "country": self.country,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "has_complete_address": self.has_complete_address,
            "formatted_address": self.formatted_address
        }