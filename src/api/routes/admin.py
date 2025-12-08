"""Admin analytics dashboard API routes.

Provides password-protected endpoints for viewing analytics metrics.
Access is via non-obvious URL path for additional security.
"""

import logging
import secrets
import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from src.config import get_settings

logger = logging.getLogger(__name__)

# In-memory token store (simple, resets on restart)
_valid_tokens: set[str] = set()

# Default database path (same as DocumentRegistry)
DEFAULT_DB_PATH = "data/lexard.db"


class AuthRequest(BaseModel):
    """Authentication request payload."""

    password: str


class AuthResponse(BaseModel):
    """Authentication response with token."""

    token: str


class SummaryMetrics(BaseModel):
    """Dashboard summary metrics."""

    daily_active_users: int
    new_users_today: int
    returning_users_today: int
    queries_today: int
    documents_uploaded_today: int
    total_browsers: int
    total_sessions: int
    total_events: int


class FeatureUsage(BaseModel):
    """Feature usage statistics."""

    feature: str
    usage_count: int
    unique_sessions: int


class SessionInfo(BaseModel):
    """Session information for display."""

    session_id: str
    browser_id: str
    started_at: str
    ended_at: str | None
    is_returning_user: bool
    event_count: int
    query_count: int
    docs_uploaded: int


class EventInfo(BaseModel):
    """Event information for display."""

    event_name: str
    browser_id: str
    session_id: str
    properties: str
    created_at: str


def get_db_path() -> str:
    """Get database path (uses same default as DocumentRegistry)."""
    return DEFAULT_DB_PATH


def require_admin_token(x_admin_token: str = Header(None)) -> bool:
    """Dependency to verify admin token.

    Args:
        x_admin_token: Token from X-Admin-Token header

    Returns:
        True if token is valid

    Raises:
        HTTPException: If token is missing or invalid
    """
    if not x_admin_token or x_admin_token not in _valid_tokens:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return True


