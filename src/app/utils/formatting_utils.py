from typing import Optional, Dict, Any, Union
from decimal import Decimal
import json
import re


class FormattingUtils:
    """
    Data formatting utilities for consistent display and API responses
    
    Features:
    - Money formatting with currency support
    - Text formatting and truncation
    - JSON serialization helpers
    - Number formatting with localization
    - Address formatting
    """
    
    # Currency symbols and formatting rules
    CURRENCY_FORMATS = {
        'USD': {'symbol': '$', 'decimal_places': 2, 'symbol_position': 'before'},
        'EUR': {'symbol': '€', 'decimal_places': 2, 'symbol_position': 'after'},
        'GBP': {'symbol': '£', 'decimal_places': 2, 'symbol_position': 'before'},
        'JPY': {'symbol': '¥', 'decimal_places': 0, 'symbol_position': 'before'},
    }
    
    # Text formatting constants
    DEFAULT_TRUNCATE_LENGTH = 100
    ELLIPSIS = '...'
    
    @classmethod
    def format_money(
        cls, 
        amount_cents: int, 
        currency: str = 'USD',
        include_symbol: bool = True,
        include_currency_code: bool = False
    ) -> str:
        """
        Format money amount for display
        
        Args:
            amount_cents: Amount in cents
            currency: Currency code (USD, EUR, etc.)
            include_symbol: Whether to include currency symbol
            include_currency_code: Whether to include currency code
        
        Examples:
            format_money(1299, 'USD') -> "$12.99"
            format_money(1299, 'USD', include_currency_code=True) -> "$12.99 USD"
        """
        currency_config = cls.CURRENCY_FORMATS.get(currency, cls.CURRENCY_FORMATS['USD'])
        
        # Convert cents to main currency unit
        decimal_places = currency_config['decimal_places']
        amount = Decimal(amount_cents) / (10 ** decimal_places)
        
        # Format number with appropriate decimal places
        if decimal_places == 0:
            formatted_amount = f"{amount:,.0f}"
        else:
            formatted_amount = f"{amount:,.{decimal_places}f}"
        
        result = formatted_amount
        
        # Add currency symbol
        if include_symbol:
            symbol = currency_config['symbol']
            if currency_config['symbol_position'] == 'before':
                result = f"{symbol}{formatted_amount}"
            else:
                result = f"{formatted_amount}{symbol}"
        
        # Add currency code
        if include_currency_code:
            result = f"{result} {currency}"
        
        return result
    
    @classmethod
    def format_percentage(cls, decimal_value: float, decimal_places: int = 1) -> str:
        """
        Format decimal as percentage
        
        Examples:
            format_percentage(0.08, 1) -> "8.0%"
            format_percentage(0.125, 2) -> "12.50%"
        """
        percentage = decimal_value * 100
        return f"{percentage:.{decimal_places}f}%"
    
    @classmethod
    def truncate_text(
        cls, 
        text: str, 
        max_length: int = DEFAULT_TRUNCATE_LENGTH,
        ellipsis: str = ELLIPSIS,
        word_boundary: bool = True
    ) -> str:
        """
        Truncate text with ellipsis
        
        Args:
            text: Text to truncate
            max_length: Maximum length before truncation
            ellipsis: String to append when truncated
            word_boundary: Whether to break at word boundaries
        """
        if len(text) <= max_length:
            return text
        
        if word_boundary:
            # Find last space before max_length
            truncate_point = max_length - len(ellipsis)
            last_space = text.rfind(' ', 0, truncate_point)
            
            if last_space > 0:
                return text[:last_space] + ellipsis
        
        # Character-based truncation
        truncate_point = max_length - len(ellipsis)
        return text[:truncate_point] + ellipsis
    
    @classmethod
    def format_phone_display(cls, phone: str) -> str:
        """Format phone number for display"""
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits.startswith('1'):
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        
        return phone  # Return original if can't format
    
    @classmethod
    def format_address(cls, address_components: Dict[str, Optional[str]]) -> str:
        """
        Format address components into single string
        
        Expected components:
        - line1, line2, city, state, postal_code, country
        """
        parts = []
        
        # Address lines
        if address_components.get('line1'):
            parts.append(address_components['line1'])
        
        if address_components.get('line2'):
            parts.append(address_components['line2'])
        
        # City, state, postal code
        city_state_zip = []
        if address_components.get('city'):
            city_state_zip.append(address_components['city'])
        
        if address_components.get('state'):
            city_state_zip.append(address_components['state'])
        
        if address_components.get('postal_code'):
            city_state_zip.append(address_components['postal_code'])
        
        if city_state_zip:
            parts.append(', '.join(city_state_zip))
        
        # Country (if not US)
        country = address_components.get('country', '').upper()
        if country and country != 'US':
            parts.append(country)
        
        return ', '.join(parts)
    
    @classmethod
    def format_name(cls, first_name: str, last_name: str, format_type: str = 'full') -> str:
        """
        Format person's name
        
        Args:
            first_name: First name
            last_name: Last name  
            format_type: 'full', 'last_first', 'initials', 'first_only'
        """
        first = first_name.strip()
        last = last_name.strip()
        
        if format_type == 'full':
            return f"{first} {last}".strip()
        elif format_type == 'last_first':
            return f"{last}, {first}".strip()
        elif format_type == 'initials':
            first_initial = first[0].upper() if first else ''
            last_initial = last[0].upper() if last else ''
            return f"{first_initial}{last_initial}"
        elif format_type == 'first_only':
            return first
        else:
            return f"{first} {last}".strip()
    
    @classmethod
    def format_list_display(
        cls, 
        items: list, 
        max_items: int = 3,
        conjunction: str = 'and'
    ) -> str:
        """
        Format list for display with conjunction
        
        Examples:
            format_list_display(['A', 'B', 'C']) -> "A, B, and C"
            format_list_display(['A', 'B'], conjunction='or') -> "A or B"
        """
        if not items:
            return ""
        
        if len(items) == 1:
            return str(items[0])
        
        if len(items) == 2:
            return f"{items[0]} {conjunction} {items[1]}"
        
        if len(items) <= max_items:
            # "A, B, and C"
            return f"{', '.join(str(item) for item in items[:-1])}, {conjunction} {items[-1]}"
        else:
            # "A, B, and 5 others"
            displayed = items[:max_items]
            remaining_count = len(items) - max_items
            displayed_str = ', '.join(str(item) for item in displayed)
            return f"{displayed_str}, {conjunction} {remaining_count} others"
    
    @classmethod
    def format_file_size(cls, size_bytes: int) -> str:
        """
        Format file size in human-readable format
        
        Examples:
            format_file_size(1024) -> "1.0 KB"
            format_file_size(1048576) -> "1.0 MB"
        """
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(size_bytes)
        
        for unit in units:
            if size < 1024.0:
                if unit == 'B':
                    return f"{int(size)} {unit}"
                else:
                    return f"{size:.1f} {unit}"
            size /= 1024.0
        
        return f"{size:.1f} PB"
    
    @classmethod
    def format_duration(cls, seconds: int) -> str:
        """
        Format duration in human-readable format
        
        Examples:
            format_duration(90) -> "1m 30s"
            format_duration(3665) -> "1h 1m 5s"
        """
        if seconds < 60:
            return f"{seconds}s"
        
        minutes, secs = divmod(seconds, 60)
        if minutes < 60:
            if secs == 0:
                return f"{minutes}m"
            return f"{minutes}m {secs}s"
        
        hours, mins = divmod(minutes, 60)
        if hours < 24:
            parts = [f"{hours}h"]
            if mins > 0:
                parts.append(f"{mins}m")
            if secs > 0:
                parts.append(f"{secs}s")
            return " ".join(parts)
        
        days, hrs = divmod(hours, 24)
        parts = [f"{days}d"]
        if hrs > 0:
            parts.append(f"{hrs}h")
        if mins > 0:
            parts.append(f"{mins}m")
        return " ".join(parts)
    
    @classmethod
    def format_json_pretty(cls, data: Any, indent: int = 2) -> str:
        """Format JSON with pretty printing"""
        return json.dumps(
            data, 
            indent=indent,
            ensure_ascii=False,
            sort_keys=True,
            default=str  # Handle datetime and other non-serializable types
        )
    
    @classmethod
    def format_api_response(
        cls,
        data: Any,
        success: bool = True,
        message: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format standardized API response"""
        response = {
            'success': success,
            'data': data,
            'timestamp': cls._get_current_iso_timestamp()
        }
        
        if message:
            response['message'] = message
        
        if request_id:
            response['request_id'] = request_id
        
        return response
    
    @classmethod
    def format_error_response(
        cls,
        error_code: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format standardized error response"""
        response = {
            'success': False,
            'error': {
                'code': error_code,
                'message': error_message
            },
            'timestamp': cls._get_current_iso_timestamp()
        }
        
        if details:
            response['error']['details'] = details
        
        if request_id:
            response['request_id'] = request_id
        
        return response
    
    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove/replace unsafe characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Remove control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
        
        # Limit length
        if len(sanitized) > 255:
            name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
            max_name_length = 255 - len(ext) - 1 if ext else 255
            sanitized = name[:max_name_length] + ('.' + ext if ext else '')
        
        return sanitized.strip()
    
    @classmethod
    def _get_current_iso_timestamp(cls) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()