from datetime import datetime, timezone, timedelta
from typing import Optional, Union
import pytz
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta

class DateUtils:
    """
    Centralized date/time utilities for consistent handling across the application
    
    Key Features:
    - Timezone-aware datetime handling
    - Business day calculations
    - Date formatting and parsing
    - Time range validations
    """
    
    # Standard timezone definitions
    UTC = timezone.utc
    EST = pytz.timezone('US/Eastern')
    PST = pytz.timezone('US/Pacific')
    
    # Business constants
    BUSINESS_HOUR_START = 9  # 9 AM
    BUSINESS_HOUR_END = 17   # 5 PM
    WEEKEND_DAYS = {5, 6}    # Saturday, Sunday (0=Monday)
    
    @classmethod
    def now_utc(cls) -> datetime:
        """Get current UTC datetime - always use this for database storage"""
        return datetime.now(cls.UTC)
    
    @classmethod
    def now_local(cls, timezone_name: str = 'US/Eastern') -> datetime:
        """Get current datetime in specified timezone"""
        tz = pytz.timezone(timezone_name)
        return datetime.now(tz)
    
    @classmethod
    def to_utc(cls, dt: datetime, source_timezone: Optional[str] = None) -> datetime:
        """
        Convert datetime to UTC
        
        Args:
            dt: datetime to convert
            source_timezone: source timezone (if dt is naive)
        """
        if dt.tzinfo is None:
            # Naive datetime - assume source timezone
            if source_timezone:
                tz = pytz.timezone(source_timezone)
                dt = tz.localize(dt)
            else:
                # Assume UTC if no timezone specified
                dt = dt.replace(tzinfo=cls.UTC)
        
        return dt.astimezone(cls.UTC)
    
    @classmethod
    def from_utc(cls, dt: datetime, target_timezone: str) -> datetime:
        """Convert UTC datetime to target timezone"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=cls.UTC)
        
        target_tz = pytz.timezone(target_timezone)
        return dt.astimezone(target_tz)
    
    @classmethod
    def parse_iso_string(cls, date_string: str) -> datetime:
        """
        Parse ISO 8601 date string to datetime
        
        Handles various formats:
        - 2026-01-03T10:30:00Z
        - 2026-01-03T10:30:00+00:00
        - 2026-01-03T10:30:00.123456Z
        """
        try:
            # Use dateutil parser for flexibility
            parsed_dt = date_parser.isoparse(date_string)
            
            # Ensure timezone awareness
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=cls.UTC)
            
            return parsed_dt
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid date format: {date_string}") from e
    
    @classmethod
    def to_iso_string(cls, dt: datetime) -> str:
        """Convert datetime to ISO 8601 string"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=cls.UTC)
        
        return dt.isoformat()
    
    @classmethod
    def format_for_display(
        cls, 
        dt: datetime, 
        timezone_name: str = 'US/Eastern',
        format_string: str = '%Y-%m-%d %I:%M %p %Z'
    ) -> str:
        """
        Format datetime for user display
        
        Default format: "2026-01-03 10:30 AM EST"
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=cls.UTC)
        
        target_tz = pytz.timezone(timezone_name)
        local_dt = dt.astimezone(target_tz)
        
        return local_dt.strftime(format_string)
    
    @classmethod
    def is_business_hours(
        cls, 
        dt: datetime, 
        timezone_name: str = 'US/Eastern'
    ) -> bool:
        """Check if datetime falls within business hours"""
        local_dt = cls.from_utc(dt, timezone_name)
        
        # Check if weekend
        if local_dt.weekday() in cls.WEEKEND_DAYS:
            return False
        
        # Check business hours
        hour = local_dt.hour
        return cls.BUSINESS_HOUR_START <= hour < cls.BUSINESS_HOUR_END
    
    @classmethod
    def next_business_day(
        cls, 
        dt: datetime, 
        timezone_name: str = 'US/Eastern'
    ) -> datetime:
        """Get next business day from given date"""
        local_dt = cls.from_utc(dt, timezone_name)
        
        # Start from next day
        next_day = local_dt + timedelta(days=1)
        
        # Skip weekends
        while next_day.weekday() in cls.WEEKEND_DAYS:
            next_day += timedelta(days=1)
        
        # Set to business hour start
        business_start = next_day.replace(
            hour=cls.BUSINESS_HOUR_START,
            minute=0,
            second=0,
            microsecond=0
        )
        
        return cls.to_utc(business_start, timezone_name)
    
    @classmethod
    def days_between(cls, start_date: datetime, end_date: datetime) -> int:
        """Calculate number of days between two dates"""
        # Normalize to dates only
        start = start_date.date() if isinstance(start_date, datetime) else start_date
        end = end_date.date() if isinstance(end_date, datetime) else end_date
        
        return (end - start).days
    
    @classmethod
    def months_between(cls, start_date: datetime, end_date: datetime) -> int:
        """Calculate number of months between two dates"""
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        delta = relativedelta(end_date, start_date)
        return delta.years * 12 + delta.months
    
    @classmethod
    def is_expired(cls, expiry_date: datetime, buffer_minutes: int = 0) -> bool:
        """
        Check if a date has expired
        
        Args:
            expiry_date: The expiration datetime
            buffer_minutes: Grace period in minutes
        """
        now = cls.now_utc()
        buffer = timedelta(minutes=buffer_minutes)
        return now > (expiry_date + buffer)
    
    @classmethod
    def time_until_expiry(cls, expiry_date: datetime) -> timedelta:
        """Calculate time remaining until expiry"""
        now = cls.now_utc()
        return expiry_date - now
    
    @classmethod
    def create_expiry_time(cls, duration_minutes: int) -> datetime:
        """Create expiry datetime from current time + duration"""
        return cls.now_utc() + timedelta(minutes=duration_minutes)
    
    @classmethod
    def validate_date_range(
        cls, 
        start_date: datetime, 
        end_date: datetime,
        max_range_days: Optional[int] = None
    ) -> bool:
        """
        Validate a date range
        
        Business rules:
        - Start date must be before end date
        - Range cannot exceed maximum days if specified
        """
        if start_date >= end_date:
            return False
        
        if max_range_days:
            days_diff = cls.days_between(start_date, end_date)
            if days_diff > max_range_days:
                return False
        
        return True
    
    @classmethod
    def get_start_of_day(cls, dt: datetime) -> datetime:
        """Get start of day (00:00:00) for given datetime"""
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    
    @classmethod
    def get_end_of_day(cls, dt: datetime) -> datetime:
        """Get end of day (23:59:59.999999) for given datetime"""
        return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    @classmethod
    def get_quarter_start(cls, dt: datetime) -> datetime:
        """Get start of quarter for given datetime"""
        quarter = (dt.month - 1) // 3 + 1
        quarter_start_month = (quarter - 1) * 3 + 1
        
        return dt.replace(
            month=quarter_start_month,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )