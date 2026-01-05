from typing import List, Optional, Dict, Any, Tuple
from app.repositories.base import BaseRepository
from app.models.product import Product, ProductVariant, ProductSummary
from app.core.exceptions import NotFoundError, ValidationError
import logging

logger = logging.getLogger(__name__)


class ProductRepository(BaseRepository[Product]):
    """Repository for Product entity with complex variant relationships"""
    
    @property
    def table_name(self) -> str:
        return "products"
    
    def get_by_id(self, product_id: int) -> Product:
        """
        Get product with all variants and inventory data by ID
        
        Complex JOIN query demonstrating:
        - Multi-table relationships
        - LEFT JOINs for optional data
        - Data aggregation in repository layer
        """
        query = """
        SELECT 
            p.id,
            p.sku,
            p.title,
            p.description,
            p.category_id,
            p.created_at,
            v.id as variant_id,
            v.sku as variant_sku,
            v.price_cents,
            v.attributes,
            COALESCE(i.available, 0) AS available,
            COALESCE(i.reserved, 0) AS reserved 
        FROM products p 
        LEFT JOIN product_variants v ON v.product_id = p.id 
        LEFT JOIN inventory i ON i.variant_id = v.id 
        WHERE p.id = :product_id 
        ORDER BY v.id
        """
        
        rows = self.execute_query(query, {"product_id": product_id})
        
        if not rows:
            raise NotFoundError("Product", str(product_id))
        
        return self._build_product_from_rows(rows)
    
    def list_products(
        self,
        limit: int,
        after: Optional[int] = None,
        category_id: Optional[int] = None,
        search_query: Optional[str] = None,
        min_price_cents: Optional[int] = None,
        max_price_cents: Optional[int] = None,
        has_inventory: Optional[bool] = None
    ) -> Tuple[List[ProductSummary], Optional[int]]:
        """
        List products with advanced filtering and cursor-based pagination
        
        Demonstrates:
        - Complex WHERE clause building
        - GROUP BY with aggregations
        - HAVING clauses for post-aggregation filtering
        - Cursor-based pagination for scalability
        """
        
        # Base query with aggregations
        query = """
        SELECT 
            p.id AS product_id,
            p.sku AS product_sku,
            p.title,
            MIN(v.price_cents) AS min_price_cents,
            COUNT(v.id) AS variant_count,
            COALESCE(SUM(i.available - i.reserved), 0) AS total_available
        FROM products p
        LEFT JOIN product_variants v ON v.product_id = p.id
        LEFT JOIN inventory i ON i.variant_id = v.id
        WHERE 1=1
        """
        
        params = {"limit": limit + 1}  # +1 to check if there are more results
        
        # Dynamic WHERE clause building
        if after is not None:
            query += " AND p.id > :after"
            params["after"] = after
            
        if category_id is not None:
            query += " AND p.category_id = :category_id"
            params["category_id"] = category_id
            
        if search_query:
            # Full-text search using PostgreSQL's ILIKE
            query += " AND (p.title ILIKE :search_query OR p.description ILIKE :search_query)"
            params["search_query"] = f"%{search_query}%"
        
        query += " GROUP BY p.id, p.sku, p.title"
        
        # Build HAVING clauses for post-aggregation filtering
        having_clauses = []
        if min_price_cents is not None:
            having_clauses.append("MIN(v.price_cents) >= :min_price_cents")
            params["min_price_cents"] = min_price_cents
            
        if max_price_cents is not None:
            having_clauses.append("MIN(v.price_cents) <= :max_price_cents")
            params["max_price_cents"] = max_price_cents
            
        if has_inventory is True:
            having_clauses.append("COALESCE(SUM(i.available - i.reserved), 0) > 0")
        elif has_inventory is False:
            having_clauses.append("COALESCE(SUM(i.available - i.reserved), 0) = 0")
        
        if having_clauses:
            query += " HAVING " + " AND ".join(having_clauses)
        
        query += " ORDER BY p.id LIMIT :limit"
        
        rows = self.execute_query(query, params)
        
        # Handle cursor-based pagination
        cursor = None
        if len(rows) > limit:
            cursor = rows[-1]["product_id"]
            rows = rows[:-1]
        
        products = [
            ProductSummary(
                product_id=row["product_id"],
                product_sku=row["product_sku"],
                title=row["title"],
                min_price_cents=row["min_price_cents"],
                variant_count=row["variant_count"],
                total_available=row["total_available"]
            )
            for row in rows
        ]
        
        return products, cursor
    
    def get_products_by_category(self, category_id: int) -> List[ProductSummary]:
        """Get all products in a specific category"""
        products, _ = self.list_products(
            limit=1000,  # Large limit for category listing
            category_id=category_id
        )
        return products
    
    def search_products_by_title(self, search_term: str, limit: int = 50) -> List[ProductSummary]:
        """Search products by title using full-text search"""
        # PostgreSQL full-text search with ranking
        query = """
        SELECT 
            p.id AS product_id,
            p.sku AS product_sku,
            p.title,
            MIN(v.price_cents) AS min_price_cents,
            COUNT(v.id) AS variant_count,
            COALESCE(SUM(i.available - i.reserved), 0) AS total_available,
            ts_rank(to_tsvector('english', p.title), plainto_tsquery('english', :search_term)) AS rank
        FROM products p
        LEFT JOIN product_variants v ON v.product_id = p.id
        LEFT JOIN inventory i ON i.variant_id = v.id
        WHERE to_tsvector('english', p.title) @@ plainto_tsquery('english', :search_term)
        GROUP BY p.id, p.sku, p.title
        ORDER BY rank DESC, p.id
        LIMIT :limit
        """
        
        rows = self.execute_query(query, {"search_term": search_term, "limit": limit})
        
        return [
            ProductSummary(
                product_id=row["product_id"],
                product_sku=row["product_sku"],
                title=row["title"],
                min_price_cents=row["min_price_cents"],
                variant_count=row["variant_count"],
                total_available=row["total_available"]
            )
            for row in rows
        ]
    
    def get_variant_by_id(self, variant_id: int) -> ProductVariant:
        """Get specific product variant with inventory"""
        query = """
        SELECT 
            v.id as variant_id,
            v.sku as variant_sku,
            v.price_cents,
            v.attributes,
            COALESCE(i.available, 0) AS available,
            COALESCE(i.reserved, 0) AS reserved
        FROM product_variants v
        LEFT JOIN inventory i ON i.variant_id = v.id
        WHERE v.id = :variant_id
        """
        
        row = self.execute_single_query(query, {"variant_id": variant_id})
        
        if not row:
            raise NotFoundError("Product variant", str(variant_id))
        
        return ProductVariant(
            variant_id=row["variant_id"],
            variant_sku=row["variant_sku"],
            price_cents=row["price_cents"],
            attributes=row["attributes"] or {},
            available=row["available"],
            reserved=row["reserved"]
        )
    
    def update_inventory(self, variant_id: int, available: int, reserved: int = 0) -> bool:
        """Update inventory for a variant"""
        if available < 0 or reserved < 0:
            raise ValidationError("Inventory quantities cannot be negative")
        
        # Upsert operation - update if exists, insert if not
        query = """
        INSERT INTO inventory (variant_id, available, reserved) 
        VALUES (:variant_id, :available, :reserved)
        ON CONFLICT (variant_id) 
        DO UPDATE SET 
            available = EXCLUDED.available,
            reserved = EXCLUDED.reserved,
            updated_at = NOW()
        """
        
        affected_rows = self.execute_command(query, {
            "variant_id": variant_id,
            "available": available,
            "reserved": reserved
        })
        
        return affected_rows > 0
    
    def reserve_inventory(self, variant_id: int, quantity: int) -> bool:
        """
        Reserve inventory for checkout process
        
        Uses atomic operation to prevent race conditions
        """
        query = """
        UPDATE inventory 
        SET reserved = reserved + :quantity,
            updated_at = NOW()
        WHERE variant_id = :variant_id 
        AND (available - reserved) >= :quantity
        """
        
        affected_rows = self.execute_command(query, {
            "variant_id": variant_id,
            "quantity": quantity
        })
        
        return affected_rows > 0
    
    def release_inventory_reservation(self, variant_id: int, quantity: int) -> bool:
        """Release reserved inventory (e.g., when cart is abandoned)"""
        query = """
        UPDATE inventory 
        SET reserved = GREATEST(0, reserved - :quantity),
            updated_at = NOW()
        WHERE variant_id = :variant_id
        """
        
        affected_rows = self.execute_command(query, {
            "variant_id": variant_id,
            "quantity": quantity
        })
        
        return affected_rows > 0
    
    def _build_product_from_rows(self, rows: List[Dict[str, Any]]) -> Product:
        """
        Build Product domain object from database rows
        
        Demonstrates the Repository's role in:
        - Data transformation from DB to domain objects
        - Handling complex object relationships
        - Encapsulating SQL complexity
        """
        if not rows:
            raise ValueError("Cannot build product from empty rows")
        
        first_row = rows[0]
        
        # Build variants from rows
        variants = []
        for row in rows:
            if row["variant_id"] is not None:
                variants.append(ProductVariant(
                    variant_id=row["variant_id"],
                    variant_sku=row["variant_sku"],
                    price_cents=row["price_cents"],
                    attributes=row["attributes"] or {},
                    available=row["available"],
                    reserved=row["reserved"]
                ))
        
        return Product(
            id=first_row["id"],
            sku=first_row["sku"],
            title=first_row["title"],
            description=first_row["description"],
            category_id=first_row["category_id"],
            created_at=first_row["created_at"],
            variants=variants
        )