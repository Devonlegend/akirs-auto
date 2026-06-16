"""Auth/admin SQLAlchemy models. Importing the package registers every table
on backend.database.Base so alembic autogenerate and create_all see them."""

from backend.models import embed, users  # noqa: F401

__all__ = ["embed", "users"]
