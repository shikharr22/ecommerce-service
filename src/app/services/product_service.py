from typing import List, Optional, Tuple
from app.repositories.product_repository import ProductRepository
from app.models.product import Product, ProductSummary, ProductVariant
from app.schemas.product_schemas import (
    ProductListRequest, ProductSearchRequest, InventoryUpdateRequest
)
from app.core.exceptions import (
    NotFoundError, ValidationError, BusinessLogicError, ConflictError
)
from app.core.config import config
import logging

logger = logging.getLogger(__name__)


class ProductService:
    """
    Product business logic service
    
    Responsibilities:
    - Enforce business rules
    - Coordinate between repositories
    - Handle complex use cases
    - Cache management
    - Event publishing
    """
    
    def __init__(self, product_repository: ProductRepository):
        self.product_repo = product_repository
        self.cache_ttl = config.api.cache_ttl_seconds if hasattr(config.api, 'cache_ttl_seconds') else 300
    
    def get_product_by_id(self, product_id: int) -> Product:
        """
        Get product by ID with business validation
        
        Business Rules:
        - Product must exist
        - Product must be active (if status field exists)
        - Inventory data must be fresh
        """
        logger.info(f"Fetching product {product_id}")
        
        try:
            product = self.product_repo.get_by_id(product_id)
            
            # Business rule: Don't return products with no variants
            if not product.variants:
                logger.warning(f"Product {product_id} has no variants")
                raise BusinessLogicError(
                    "Product is not available", 
                    rule="product_must_have_variants"
                )
            
            # Business logic: Sort variants by price
            product.variants.sort(key=lambda v: v.price_cents)
            
            logger.info(f"Successfully retrieved product {product_id} with {len(product.variants)} variants")
            return product
            
        except NotFoundError:
            logger.warning(f"Product {product_id} not found")
            raise
        except Exception as e:
            logger.error(f"Error retrieving product {product_id}: {str(e)}")
            raise BusinessLogicError(f"Failed to retrieve product: {str(e)}")
    
    def list_products(self, request: ProductListRequest) -> Tuple[List[ProductSummary], Optional[int]]:
        """
        List products with filtering and pagination
        
        Business Rules:
        - Enforce maximum page size
        - Apply default filtering for active products
        - Apply business-specific sorting
        """
        logger.info(f"Listing products with filters: {request.dict()}")
        
        # Business rule: Enforce maximum page size
        max_page_size = config.api.max_page_size
        if request.limit > max_page_size:
            logger.warning(f"Requested limit {request.limit} exceeds maximum {max_page_size}")
            request.limit = max_page_size
        
        # Business validation: Price range validation
        if (request.min_price_cents is not None and 
            request.max_price_cents is not None and 
            request.min_price_cents > request.max_price_cents):
            raise ValidationError("min_price_cents cannot be greater than max_price_cents")
        
        try:
            products, next_cursor = self.product_repo.list_products(
                limit=request.limit,
                after=request.after,
                category_id=request.category_id,
                search_query=request.search,
                min_price_cents=request.min_price_cents,
                max_price_cents=request.max_price_cents,
                has_inventory=request.has_inventory
            )
            
            # Business logic: Apply additional filtering
            filtered_products = self._apply_business_filters(products)
            
            logger.info(f"Retrieved {len(filtered_products)} products")
            return filtered_products, next_cursor
            
        except Exception as e:
            logger.error(f"Error listing products: {str(e)}")
            raise BusinessLogicError(f"Failed to list products: {str(e)}")
    
    def search_products(self, request: ProductSearchRequest) -> List[ProductSummary]:
        """
        Search products with business logic
        
        Business Rules:
        - Sanitize search terms
        - Apply relevance scoring
        - Filter inappropriate results
        """
        logger.info(f"Searching products with query: '{request.query}'")
        
        # Business logic: Sanitize search query
        sanitized_query = self._sanitize_search_query(request.query)
        
        if len(sanitized_query) < 2:
            raise ValidationError("Search query must be at least 2 characters after sanitization")
        
        try:
            products = self.product_repo.search_products_by_title(
                search_term=sanitized_query,
                limit=request.limit
            )
            
            # Business logic: Apply search result filtering
            filtered_products = self._filter_search_results(products, sanitized_query)
            
            logger.info(f"Search returned {len(filtered_products)} results for '{sanitized_query}'")
            return filtered_products
            
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            raise BusinessLogicError(f"Search failed: {str(e)}")
    
    def get_variant_by_id(self, variant_id: int) -> ProductVariant:
        """
        Get product variant with business validation
        
        Business Rules:
        - Variant must exist
        - Variant must be purchasable
        """
        logger.info(f"Fetching variant {variant_id}")
        
        try:
            variant = self.product_repo.get_variant_by_id(variant_id)
            
            # Business rule: Variant must have valid pricing
            if variant.price_cents <= 0:
                raise BusinessLogicError(
                    "Product variant is not available for purchase",
                    rule="variant_must_have_valid_price"
                )
            
            return variant
            
        except NotFoundError:
            logger.warning(f"Variant {variant_id} not found")
            raise
        except Exception as e:
            logger.error(f"Error retrieving variant {variant_id}: {str(e)}")
            raise BusinessLogicError(f"Failed to retrieve variant: {str(e)}")
    
    def check_variant_availability(self, variant_id: int, requested_quantity: int) -> bool:
        """
        Check if variant has sufficient inventory
        
        Business Rules:
        - Must have enough available inventory
        - Account for reserved inventory
        - Consider minimum stock levels
        """
        logger.info(f"Checking availability for variant {variant_id}, quantity {requested_quantity}")
        
        if requested_quantity <= 0:
            raise ValidationError("Requested quantity must be positive")
        
        try:
            variant = self.product_repo.get_variant_by_id(variant_id)
            
            # Business logic: Calculate truly available quantity
            available_quantity = variant.available_quantity
            
            # Business rule: Minimum stock level (reserve some inventory)
            min_stock_level = self._get_minimum_stock_level(variant)
            effective_available = max(0, available_quantity - min_stock_level)
            
            is_available = effective_available >= requested_quantity
            
            logger.info(f"Variant {variant_id}: available={available_quantity}, "
                       f"min_stock={min_stock_level}, effective={effective_available}, "
                       f"requested={requested_quantity}, result={is_available}")
            
            return is_available
            
        except NotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking availability for variant {variant_id}: {str(e)}")
            return False
    
    def reserve_inventory(self, variant_id: int, quantity: int) -> bool:
        """
        Reserve inventory for checkout process
        
        Business Rules:
        - Must check availability first
        - Atomic operation to prevent race conditions
        - Log reservation for audit trail
        """
        logger.info(f"Reserving {quantity} units of variant {variant_id}")
        
        # Business validation
        if quantity <= 0:
            raise ValidationError("Reservation quantity must be positive")
        
        if quantity > 99:  # Business rule: Maximum quantity per reservation
            raise ValidationError("Cannot reserve more than 99 units at once")
        
        # Business rule: Check availability before reservation
        if not self.check_variant_availability(variant_id, quantity):
            logger.warning(f"Insufficient inventory for variant {variant_id}, quantity {quantity}")
            raise BusinessLogicError(
                "Insufficient inventory available",
                rule="insufficient_inventory"
            )
        
        try:
            # Atomic reservation operation
            success = self.product_repo.reserve_inventory(variant_id, quantity)
            
            if success:
                logger.info(f"Successfully reserved {quantity} units of variant {variant_id}")
                # Here you might publish an event for inventory tracking
                # self.event_publisher.publish(InventoryReservedEvent(...))
            else:
                logger.warning(f"Failed to reserve inventory - concurrent modification for variant {variant_id}")
                raise ConflictError("Inventory was modified by another operation")
            
            return success
            
        except Exception as e:
            logger.error(f"Error reserving inventory for variant {variant_id}: {str(e)}")
            raise BusinessLogicError(f"Failed to reserve inventory: {str(e)}")
    
    def release_inventory_reservation(self, variant_id: int, quantity: int) -> bool:
        """
        Release reserved inventory (e.g., when cart is abandoned)
        
        Business Rules:
        - Can only release what was previously reserved
        - Should be idempotent (safe to call multiple times)
        """
        logger.info(f"Releasing {quantity} reserved units of variant {variant_id}")
        
        if quantity <= 0:
            raise ValidationError("Release quantity must be positive")
        
        try:
            success = self.product_repo.release_inventory_reservation(variant_id, quantity)
            
            if success:
                logger.info(f"Successfully released {quantity} reserved units of variant {variant_id}")
                # Publish event for audit trail
                # self.event_publisher.publish(InventoryReleasedEvent(...))
            
            return success
            
        except Exception as e:
            logger.error(f"Error releasing reservation for variant {variant_id}: {str(e)}")
            raise BusinessLogicError(f"Failed to release reservation: {str(e)}")
    
    def update_inventory(self, variant_id: int, request: InventoryUpdateRequest) -> bool:
        """
        Update inventory levels (admin operation)
        
        Business Rules:
        - Only authorized users can update inventory
        - Must validate reasonable inventory levels
        - Log all inventory changes
        """
        logger.info(f"Updating inventory for variant {variant_id}: available={request.available}, reserved={request.reserved}")
        
        # Business validation: Reasonable inventory limits
        max_inventory = 10000  # Business rule: Maximum inventory per variant
        if request.available > max_inventory:
            raise ValidationError(f"Available inventory cannot exceed {max_inventory}")
        
        if request.reserved > request.available:
            raise ValidationError("Reserved quantity cannot exceed available quantity")
        
        try:
            # Verify variant exists
            self.product_repo.get_variant_by_id(variant_id)
            
            success = self.product_repo.update_inventory(
                variant_id=variant_id,
                available=request.available,
                reserved=request.reserved
            )
            
            if success:
                logger.info(f"Successfully updated inventory for variant {variant_id}")
                # Publish event for inventory tracking systems
                # self.event_publisher.publish(InventoryUpdatedEvent(...))
            
            return success
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error updating inventory for variant {variant_id}: {str(e)}")
            raise BusinessLogicError(f"Failed to update inventory: {str(e)}")
    
    # Private helper methods for business logic
    def _apply_business_filters(self, products: List[ProductSummary]) -> List[ProductSummary]:
        """Apply additional business-specific filtering"""
        # Example: Filter out products that don't meet business criteria
        return [
            product for product in products
            if product.variant_count > 0  # Must have variants
            and (product.min_price_cents or 0) > 0  # Must have valid pricing
        ]
    
    def _sanitize_search_query(self, query: str) -> str:
        """Sanitize search query for security and relevance"""
        # Remove potentially harmful characters
        import re
        sanitized = re.sub(r'[^\w\s-]', '', query)
        # Remove extra whitespace
        sanitized = ' '.join(sanitized.split())
        return sanitized.lower()
    
    def _filter_search_results(self, products: List[ProductSummary], query: str) -> List[ProductSummary]:
        """Apply business logic to search results"""
        # Example: Boost products with exact matches in title
        query_words = set(query.lower().split())
        
        def relevance_score(product: ProductSummary) -> int:
            title_words = set(product.title.lower().split())
            exact_matches = len(query_words.intersection(title_words))
            return exact_matches
        
        # Sort by relevance, then by availability
        return sorted(
            products,
            key=lambda p: (relevance_score(p), p.total_available),
            reverse=True
        )
    
    def _get_minimum_stock_level(self, variant: ProductVariant) -> int:
        """Calculate minimum stock level to maintain"""
        # Business rule: Keep 5% or minimum 1 unit as safety stock
        safety_stock = max(1, int(variant.available * 0.05))
        return min(safety_stock, 5)  # Cap at 5 units