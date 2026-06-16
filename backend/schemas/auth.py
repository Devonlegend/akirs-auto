from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    id: int
    username: str
    display_name: str
    account_type: str
    # Signed session token: authenticates SSE connections and admin actions.
    token: str
