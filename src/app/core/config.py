import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    url: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False  # Log SQL queries
    
@dataclass
class RedisConfig:
    """Redis configuration for caching"""
    url: str
    decode_responses: bool = True
    socket_timeout: int = 30


@dataclass
class APIConfig:
    """API-specific configuration"""
    version: str = "v1"
    title: str = "E-commerce API"
    description: str = "Scalable e-commerce service"
    rate_limit_per_minute: int = 100
    max_page_size: int = 100
    default_page_size: int = 20


@dataclass
class SecurityConfig:
    """Security-related configuration"""
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    password_hash_rounds: int = 12


@dataclass
class AppConfig:
    """Application configuration"""
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 5000
    environment: str = "development"  # development, staging, production
    log_level: str = "INFO"
    
class Config:
    def __init(self):
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # Database configuration
        self.database = DatabaseConfig(
            url=os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/ecommerce"),
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
            echo=os.getenv("DB_ECHO", "false").lower() == "true"
        )
        
        # Redis configuration
        self.redis = RedisConfig(
            url=os.getenv("REDIS_URL", "redis://localhost:6379/0")
        )
        
        # API configuration
        self.api = APIConfig(
            rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "100")),
            max_page_size=int(os.getenv("MAX_PAGE_SIZE", "100")),
            default_page_size=int(os.getenv("DEFAULT_PAGE_SIZE", "20"))
        )
        
        # Security configuration
        self.security = SecurityConfig(
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production"),
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            jwt_expiration_hours=int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
        )
        
        # App configuration
        self.app = AppConfig(
            debug=os.getenv("DEBUG", "false").lower() == "true",
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "5000")),
            environment=self.environment,
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )
        
    @property
    def is_development(self) -> bool:
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
        
    def validate(self) -> None:
        """Validate critical configuration"""
        if self.is_production and self.security.jwt_secret_key == "your-secret-key-change-in-production":
            raise ValueError("JWT_SECRET_KEY must be set in production")
        
        if not self.database.url:
            raise ValueError("DATABASE_URL is required")
        
config=Config()