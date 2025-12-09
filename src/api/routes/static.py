"""Static file serving for the web UI."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.config import get_settings

router = APIRouter(tags=["ui"])

UI_DIR = Path(__file__).parent.parent.parent.parent / "ui"
STATIC_DIR = UI_DIR / "static"


class LoginRequest(BaseModel):
    """Login request payload."""

    password: str


@router.get("/", include_in_schema=False)
async def serve_ui() -> FileResponse:
    """Serve the main web UI."""
    return FileResponse(
        UI_DIR / "index.html",
        media_type="text/html"
    )


@router.get("/login", include_in_schema=False)
async def serve_login() -> FileResponse:
    """Serve the login page."""
    return FileResponse(
        UI_DIR / "login.html",
        media_type="text/html"
    )


@router.post("/api/auth/login", include_in_schema=False)
async def login(request: LoginRequest) -> dict:
    """Verify password for UI access.

    Uses the same password as the admin dashboard.
    """
    settings = get_settings()

    if request.password != settings.admin.analytics_password:
        raise HTTPException(status_code=401, detail="Invalid password")

    return {"status": "ok"}


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
