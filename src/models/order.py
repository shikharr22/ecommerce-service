from datetime import datetime, timezone

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Integer, Text
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from src.db import Base


class Address(Base):
    """
    A postal address belonging to a user.

    user_id uses SET NULL on delete: if a user is deleted their addresses are
    kept (orders may still reference them for historical record-keeping) but
    the link to the user is severed.
    """

    __tablename__ = "addresses"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    line1 = Column(Text, nullable=True)
    line2 = Column(Text, nullable=True)
    city = Column(Text, nullable=True)
    region = Column(Text, nullable=True)
    country = Column(Text, nullable=True)
    postal_code = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Address id={self.id} city={self.city!r}>"


class Order(Base):
    """
    A completed (or in-progress) purchase by a user.

    status is constrained to a fixed set of values using a CHECK constraint
    rather than a Postgres ENUM type. CHECK constraints are simpler to migrate
    (adding a new status is an ALTER TABLE, not an ALTER TYPE + ALTER TABLE).

    total_cents is stored redundantly alongside order_items for fast reads and
    as an audit trail -- even if variant prices change later, the charged
    amount is preserved.

    metadata_ maps to the 'metadata' column. JSONB stores free-form data like
    payment provider responses or promo codes without requiring schema changes.
    """

    __tablename__ = "orders"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    status = Column(Text, nullable=False, default="created")
    total_cents = Column(BigInteger, nullable=False)
    currency = Column(Text, nullable=False, default="USD")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    billing_address_id = Column(BigInteger, ForeignKey("addresses.id"), nullable=True)
    shipping_address_id = Column(BigInteger, ForeignKey("addresses.id"), nullable=True)
    payment_provider_id = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint(
            "status IN ('created','paid','shipped','refunded','cancelled')",
            name="ck_order_status",
        ),
        CheckConstraint("total_cents >= 0", name="ck_order_total"),
    )

    # cascade='all, delete-orphan' -> deleting an order removes its line items
    items = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Order id={self.id} status={self.status!r} "
            f"total_cents={self.total_cents}>"
        )


class OrderItem(Base):
    """
    A single line item within an order.

    unit_price_cents is snapshotted at the time of purchase so that later
    price changes on the variant do not alter historical order totals.

    subtotal_cents = unit_price_cents * quantity, also stored for fast reads.
    """

    __tablename__ = "order_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    variant_id = Column(
        BigInteger, ForeignKey("product_variants.id"), nullable=False
    )
    unit_price_cents = Column(BigInteger, nullable=False)
    quantity = Column(Integer, nullable=False)
    subtotal_cents = Column(BigInteger, nullable=False)

    __table_args__ = (
        CheckConstraint("unit_price_cents >= 0", name="ck_item_unit_price"),
        CheckConstraint("quantity > 0", name="ck_item_quantity"),
        CheckConstraint("subtotal_cents >= 0", name="ck_item_subtotal"),
    )

    order = relationship("Order", back_populates="items")

    def __repr__(self) -> str:
        return (
            f"<OrderItem id={self.id} variant_id={self.variant_id} "
            f"qty={self.quantity}>"
        )
