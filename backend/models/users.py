from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AccountType(str, Enum):
    User = "User"
    Admin = "Admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    account_type: Mapped[AccountType] = mapped_column(
        SAEnum(AccountType, name="account_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=AccountType.User,
    )

    __mapper_args__ = {
        "polymorphic_on": account_type,
        "polymorphic_identity": AccountType.User,
    }


class Admin(User):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    can_manage_embed_keys: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    permissions: Mapped[str] = mapped_column(String(256), nullable=False, default="*")

    __mapper_args__ = {
        "polymorphic_identity": AccountType.Admin,
    }
