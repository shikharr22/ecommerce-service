from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List, Any, Dict, Union
from contextlib import contextmanager
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app.core.exceptions import DatabaseError, NotFoundError
from db import get_connection
import logging

T = TypeVar('T')

logger = logging.getLogger(__name__)


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository providing common database operations.
    Implements Repository Pattern for clean separation of data access logic.
    """
    
    @contextmanager
    def get_db_connection(self):
        """Database connection context manager with error handling"""
        try:
            with get_connection() as conn:
                yield conn
        except SQLAlchemyError as e:
            logger.error(f"Database connection error: {str(e)}")
            raise DatabaseError(f"Database connection failed: {str(e)}")
    
    def execute_query(
        self, 
        query: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute SELECT query and return results as list of dictionaries
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of row dictionaries
            
        Raises:
            DatabaseError: When query execution fails
        """
        try:
            with self.get_db_connection() as conn:
                result = conn.execute(text(query), params or {})
                return [dict(row._mapping) for row in result]
        except SQLAlchemyError as e:
            logger.error(f"Query execution failed: {query}, Error: {str(e)}")
            raise DatabaseError(f"Query execution failed", "SELECT")
    
    def execute_single_query(
        self, 
        query: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Execute query expecting single result
        
        Returns:
            Single row dictionary or None if not found
        """
        try:
            with self.get_db_connection() as conn:
                result = conn.execute(text(query), params or {}).first()
                return dict(result._mapping) if result else None
        except SQLAlchemyError as e:
            logger.error(f"Single query execution failed: {query}, Error: {str(e)}")
            raise DatabaseError(f"Single query execution failed", "SELECT")
    
    def execute_command(
        self, 
        command: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Execute INSERT/UPDATE/DELETE command
        
        Returns:
            Number of affected rows
        """
        try:
            with self.get_db_connection() as conn:
                result = conn.execute(text(command), params or {})
                conn.commit()
                return result.rowcount
        except IntegrityError as e:
            logger.error(f"Integrity constraint violation: {command}, Error: {str(e)}")
            raise DatabaseError(f"Data integrity violation: {str(e)}", "WRITE")
        except SQLAlchemyError as e:
            logger.error(f"Command execution failed: {command}, Error: {str(e)}")
            raise DatabaseError(f"Command execution failed", "WRITE")
    
    def execute_scalar(
        self, 
        query: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute query returning single scalar value (COUNT, SUM, etc.)
        """
        try:
            with self.get_db_connection() as conn:
                result = conn.execute(text(query), params or {}).scalar()
                return result
        except SQLAlchemyError as e:
            logger.error(f"Scalar query execution failed: {query}, Error: {str(e)}")
            raise DatabaseError(f"Scalar query execution failed", "SELECT")
    
    def execute_insert_returning_id(
        self, 
        command: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Execute INSERT command and return the generated ID
        """
        try:
            with self.get_db_connection() as conn:
                result = conn.execute(text(command + " RETURNING id"), params or {})
                conn.commit()
                return result.scalar()
        except IntegrityError as e:
            logger.error(f"Insert with integrity violation: {command}, Error: {str(e)}")
            raise DatabaseError(f"Data integrity violation: {str(e)}", "INSERT")
        except SQLAlchemyError as e:
            logger.error(f"Insert execution failed: {command}, Error: {str(e)}")
            raise DatabaseError(f"Insert execution failed", "INSERT")
    
    def execute_batch_command(
        self, 
        command: str, 
        params_list: List[Dict[str, Any]]
    ) -> int:
        """
        Execute batch operations for better performance
        
        Returns:
            Total number of affected rows
        """
        if not params_list:
            return 0
        
        try:
            with self.get_db_connection() as conn:
                total_affected = 0
                for params in params_list:
                    result = conn.execute(text(command), params)
                    total_affected += result.rowcount
                conn.commit()
                return total_affected
        except SQLAlchemyError as e:
            logger.error(f"Batch execution failed: {command}, Error: {str(e)}")
            raise DatabaseError(f"Batch execution failed", "BATCH")
    
    # Abstract methods that concrete repositories must implement
    @abstractmethod
    def get_by_id(self, entity_id: int) -> T:
        """Get entity by ID"""
        pass
    
    def exists(self, entity_id: int) -> bool:
        """Check if entity exists by ID"""
        query = f"SELECT 1 FROM {self.table_name} WHERE id = :id"
        result = self.execute_scalar(query, {"id": entity_id})
        return result is not None
    
    @property
    @abstractmethod
    def table_name(self) -> str:
        """Table name for the entity"""
        pass