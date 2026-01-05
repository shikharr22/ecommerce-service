import re
import uuid
from typing import Any, Union, Optional, List, Dict
from decimal import Decimal, InvalidOperation
from email_validator import validate_email, EmailNotValidError
class ValidationUtils:
    """
    Comprehensive validation utilities for data integrity
    
    Features:
    - Email validation with DNS checking
    - Phone number formatting and validation
    - Business identifier validation (SKU, order numbers)
    - Financial data validation
    - Input sanitization
    """
    
    # Regex patterns for common validations
    PATTERNS = {
        'sku': re.compile(r'^[A-Z0-9][A-Z0-9\-]{2,49}$'),  # SKU: 3-50 chars, alphanumeric + hyphens
        'phone_us': re.compile(r'^\+?1?[2-9]\d{2}[2-9]\d{2}\d{4}$'),  # US phone numbers
        'postal_code_us': re.compile(r'^\d{5}(-\d{4})?$'),  # US ZIP codes
        'credit_card': re.compile(r'^\d{13,19}$'),  # Credit card numbers
        'order_number': re.compile(r'^ORD-\d{4}-\d{6}$'),  # Format: ORD-YYYY-NNNNNN
        'username': re.compile(r'^[a-zA-Z0-9_][a-zA-Z0-9._-]{2,29}$'),  # Username: 3-30 chars
        'hex_color': re.compile(r'^#[0-9A-Fa-f]{6}$'),  # Hex color codes
        'url': re.compile(r'^https?://[^\s<>"{}|\\^`[\]]+$'),  # Basic URL validation
    }
    
    # Business-specific validation rules
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 128
    MAX_TEXT_LENGTH = 2000
    MAX_TITLE_LENGTH = 500
    MIN_PRICE_CENTS = 1
    MAX_PRICE_CENTS = 99999999  # $999,999.99
    
    @classmethod
    def validate_email(cls, email: str, check_deliverability: bool = False) -> bool:
        """
        Validate email address with optional DNS checking
        
        Args:
            email: Email address to validate
            check_deliverability: Whether to check DNS records
        """
        try:
            # Use email-validator library for comprehensive validation
            valid = validate_email(
                email, 
                check_deliverability=check_deliverability
            )
            return True
        except EmailNotValidError:
            return False
    
    @classmethod
    def normalize_email(cls, email: str) -> str:
        """Normalize email address for consistent storage"""
        try:
            validated = validate_email(email)
            return validated.email.lower()
        except EmailNotValidError:
            raise ValueError(f"Invalid email address: {email}")
    
    @classmethod
    def validate_phone_number(cls, phone: str, country: str = 'US') -> bool:
        """Validate phone number format"""
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)
        
        if country == 'US':
            # US phone number validation
            if len(digits_only) == 10:
                digits_only = '1' + digits_only  # Add country code
            
            return cls.PATTERNS['phone_us'].match(digits_only) is not None
        
        # Add other country validations as needed
        return len(digits_only) >= 10
    
    @classmethod
    def format_phone_number(cls, phone: str, country: str = 'US') -> str:
        """Format phone number for display"""
        digits_only = re.sub(r'\D', '', phone)
        
        if country == 'US' and len(digits_only) >= 10:
            if len(digits_only) == 11 and digits_only.startswith('1'):
                digits_only = digits_only[1:]  # Remove country code for formatting
            
            if len(digits_only) == 10:
                return f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}"
        
        return phone  # Return original if can't format
    
    @classmethod
    def validate_password(cls, password: str) -> Dict[str, bool]:
        """
        Comprehensive password validation
        
        Returns dict with validation results for each rule
        """
        results = {
            'min_length': len(password) >= cls.MIN_PASSWORD_LENGTH,
            'max_length': len(password) <= cls.MAX_PASSWORD_LENGTH,
            'has_uppercase': bool(re.search(r'[A-Z]', password)),
            'has_lowercase': bool(re.search(r'[a-z]', password)),
            'has_digit': bool(re.search(r'\d', password)),
            'has_special': bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password)),
            'no_common_patterns': not cls._has_common_patterns(password)
        }
        
        results['is_valid'] = all(results.values())
        return results
    
    @classmethod
    def validate_sku(cls, sku: str) -> bool:
        """Validate product SKU format"""
        return cls.PATTERNS['sku'].match(sku.upper()) is not None
    
    @classmethod
    def normalize_sku(cls, sku: str) -> str:
        """Normalize SKU for consistent storage"""
        normalized = sku.strip().upper()
        
        if not cls.validate_sku(normalized):
            raise ValueError(f"Invalid SKU format: {sku}")
        
        return normalized
    
    @classmethod
    def validate_price_cents(cls, price_cents: int) -> bool:
        """Validate price in cents"""
        return cls.MIN_PRICE_CENTS <= price_cents <= cls.MAX_PRICE_CENTS
    
    @classmethod
    def validate_quantity(cls, quantity: int, max_quantity: int = 99) -> bool:
        """Validate item quantity"""
        return 1 <= quantity <= max_quantity
    
    @classmethod
    def validate_postal_code(cls, postal_code: str, country: str = 'US') -> bool:
        """Validate postal code format"""
        if country == 'US':
            return cls.PATTERNS['postal_code_us'].match(postal_code) is not None
        
        # Add other country validations
        return len(postal_code.strip()) >= 3
    
    @classmethod
    def validate_uuid(cls, uuid_string: str) -> bool:
        """Validate UUID format"""
        try:
            uuid.UUID(uuid_string)
            return True
        except (ValueError, TypeError):
            return False
    
    @classmethod
    def validate_url(cls, url: str) -> bool:
        """Basic URL validation"""
        return cls.PATTERNS['url'].match(url) is not None
    
    @classmethod
    def sanitize_text(cls, text: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize text input for safe storage and display
        
        - Strips whitespace
        - Removes potentially harmful characters
        - Enforces length limits
        """
        if not isinstance(text, str):
            return str(text)
        
        # Basic sanitization
        sanitized = text.strip()
        
        # Remove control characters except newlines and tabs
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', sanitized)
        
        # Enforce length limit
        if max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized
    
    @classmethod
    def sanitize_html(cls, html: str) -> str:
        """
        Basic HTML sanitization (for production, use a proper library like bleach)
        """
        # Remove script tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove potentially dangerous attributes
        html = re.sub(r'\s(on\w+|javascript:)[^>]*', '', html, flags=re.IGNORECASE)
        
        return html
    
    @classmethod
    def validate_json_structure(cls, data: Any, required_fields: List[str]) -> bool:
        """Validate that JSON data has required fields"""
        if not isinstance(data, dict):
            return False
        
        return all(field in data for field in required_fields)
    
    @classmethod
    def validate_decimal(cls, value: Union[str, Decimal], max_digits: int = 10, decimal_places: int = 2) -> bool:
        """Validate decimal number format"""
        try:
            if isinstance(value, str):
                decimal_val = Decimal(value)
            else:
                decimal_val = value
            
            # Check total digits
            sign, digits, exponent = decimal_val.as_tuple()
            total_digits = len(digits)
            
            if total_digits > max_digits:
                return False
            
            # Check decimal places
            if exponent < -decimal_places:
                return False
            
            return True
            
        except (InvalidOperation, ValueError):
            return False
    
    @classmethod
    def validate_business_identifier(cls, identifier: str, identifier_type: str) -> bool:
        """Validate business-specific identifiers"""
        patterns = {
            'order_number': cls.PATTERNS['order_number'],
            'sku': cls.PATTERNS['sku'],
            'username': cls.PATTERNS['username']
        }
        
        pattern = patterns.get(identifier_type.lower())
        if not pattern:
            return False
        
        return pattern.match(identifier) is not None
    
    @classmethod
    def _has_common_patterns(cls, password: str) -> bool:
        """Check for common weak password patterns"""
        common_patterns = [
            r'123456',
            r'password',
            r'qwerty',
            r'abc123',
            r'(\w)\1{2,}',  # Repeated characters (aaa, 111)
        ]
        
        password_lower = password.lower()
        
        for pattern in common_patterns:
            if re.search(pattern, password_lower):
                return True
        
        return False
    
    @classmethod
    def batch_validate_emails(cls, emails: List[str]) -> Dict[str, bool]:
        """Validate multiple emails efficiently"""
        results = {}
        
        for email in emails:
            try:
                results[email] = cls.validate_email(email)
            except Exception:
                results[email] = False
        
        return results
    
    @classmethod
    def validate_credit_card_number(cls, card_number: str) -> bool:
        """
        Validate credit card number using Luhn algorithm
        
        Note: This is for format validation only, not for payment processing
        """
        # Remove spaces and hyphens
        number = re.sub(r'[\s-]', '', card_number)
        
        # Check basic format
        if not cls.PATTERNS['credit_card'].match(number):
            return False
        
        # Luhn algorithm
        def luhn_check(num: str) -> bool:
            digits = [int(d) for d in num]
            checksum = 0
            
            # Process every second digit from right
            for i in range(len(digits) - 2, -1, -2):
                doubled = digits[i] * 2
                checksum += doubled if doubled < 10 else doubled - 9
            
            # Add remaining digits
            for i in range(len(digits) - 1, -1, -2):
                checksum += digits[i]
            
            return checksum % 10 == 0
        
        return luhn_check(number)