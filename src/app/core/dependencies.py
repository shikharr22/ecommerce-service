from typing import TypeVar, Type, Dict, Any, Callable
from functools import lru_cache
from app.core.config import config

T=TypeVar('T')

class DependencyContainer:
    """Simple dependency injection container"""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
    
    def register_singleton(self, service_class: Type[T], instance: T) -> None:
        """Register a singleton instance"""
        key = self._get_service_key(service_class)
        self._services[key] = instance
    
    def register_factory(self, service_class: Type[T], factory: Callable[[], T]) -> None:
        """Register a factory function for creating instances"""
        key = self._get_service_key(service_class)
        self._factories[key] = factory
    
    def get(self, service_class: Type[T]) -> T:
        """Get service instance"""
        key = self._get_service_key(service_class)
        
        # Check if singleton exists
        if key in self._services:
            return self._services[key]
        
        # Check if factory exists
        if key in self._factories:
            instance = self._factories[key]()
            # Cache as singleton
            self._services[key] = instance
            return instance
        
        raise ValueError(f"Service {service_class.__name__} not registered")
    
    def _get_service_key(self, service_class: Type[T]) -> str:
        """Get unique key for service class"""
        return f"{service_class.__module__}.{service_class.__qualname__}"


# Global container instance
container = DependencyContainer()


@lru_cache()
def get_config():
    """Get application configuration"""
    return config


def get_container():
    """Get dependency container"""
    return container