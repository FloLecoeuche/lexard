"""Tests for analytics API endpoint and event storage."""

import json
import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes.analytics import AnalyticsEvent, store_event


@pytest.fixture
def client():
    """Create test client for API."""
    return TestClient(app)


class TestAnalyticsEndpoint:
    """Tests for POST /analytics/events endpoint."""

    def test_track_event_returns_ok(self, client):
        """POST /analytics/events should return 200 with status ok."""
        response = client.post(
            "/analytics/events",
            json={
                "event_name": "test_event",
                "browser_id": "browser123",
                "session_id": "session456",
                "properties": {"key": "value"},
            },
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_track_event_without_properties(self, client):
        """POST /analytics/events should work without properties."""
        response = client.post(
            "/analytics/events",
            json={
                "event_name": "simple_event",
                "browser_id": "browser789",
                "session_id": "session012",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_track_event_requires_event_name(self, client):
        """POST /analytics/events should require event_name."""
        response = client.post(
            "/analytics/events",
            json={
                "browser_id": "browser123",
                "session_id": "session456",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_track_event_requires_browser_id(self, client):
        """POST /analytics/events should require browser_id."""
        response = client.post(
            "/analytics/events",
            json={
                "event_name": "test_event",
                "session_id": "session456",
            },
        )

        assert response.status_code == 422

    def test_track_event_requires_session_id(self, client):
        """POST /analytics/events should require session_id."""
        response = client.post(
            "/analytics/events",
            json={
                "event_name": "test_event",
                "browser_id": "browser123",
            },
        )

        assert response.status_code == 422


class TestStoreEventFunction:
    """Tests for store_event background function."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database with analytics schema."""
        db_path = tmp_path / "test_analytics.db"
        conn = sqlite3.connect(str(db_path))

        # Create analytics tables
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                browser_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                properties TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS analytics_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                browser_id TEXT NOT NULL,
                started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                is_returning_user BOOLEAN NOT NULL DEFAULT 0,
                event_count INTEGER DEFAULT 0,
                query_count INTEGER DEFAULT 0,
                docs_uploaded INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS analytics_browsers (
                browser_id TEXT PRIMARY KEY,
                first_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                total_sessions INTEGER DEFAULT 1
            );
        """
        )
        conn.commit()
        conn.close()
        return str(db_path)

    def test_store_event_creates_browser_record(self, temp_db):
        """store_event should create browser record for new browser."""
        with patch(
            "src.api.routes.analytics.get_db_path", return_value=temp_db
        ):
            event = AnalyticsEvent(
                event_name="test_event",
                browser_id="new_browser",
                session_id="session123",
                properties={},
            )
            store_event(event)

        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT browser_id FROM analytics_browsers WHERE browser_id = ?",
            ("new_browser",),
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "new_browser"

    def test_store_event_creates_session_on_session_started(self, temp_db):
        """store_event should create session record for session_started event."""
        with patch(
            "src.api.routes.analytics.get_db_path", return_value=temp_db
        ):
            event = AnalyticsEvent(
                event_name="session_started",
                browser_id="browser123",
                session_id="new_session",
                properties={},
            )
            store_event(event)

        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT session_id, browser_id FROM analytics_sessions WHERE session_id = ?",
            ("new_session",),
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "new_session"
        assert result[1] == "browser123"

    def test_store_event_does_not_create_session_for_other_events(self, temp_db):
        """store_event should not create session record for non session_started events."""
        with patch(
            "src.api.routes.analytics.get_db_path", return_value=temp_db
        ):
            event = AnalyticsEvent(
                event_name="query_submitted",
                browser_id="browser123",
                session_id="no_session_record",
                properties={},
            )
            store_event(event)

        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT session_id FROM analytics_sessions WHERE session_id = ?",
            ("no_session_record",),
        )
        result = cursor.fetchone()
        conn.close()

        assert result is None

    def test_store_event_stores_raw_event(self, temp_db):
        """store_event should store the raw event in analytics_events."""
        with patch(
            "src.api.routes.analytics.get_db_path", return_value=temp_db
        ):
            event = AnalyticsEvent(
                event_name="document_uploaded",
                browser_id="browser456",
                session_id="session789",
                properties={"file_type": "pdf", "page_count": 10},
            )
            store_event(event)

        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT event_name, browser_id, session_id, properties FROM analytics_events"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "document_uploaded"
        assert result[1] == "browser456"
        assert result[2] == "session789"

        properties = json.loads(result[3])
        assert properties["file_type"] == "pdf"
        assert properties["page_count"] == 10

    def test_store_event_updates_session_event_count(self, temp_db):
        """store_event should increment session event_count."""
        with patch(
            "src.api.routes.analytics.get_db_path", return_value=temp_db
        ):
            # First create the session
            event1 = AnalyticsEvent(
                event_name="session_started",
                browser_id="browser123",
                session_id="counting_session",
                properties={},
            )
            store_event(event1)

            # Then send additional events
            event2 = AnalyticsEvent(
                event_name="page_viewed",
                browser_id="browser123",
                session_id="counting_session",
                properties={},
            )
            store_event(event2)

            event3 = AnalyticsEvent(
                event_name="button_clicked",
                browser_id="browser123",
                session_id="counting_session",
                properties={},
            )
            store_event(event3)

        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT event_count FROM analytics_sessions WHERE session_id = ?",
            ("counting_session",),
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 3  # session_started + page_viewed + button_clicked

    def test_store_event_updates_query_count(self, temp_db):
        """store_event should increment query_count for query_submitted events."""
        with patch(
            "src.api.routes.analytics.get_db_path", return_value=temp_db
        ):
            # Create session first
            event1 = AnalyticsEvent(
                event_name="session_started",
                browser_id="browser123",
                session_id="query_session",
                properties={},
            )
            store_event(event1)

            # Submit queries
            for _ in range(3):
                event = AnalyticsEvent(
                    event_name="query_submitted",
                    browser_id="browser123",
                    session_id="query_session",
                    properties={"question_length": 50},
                )
                store_event(event)

        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT query_count FROM analytics_sessions WHERE session_id = ?",
            ("query_session",),
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 3

    def test_store_event_updates_docs_uploaded(self, temp_db):
        """store_event should increment docs_uploaded for document_uploaded events."""
        with patch(
            "src.api.routes.analytics.get_db_path", return_value=temp_db
        ):
            # Create session first
            event1 = AnalyticsEvent(
                event_name="session_started",
                browser_id="browser123",
                session_id="upload_session",
                properties={},
            )
            store_event(event1)

            # Upload documents
            for i in range(2):
                event = AnalyticsEvent(
                    event_name="document_uploaded",
                    browser_id="browser123",
                    session_id="upload_session",
                    properties={"file_type": "pdf"},
                )
                store_event(event)

        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT docs_uploaded FROM analytics_sessions WHERE session_id = ?",
            ("upload_session",),
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 2

    def test_store_event_detects_returning_user(self, temp_db):
        """store_event should mark returning user correctly."""
        with patch(
            "src.api.routes.analytics.get_db_path", return_value=temp_db
        ):
            # First session for new browser
            event1 = AnalyticsEvent(
                event_name="session_started",
                browser_id="returning_browser",
                session_id="first_session",
                properties={},
            )
            store_event(event1)

            # Second session for same browser (returning user)
            event2 = AnalyticsEvent(
                event_name="session_started",
                browser_id="returning_browser",
                session_id="second_session",
                properties={},
            )
            store_event(event2)

        conn = sqlite3.connect(temp_db)

        # Check first session - not returning
        cursor = conn.execute(
            "SELECT is_returning_user FROM analytics_sessions WHERE session_id = ?",
            ("first_session",),
        )
        first = cursor.fetchone()

        # Check second session - returning
        cursor = conn.execute(
            "SELECT is_returning_user FROM analytics_sessions WHERE session_id = ?",
            ("second_session",),
        )
        second = cursor.fetchone()

        conn.close()

        assert first is not None
        assert first[0] == 0  # Not returning (False)

        assert second is not None
        assert second[0] == 1  # Returning (True)

    def test_store_event_increments_browser_total_sessions(self, temp_db):
        """store_event should increment browser's total_sessions on session_started."""
        with patch(
            "src.api.routes.analytics.get_db_path", return_value=temp_db
        ):
            # Multiple session_started events for same browser
            for i in range(3):
                event = AnalyticsEvent(
                    event_name="session_started",
                    browser_id="multi_session_browser",
                    session_id=f"session_{i}",
                    properties={},
                )
                store_event(event)

        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT total_sessions FROM analytics_browsers WHERE browser_id = ?",
            ("multi_session_browser",),
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 3

    def test_store_event_does_not_increment_sessions_for_other_events(self, temp_db):
        """store_event should not increment total_sessions for non session_started events."""
        with patch(
            "src.api.routes.analytics.get_db_path", return_value=temp_db
        ):
            # One session_started
            event1 = AnalyticsEvent(
                event_name="session_started",
                browser_id="stable_browser",
                session_id="single_session",
                properties={},
            )
            store_event(event1)

            # Multiple other events
            for _ in range(5):
                event = AnalyticsEvent(
                    event_name="query_submitted",
                    browser_id="stable_browser",
                    session_id="single_session",
                    properties={},
                )
                store_event(event)

        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT total_sessions FROM analytics_browsers WHERE browser_id = ?",
            ("stable_browser",),
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 1  # Only 1 session_started event

    def test_store_event_handles_errors_gracefully(self, temp_db, caplog):
        """store_event should log errors but not raise exceptions."""
        # Create a database without analytics tables to cause an error
        bad_db = temp_db.replace("test_analytics.db", "bad_db.db")
        conn = sqlite3.connect(bad_db)
        # Create empty database - no analytics tables
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.commit()
        conn.close()

        with patch(
            "src.api.routes.analytics.get_db_path",
            return_value=bad_db,
        ):
            event = AnalyticsEvent(
                event_name="test_event",
                browser_id="browser123",
                session_id="session456",
                properties={},
            )
            # Should not raise - should log warning instead
            store_event(event)

        # Check that warning was logged
        assert "Analytics storage failed" in caplog.text
