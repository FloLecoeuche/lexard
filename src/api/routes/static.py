"""Static file serving for the web UI."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["ui"])

UI_DIR = Path(__file__).parent.parent.parent.parent / "ui"
STATIC_DIR = UI_DIR / "static"


@router.get("/", include_in_schema=False)
async def serve_ui() -> FileResponse:
    """Serve the main web UI."""
    return FileResponse(
        UI_DIR / "index.html",
        media_type="text/html"
    )


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