# Create router with dynamic prefix from config
def create_admin_router() -> APIRouter:
    """Create admin router with configured path prefix."""
    settings = get_settings()
    dashboard_path = settings.admin.dashboard_path

    router = APIRouter(tags=["admin"], prefix=f"/internal/{dashboard_path}")

    @router.post("/auth", response_model=AuthResponse)
    async def authenticate(request: AuthRequest) -> AuthResponse:
        """Verify admin password and return session token.

        Args:
            request: Authentication request with password

        Returns:
            Token for accessing admin endpoints

        Raises:
            HTTPException: If password is incorrect
        """
        settings = get_settings()

        if request.password != settings.admin.analytics_password:
            raise HTTPException(status_code=401, detail="Invalid password")

        # Generate session token
        token = secrets.token_urlsafe(32)
        _valid_tokens.add(token)

        return AuthResponse(token=token)

    @router.get("/summary", response_model=SummaryMetrics)
    async def get_summary(_: bool = Depends(require_admin_token)) -> SummaryMetrics:
        """Get dashboard summary metrics.

        Returns:
            Summary metrics including DAU, new/returning users, queries
        """
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        today = datetime.now().strftime("%Y-%m-%d")

        try:
            # Daily active users (unique browsers with events today)
            cursor.execute(
                """
                SELECT COUNT(DISTINCT browser_id) as count
                FROM analytics_events
                WHERE DATE(created_at) = ?
                """,
                (today,),
            )
            dau = cursor.fetchone()["count"]

            # New users today (browsers first seen today)
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM analytics_browsers
                WHERE DATE(first_seen_at) = ?
                """,
                (today,),
            )
            new_users = cursor.fetchone()["count"]

            # Returning users today (sessions where is_returning_user = 1)
            cursor.execute(
                """
                SELECT COUNT(DISTINCT browser_id) as count
                FROM analytics_sessions
                WHERE DATE(started_at) = ? AND is_returning_user = 1
                """,
                (today,),
            )
            returning_users = cursor.fetchone()["count"]

            # Queries today
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM analytics_events
                WHERE event_name = 'query_submitted' AND DATE(created_at) = ?
                """,
                (today,),
            )
            queries = cursor.fetchone()["count"]

            # Documents uploaded today
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM analytics_events
                WHERE event_name = 'document_uploaded' AND DATE(created_at) = ?
                """,
                (today,),
            )
            docs_uploaded = cursor.fetchone()["count"]

            # Total browsers
            cursor.execute("SELECT COUNT(*) as count FROM analytics_browsers")
            total_browsers = cursor.fetchone()["count"]

            # Total sessions
            cursor.execute("SELECT COUNT(*) as count FROM analytics_sessions")
            total_sessions = cursor.fetchone()["count"]

            # Total events
            cursor.execute("SELECT COUNT(*) as count FROM analytics_events")
            total_events = cursor.fetchone()["count"]

            return SummaryMetrics(
                daily_active_users=dau,
                new_users_today=new_users,
                returning_users_today=returning_users,
                queries_today=queries,
                documents_uploaded_today=docs_uploaded,
                total_browsers=total_browsers,
                total_sessions=total_sessions,
                total_events=total_events,
            )
        finally:
            conn.close()

    @router.get("/feature-usage", response_model=list[FeatureUsage])
    async def get_feature_usage(
        days: int = 7,
        _: bool = Depends(require_admin_token),
    ) -> list[FeatureUsage]:
        """Get feature usage breakdown for the last N days.

        Args:
            days: Number of days to analyze (default 7)

        Returns:
            List of feature usage statistics
        """
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        try:
            cursor.execute(
                """
                SELECT
                    event_name as feature,
                    COUNT(*) as usage_count,
                    COUNT(DISTINCT session_id) as unique_sessions
                FROM analytics_events
                WHERE DATE(created_at) >= ?
                    AND (event_name LIKE '%_requested'
                         OR event_name LIKE '%_submitted'
                         OR event_name LIKE '%_completed')
                GROUP BY event_name
                ORDER BY usage_count DESC
                """,
                (since_date,),
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    FeatureUsage(
                        feature=row["feature"],
                        usage_count=row["usage_count"],
                        unique_sessions=row["unique_sessions"],
                    )
                )

            return results
        finally:
            conn.close()

    @router.get("/sessions", response_model=list[SessionInfo])
    async def get_sessions(
        limit: int = 50,
        _: bool = Depends(require_admin_token),
    ) -> list[SessionInfo]:
        """Get recent sessions.

        Args:
            limit: Maximum number of sessions to return (default 50)

        Returns:
            List of recent sessions
        """
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT
                    session_id,
                    browser_id,
                    started_at,
                    ended_at,
                    is_returning_user,
                    event_count,
                    query_count,
                    docs_uploaded
                FROM analytics_sessions
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    SessionInfo(
                        session_id=row["session_id"][:8] + "...",  # Truncate for display
                        browser_id=row["browser_id"][:8] + "...",
                        started_at=row["started_at"],
                        ended_at=row["ended_at"],
                        is_returning_user=bool(row["is_returning_user"]),
                        event_count=row["event_count"],
                        query_count=row["query_count"],
                        docs_uploaded=row["docs_uploaded"],
                    )
                )

            return results
        finally:
            conn.close()

    @router.get("/events", response_model=list[EventInfo])
    async def get_events(
        limit: int = 100,
        _: bool = Depends(require_admin_token),
    ) -> list[EventInfo]:
        """Get recent events.

        Args:
            limit: Maximum number of events to return (default 100)

        Returns:
            List of recent events
        """
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT
                    event_name,
                    browser_id,
                    session_id,
                    properties,
                    created_at
                FROM analytics_events
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    EventInfo(
                        event_name=row["event_name"],
                        browser_id=row["browser_id"][:8] + "...",
                        session_id=row["session_id"][:8] + "...",
                        properties=row["properties"],
                        created_at=row["created_at"],
                    )
                )

            return results
        finally:
            conn.close()

    @router.post("/logout")
    async def logout(x_admin_token: str = Header(None)) -> dict:
        """Logout and invalidate the current session token.

        Returns:
            Status confirmation
        """
        if x_admin_token and x_admin_token in _valid_tokens:
            _valid_tokens.discard(x_admin_token)
        return {"status": "ok"}

    return router


# Create the router instance
router = create_admin_router()
