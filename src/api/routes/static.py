"""Static file serving for the web UI."""

import secrets
from pathlib import Path

from fastapi import APIRouter, Cookie, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel

from src.config import get_settings

router = APIRouter(tags=["ui"])

UI_DIR = Path(__file__).parent.parent.parent.parent / "ui"
STATIC_DIR = UI_DIR / "static"

# In-memory session store (simple, resets on restart)
_valid_sessions: set[str] = set()


class LoginRequest(BaseModel):
    """Login request payload."""

    password: str


def _is_authenticated(session_token: str | None) -> bool:
    """Check if the session token is valid."""
    return session_token is not None and session_token in _valid_sessions


@router.get("/", include_in_schema=False, response_model=None)
async def serve_ui(
    lexard_session: str | None = Cookie(default=None),
) -> FileResponse | RedirectResponse:
    """Serve the main web UI.

    Redirects to login if password protection is enabled and user is not authenticated.
    """
    settings = get_settings()

    # Check if password protection is enabled
    if settings.admin.ui_password_enabled:
        if not _is_authenticated(lexard_session):
            return RedirectResponse(url="/login", status_code=302)

    return FileResponse(
        UI_DIR / "index.html",
        media_type="text/html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/login", include_in_schema=False, response_model=None)
async def serve_login(
    lexard_session: str | None = Cookie(default=None),
) -> FileResponse | RedirectResponse:
    """Serve the login page.

    Redirects to main UI if already authenticated.
    """
    settings = get_settings()

    # If password protection is disabled, redirect to main UI
    if not settings.admin.ui_password_enabled:
        return RedirectResponse(url="/", status_code=302)

    # If already authenticated, redirect to main UI
    if _is_authenticated(lexard_session):
        return RedirectResponse(url="/", status_code=302)

    return FileResponse(
        UI_DIR / "login.html",
        media_type="text/html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.post("/api/auth/login", include_in_schema=False)
async def login(request: LoginRequest) -> Response:
    """Verify password for UI access.

    Uses the same password as the admin dashboard.
    Sets a session cookie on success.
    """
    settings = get_settings()

    if request.password != settings.admin.analytics_password:
        raise HTTPException(status_code=401, detail="Invalid password")

    # Generate session token
    session_token = secrets.token_urlsafe(32)
    _valid_sessions.add(session_token)

    # Create response with session cookie
    response = Response(
        content='{"status": "ok"}',
        media_type="application/json"
    )
    response.set_cookie(
        key="lexard_session",
        value=session_token,
        httponly=True,
        samesite="lax",
        max_age=86400,  # 24 hours
    )

    return response


@router.post("/api/auth/logout", include_in_schema=False)
async def logout(lexard_session: str | None = Cookie(default=None)) -> Response:
    """Logout and clear session."""
    if lexard_session and lexard_session in _valid_sessions:
        _valid_sessions.discard(lexard_session)

    response = Response(
        content='{"status": "ok"}',
        media_type="application/json"
    )
    response.delete_cookie(key="lexard_session")

    return response


@router.get("/internal/{dashboard_path}", include_in_schema=False)
async def serve_admin_ui(dashboard_path: str) -> FileResponse:
    """Serve the admin analytics dashboard.

    Only serves if the path matches the configured dashboard path.
    """
    settings = get_settings()
    if dashboard_path != settings.admin.dashboard_path:
        raise HTTPException(status_code=404, detail="Not found")

    admin_page = UI_DIR / "admin-a7x9k2.html"
    if not admin_page.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")

    return FileResponse(admin_page, media_type="text/html")


@router.get("/static/js/{filename}", include_in_schema=False)
async def serve_js(filename: str) -> FileResponse:
    """Serve JavaScript files from ui/static/js/."""
    # Prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = STATIC_DIR / "js" / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        file_path,
        media_type="application/javascript"
    )
