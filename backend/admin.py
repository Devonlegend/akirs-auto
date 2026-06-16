"""starlette-admin panel for AKIRS.

Mounted at /admin and gated to Admin accounts. The user/admin views hijack the
create/edit payload so the plaintext typed into the password field is stored as
a PBKDF2 hash (never persisted in the clear).
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import Response

from starlette_admin import BooleanField, PasswordField, StringField
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.contrib.sqla import Admin as SqlaAdmin
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import LoginFailed

from backend.database import AsyncSessionLocal
from backend.models.embed import EmbedKey
from backend.models.users import Admin, AccountType, User
from backend.services.auth_queries import authenticate_user, hash_password
from backend.services.embed_keys import generate_key

SESSION_SECRET = os.environ.get("ADMIN_SESSION_SECRET", "dev-insecure-admin-session-secret-change-me")


class AdminAuthProvider(AuthProvider):
    """Session-cookie auth that only admits accounts of type Admin."""

    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        async with AsyncSessionLocal() as session:
            user = await authenticate_user(session, username.strip(), password)
        if user is None or user.account_type != AccountType.Admin:
            raise LoginFailed("Invalid admin credentials")
        request.session.update({"admin_user": user.username, "display_name": user.display_name})
        return response

    async def is_authenticated(self, request: Request) -> bool:
        return request.session.get("admin_user") is not None

    def get_admin_user(self, request: Request) -> AdminUser | None:
        label = request.session.get("display_name") or request.session.get("admin_user")
        if not label:
            return None
        return AdminUser(username=label)

    async def logout(self, request: Request, response: Response) -> Response:
        request.session.clear()
        return response


class _PasswordHashingView(ModelView):
    """Shared user/admin view that hashes the submitted password before persist."""

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        if obj.password:
            obj.password = hash_password(obj.password)

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        # A blank password field on edit means "leave it unchanged" — restore the
        # stored hash instead of persisting an empty string. A non-empty value is
        # a new password and gets hashed.
        if obj.password:
            obj.password = hash_password(obj.password)
        else:
            history = sa_inspect(obj).attrs.password.history
            if history.deleted:
                obj.password = history.deleted[0]


class UserView(_PasswordHashingView):
    fields = ["username", "display_name", PasswordField("password"), "created_at"]
    exclude_fields_from_create = ["created_at"]
    exclude_fields_from_edit = ["created_at"]
    exclude_fields_from_list = []


class AdminView(_PasswordHashingView):
    fields = [
        "username",
        "display_name",
        PasswordField("password"),
        BooleanField("can_manage_embed_keys"),
        StringField("permissions"),
        "created_at",
    ]
    exclude_fields_from_create = ["created_at"]
    exclude_fields_from_edit = ["created_at"]


class EmbedKeyView(ModelView):
    fields = [
        "label",
        StringField("allowed_origins", help_text="Comma-separated origins; blank = any origin"),
        BooleanField("active"),
        StringField("key", read_only=True, exclude_from_create=True, exclude_from_edit=True),
        "last_used_at",
        "created_at",
    ]
    exclude_fields_from_create = ["key", "last_used_at", "created_at"]
    exclude_fields_from_edit = ["key", "last_used_at", "created_at"]

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        obj.key = generate_key()


def build_admin(engine: AsyncEngine) -> SqlaAdmin:
    admin = SqlaAdmin(
        engine,
        title="AKIRS Admin",
        base_url="/admin",
        auth_provider=AdminAuthProvider(),
        middlewares=[Middleware(SessionMiddleware, secret_key=SESSION_SECRET)],
    )
    admin.add_view(UserView(User, icon="fa fa-user", label="Users"))
    admin.add_view(AdminView(Admin, icon="fa fa-user-shield", label="Admins"))
    admin.add_view(EmbedKeyView(EmbedKey, icon="fa fa-key", label="Embed Keys"))
    return admin
