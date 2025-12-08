"""Analytics API routes for tracking user behavior events.

Fire-and-forget endpoint that stores analytics events in background
for session tracking and feature usage metrics.
"""

import json
import logging
import sqlite3

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"])

# Default database path (same as DocumentRegistry)
DEFAULT_DB_PATH = "data/lexard.db"


class AnalyticsEvent(BaseModel):
    """Analytics event payload."""

    event_name: str
    browser_id: str
    session_id: str
    properties: dict = {}


class AnalyticsResponse(BaseModel):
    """Response for analytics endpoint."""

    status: str


def get_db_path() -> str:
    """Get database path (uses same default as DocumentRegistry)."""
    return DEFAULT_DB_PATH


def store_event(event: AnalyticsEvent) -> None:
    """Store analytics event in SQLite (runs in background).

    This function handles:
    1. Checking if browser is returning user
    2. Upserting browser record
    3. Creating/updating session record
    4. Storing raw event

    Args:
        event: The analytics event to store
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Check if browser is returning
        cursor.execute(
            "SELECT 1 FROM analytics_browsers WHERE browser_id = ?",
            (event.browser_id,),
        )
        is_returning = cursor.fetchone() is not None

        # 2. Upsert browser record
        cursor.execute(
            """
            INSERT INTO analytics_browsers (browser_id, first_seen_at, last_seen_at, total_sessions)
            VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
            ON CONFLICT(browser_id) DO UPDATE SET
                last_seen_at = CURRENT_TIMESTAMP,
                total_sessions = total_sessions + CASE
                    WHEN ? = 'session_started' THEN 1
                    ELSE 0
                END
            """,
            (event.browser_id, event.event_name),
        )

        # 3. Create/update session record
        if event.event_name == "session_started":
            cursor.execute(
                """
                INSERT OR IGNORE INTO analytics_sessions
                (session_id, browser_id, started_at, is_returning_user, event_count)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, 0)
                """,
                (event.session_id, event.browser_id, is_returning),
            )

        # 4. Update session counters
        cursor.execute(
            """
            UPDATE analytics_sessions SET
                ended_at = CURRENT_TIMESTAMP,
                event_count = event_count + 1,
                query_count = query_count + CASE WHEN ? = 'query_submitted' THEN 1 ELSE 0 END,
                docs_uploaded = docs_uploaded + CASE WHEN ? = 'document_uploaded' THEN 1 ELSE 0 END
            WHERE session_id = ?
            """,
            (event.event_name, event.event_name, event.session_id),
        )

        # 5. Store raw event
        cursor.execute(
            """
            INSERT INTO analytics_events (event_name, browser_id, session_id, properties)
            VALUES (?, ?, ?, ?)
            """,
            (
                event.event_name,
                event.browser_id,
                event.session_id,
                json.dumps(event.properties),
            ),
        )

        conn.commit()
    except Exception as e:
        # Log but don't fail - analytics should never break the app
        logger.warning(f"Analytics storage failed: {e}")
    finally:
        conn.close()


@router.post("/analytics/events", response_model=AnalyticsResponse)
async def track_event(
    event: AnalyticsEvent,
    background_tasks: BackgroundTasks,
) -> AnalyticsResponse:
    """Track analytics event (fire-and-forget).

    Receives analytics events from the frontend and stores them
    in background for non-blocking operation.

    Args:
        event: Analytics event payload with event_name, browser_id,
               session_id, and optional properties
        background_tasks: FastAPI background tasks for async storage

    Returns:
        Status confirmation (always returns ok immediately)
    """
    background_tasks.add_task(store_event, event)
    return AnalyticsResponse(status="ok")
