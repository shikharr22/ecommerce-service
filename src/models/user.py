from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Text

from src.db import Base


class User(Base):
    """
    Represents a registered customer.

    hashed_password is nullable so the table can later support OAuth/SSO
    sign-ins where no local password exists.
    """

    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(Text, nullable=False, unique=True)
    hashed_password = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
