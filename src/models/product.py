from datetime import datetime, timezone

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Integer, Text
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from src.db import Base


class Category(Base):
    """
    Top-level grouping for products (e.g. Electronics, Clothing).
    """

    __tablename__ = "categories"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)

    # One category has many products. back_populates keeps both sides in sync.
    products = relationship("Product", back_populates="category")

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name!r}>"


class Product(Base):
    """
    A product is the top-level item (e.g. 'Running Shoe').
    Concrete purchasable options (size M, colour red) live in ProductVariant.

    category_id is nullable — a product can exist without a category.
    """

    __tablename__ = "products"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sku = Column(Text, nullable=False, unique=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    category_id = Column(BigInteger, ForeignKey("categories.id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    category = relationship("Category", back_populates="products")
    # cascade='all, delete-orphan' mirrors ON DELETE CASCADE in the SQL schema:
    # deleting a product automatically deletes all its variants.
    variants = relationship(
        "ProductVariant", back_populates="product", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} sku={self.sku!r} title={self.title!r}>"


class ProductVariant(Base):
    """
    A specific, purchasable version of a product.

    attributes is a JSONB column — it stores arbitrary key/value pairs like
    {"size": "M", "color": "red"} without requiring schema changes for new
    attribute types. The GIN index on this column makes JSON containment
    queries (@>) fast.

    price_cents stores the price as an integer number of cents to avoid
    floating-point rounding errors. $19.99 -> 1999.
    """

    __tablename__ = "product_variants"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sku = Column(Text, nullable=False, unique=True)
    product_id = Column(
        BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    price_cents = Column(BigInteger, nullable=False)
    attributes = Column(JSONB, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (CheckConstraint("price_cents >= 0", name="ck_variant_price"),)

    product = relationship("Product", back_populates="variants")
    # uselist=False -> one-to-one: each variant has exactly one inventory row.
    inventory = relationship(
        "Inventory",
        back_populates="variant",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ProductVariant id={self.id} sku={self.sku!r}>"


class Inventory(Base):
    """
    Tracks stock for a single ProductVariant.

    available  -- units that can be added to a cart and purchased
    reserved   -- units currently held in active carts (not yet paid)

    The CHECK constraints (mirroring the SQL schema) ensure neither column
    goes negative at the database level -- a last line of defence even if
    application logic has a bug.

    During checkout the flow is:
        1. Decrement available, increment reserved  (reservation)
        2. On payment success: decrement reserved   (fulfilment)
        3. On payment failure: increment available  (release)
    """

    __tablename__ = "inventory"

    variant_id = Column(
        BigInteger,
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    available = Column(Integer, nullable=False, default=0)
    reserved = Column(Integer, nullable=False, default=0)
    last_updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint("available >= 0", name="ck_inventory_available"),
        CheckConstraint("reserved >= 0", name="ck_inventory_reserved"),
    )

    variant = relationship("ProductVariant", back_populates="inventory")

    def __repr__(self) -> str:
        return (
            f"<Inventory variant_id={self.variant_id} "
            f"available={self.available} reserved={self.reserved}>"
        )
