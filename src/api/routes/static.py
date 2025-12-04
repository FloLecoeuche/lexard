"""Static file serving for the web UI."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["ui"])

UI_DIR = Path(__file__).parent.parent.parent.parent / "ui"


@router.get("/", include_in_schema=False)
async def serve_ui() -> FileResponse:
    """Serve the main web UI."""
    return FileResponse(
        UI_DIR / "index.html",
        media_type="text/html"
    )
