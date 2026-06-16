"""Signed session tokens for the otherwise-stateless REST API.

The SPA keeps the logged-in user in localStorage. Two things need a tamper-proof
proof of identity that a plain user object can't give:
  - admin-only actions (minting embed keys) must verify the caller is an admin;
  - the SSE stream is authenticated by query param (EventSource can't set
    headers), so it needs a token that encodes which user is connecting.

Login issues every user a signed token carrying their id, username and
account type; endpoints verify the signature and read what they need.
"""

from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.admin import SESSION_SECRET

_SALT = "akirs-session-token"
_MAX_AGE_SECONDS = 60 * 60 * 12  # 12h

_serializer = URLSafeTimedSerializer(SESSION_SECRET, salt=_SALT)


def make_token(user_id: int, username: str, account_type: str) -> str:
    return _serializer.dumps({"uid": user_id, "username": username, "account_type": account_type})


def verify_token(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        return _serializer.loads(token, max_age=_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
