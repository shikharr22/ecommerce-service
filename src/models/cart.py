from datetime import datetime, timezone

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Integer
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from src.db import Base


class Cart(Base):
    """
    A shopping cart belonging to a user.

    A user has one active cart at a time. updated_at is refreshed whenever
    items are added or removed, which is useful for expiring abandoned carts.

    ON DELETE CASCADE means deleting a user also deletes their cart and,
    via the cascade on cart_items, all items in it.
    """

    __tablename__ = "carts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    items = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Cart id={self.id} user_id={self.user_id}>"


class CartItem(Base):
    """
    A single variant + quantity pair inside a cart.

    quantity must be > 0 -- removing an item means deleting the row, not
    setting quantity to 0.
    """

    __tablename__ = "cart_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    cart_id = Column(
        BigInteger, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    variant_id = Column(
        BigInteger, ForeignKey("product_variants.id"), nullable=False
    )
    quantity = Column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_cart_item_quantity"),
    )

    cart = relationship("Cart", back_populates="items")

    def __repr__(self) -> str:
        return (
            f"<CartItem id={self.id} variant_id={self.variant_id} "
            f"qty={self.quantity}>"
        )
