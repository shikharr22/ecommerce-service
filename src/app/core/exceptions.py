from typing import Optional, Dict, Any, List
import traceback
import sys


class BaseAPIException(Exception):
    def __init__( self, 
        message: str, 
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        internal_message: Optional[str] = None):
        self.message = message  # User-facing message
        self.internal_message = internal_message or message  # Internal/debug message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__.replace('Error', '').upper()
        self.details = details or {}
        
        # Capture stack trace for debugging
        self.traceback = traceback.format_exc() if sys.exc_info()[0] else None
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response"""
        return {
            "success": False,
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details
            }
        }
        
class ValidationError(BaseAPIException):
    """Raised when request validation fails"""
    
    def __init__(
        self, 
        message: str = "Validation failed", 
        field_errors: Optional[List[Dict[str, str]]] = None
    ):
        details = {"field_errors": field_errors} if field_errors else {}
        super().__init__(message, 400, "VALIDATION_ERROR", details)


class NotFoundError(BaseAPIException):
    """Raised when a requested resource is not found"""
    
    def __init__(self, resource: str = "Resource", resource_id: Optional[str] = None):
        message = f"{resource} not found"
        if resource_id:
            message += f" with ID: {resource_id}"
        super().__init__(message, 404, "NOT_FOUND")


class UnauthorizedError(BaseAPIException):
    """Raised when user is not authenticated"""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, 401, "UNAUTHORIZED")


class ForbiddenError(BaseAPIException):
    """Raised when user lacks permission for the requested action"""
    
    def __init__(self, message: str = "Access forbidden"):
        super().__init__(message, 403, "FORBIDDEN")


class ConflictError(BaseAPIException):
    """Raised when there's a conflict with the current state"""
    
    def __init__(self, message: str = "Resource conflict", conflict_field: Optional[str] = None):
        details = {"conflict_field": conflict_field} if conflict_field else {}
        super().__init__(message, 409, "CONFLICT", details)


class BusinessLogicError(BaseAPIException):
    """Raised when business rules are violated"""
    
    def __init__(self, message: str, rule: Optional[str] = None):
        details = {"violated_rule": rule} if rule else {}
        super().__init__(message, 422, "BUSINESS_LOGIC_ERROR", details)


class ExternalServiceError(BaseAPIException):
    """Raised when external service calls fail"""
    
    def __init__(self, service_name: str, message: str = "External service unavailable"):
        details = {"service": service_name}
        super().__init__(message, 503, "EXTERNAL_SERVICE_ERROR", details)


class RateLimitError(BaseAPIException):
    """Raised when rate limit is exceeded"""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        details = {"retry_after_seconds": retry_after} if retry_after else {}
        super().__init__(message, 429, "RATE_LIMIT_ERROR", details)


class DatabaseError(BaseAPIException):
    """Raised when database operations fail"""
    
    def __init__(self, message: str = "Database operation failed", operation: Optional[str] = None):
        # Don't expose internal database details to users
        user_message = "An internal error occurred. Please try again later."
        details = {"operation": operation} if operation else {}
        super().__init__(
            user_message, 
            500, 
            "DATABASE_ERROR", 
            details,
            internal_message=message  # Keep original message for logging
        )


class InternalServerError(BaseAPIException):
    """Raised for unexpected internal errors"""
    
    def __init__(self, message: str = "An unexpected error occurred", context: Optional[Dict[str, Any]] = None):
        # Don't expose internal details to users
        user_message = "An internal server error occurred. Please try again later."
        super().__init__(
            user_message, 
            500, 
            "INTERNAL_ERROR", 
            context or {},
            internal_message=message
        )