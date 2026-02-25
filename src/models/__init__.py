# Re-export all models from a single entry point so the rest of the app
# can import cleanly:
#   from src.models import User, Product, Order
#
# Importing all models here also ensures they are registered with Base.metadata
# before any call to Base.metadata.create_all() or Alembic autogeneration.

from src.models.cart import Cart, CartItem
from src.models.order import Address, Order, OrderItem
from src.models.product import Category, Inventory, Product, ProductVariant
from src.models.user import User

__all__ = [
    "User",
    "Category",
    "Product",
    "ProductVariant",
    "Inventory",
    "Address",
    "Order",
    "OrderItem",
    "Cart",
    "CartItem",
]
