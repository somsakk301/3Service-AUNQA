"""Authentication endpoints (project owner, 2026-10-04; logout revocation, 2026-10-05). No register endpoint
and no user-management API: an account is created only by scripts/seed_user.py. Login sets a signed,
HttpOnly, time-limited session cookie, `Secure` following settings.cookie_secure (true once served over
HTTPS; false keeps plain-HTTP local development working). Logout both clears the cookie and revokes the
token's account server-side (AuthService.logout), so a copy of the old cookie stops working immediately too —
not only the browser that called logout."""
from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.dependencies import SESSION_COOKIE, get_auth_service, get_current_user, get_current_user_optional
from app.models.auth import AuthenticatedUser
from app.models.schemas import LoginRequest
from app.services.auth import AuthService
from app.settings import Settings

router = APIRouter(prefix="/api/auth")


@router.post("/login")
def login(body: LoginRequest, response: Response, auth: AuthService = Depends(get_auth_service)):
    user = auth.login(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    response.set_cookie(
        SESSION_COOKIE, auth.issue_token(user),
        httponly=True, samesite="lax", secure=Settings.from_env().cookie_secure, max_age=auth.ttl_seconds,
    )
    return {"name": user.name}


@router.get("/me")
def me(user: AuthenticatedUser = Depends(get_current_user)):
    return {"name": user.name}


@router.post("/logout")
def logout(response: Response, auth: AuthService = Depends(get_auth_service),
           user: AuthenticatedUser | None = Depends(get_current_user_optional)):
    if user is not None:
        auth.logout(user.user_id)
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}
