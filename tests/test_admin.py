"""Tests for admin analytics dashboard API endpoints."""

import json
import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import admin as admin_module


@pytest.fixture
def client():
    """Create test client for API."""
    return TestClient(app)


@pytest.fixture
def temp_db(tmp_path):
    """Create temporary database with analytics schema and sample data."""
    db_path = tmp_path / "test_admin.db"
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


@pytest.fixture
def populated_db(temp_db):
    """Populate database with sample analytics data."""
    conn = sqlite3.connect(temp_db)

    # Insert sample browsers
    conn.execute(
        "INSERT INTO analytics_browsers (browser_id, first_seen_at, last_seen_at, total_sessions) VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 2)",
        ("browser1",),
    )
    conn.execute(
        "INSERT INTO analytics_browsers (browser_id, first_seen_at, last_seen_at, total_sessions) VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)",
        ("browser2",),
    )

    # Insert sample sessions
    conn.execute(
        "INSERT INTO analytics_sessions (session_id, browser_id, started_at, is_returning_user, event_count, query_count, docs_uploaded) VALUES (?, ?, CURRENT_TIMESTAMP, 0, 5, 2, 1)",
        ("session1", "browser1"),
    )
    conn.execute(
        "INSERT INTO analytics_sessions (session_id, browser_id, started_at, is_returning_user, event_count, query_count, docs_uploaded) VALUES (?, ?, CURRENT_TIMESTAMP, 1, 3, 1, 0)",
        ("session2", "browser1"),
    )
    conn.execute(
        "INSERT INTO analytics_sessions (session_id, browser_id, started_at, is_returning_user, event_count, query_count, docs_uploaded) VALUES (?, ?, CURRENT_TIMESTAMP, 0, 2, 0, 1)",
        ("session3", "browser2"),
    )

    # Insert sample events
    events = [
        ("session_started", "browser1", "session1"),
        ("query_submitted", "browser1", "session1"),
        ("query_completed", "browser1", "session1"),
        ("document_uploaded", "browser1", "session1"),
        ("summarize_requested", "browser1", "session1"),
        ("session_started", "browser1", "session2"),
        ("query_submitted", "browser1", "session2"),
        ("risks_requested", "browser1", "session2"),
        ("session_started", "browser2", "session3"),
        ("document_uploaded", "browser2", "session3"),
    ]
    for event_name, browser_id, session_id in events:
        conn.execute(
            "INSERT INTO analytics_events (event_name, browser_id, session_id, properties, created_at) VALUES (?, ?, ?, '{}', CURRENT_TIMESTAMP)",
            (event_name, browser_id, session_id),
        )

    conn.commit()
    conn.close()
    return temp_db


class TestAuthEndpoint:
    """Tests for POST /internal/metrics-a7x9k2/auth endpoint."""

    def test_auth_with_correct_password(self, client):
        """POST /auth with correct password should return token."""
        response = client.post(
            "/internal/metrics-a7x9k2/auth",
            json={"password": "change-me-in-production"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert len(data["token"]) > 20  # Token should be reasonably long

    def test_auth_with_wrong_password(self, client):
        """POST /auth with wrong password should return 401."""
        response = client.post(
            "/internal/metrics-a7x9k2/auth",
            json={"password": "wrong-password"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid password"

    def test_auth_without_password(self, client):
        """POST /auth without password should return 422."""
        response = client.post(
            "/internal/metrics-a7x9k2/auth",
            json={},
        )

        assert response.status_code == 422

    def test_multiple_tokens_are_valid(self, client):
        """Multiple auth requests should return different valid tokens."""
        tokens = []
        for _ in range(3):
            response = client.post(
                "/internal/metrics-a7x9k2/auth",
                json={"password": "change-me-in-production"},
            )
            tokens.append(response.json()["token"])

        # All tokens should be unique
        assert len(set(tokens)) == 3


class TestProtectedEndpoints:
    """Tests for token-protected admin endpoints."""

    @pytest.fixture
    def auth_token(self, client):
        """Get a valid admin token."""
        response = client.post(
            "/internal/metrics-a7x9k2/auth",
            json={"password": "change-me-in-production"},
        )
        return response.json()["token"]

    def test_summary_requires_token(self, client):
        """GET /summary without token should return 401."""
        response = client.get("/internal/metrics-a7x9k2/summary")
        assert response.status_code == 401

    def test_summary_with_invalid_token(self, client):
        """GET /summary with invalid token should return 401."""
        response = client.get(
            "/internal/metrics-a7x9k2/summary",
            headers={"X-Admin-Token": "invalid-token"},
        )
        assert response.status_code == 401

    def test_summary_with_valid_token(self, client, auth_token, populated_db):
        """GET /summary with valid token should return metrics."""
        with patch(
            "src.api.routes.admin.get_db_path", return_value=populated_db
        ):
            response = client.get(
                "/internal/metrics-a7x9k2/summary",
                headers={"X-Admin-Token": auth_token},
            )

        assert response.status_code == 200
        data = response.json()
        assert "daily_active_users" in data
        assert "new_users_today" in data
        assert "returning_users_today" in data
        assert "queries_today" in data
        assert "total_browsers" in data
        assert data["total_browsers"] == 2
        assert data["total_sessions"] == 3

    def test_feature_usage_requires_token(self, client):
        """GET /feature-usage without token should return 401."""
        response = client.get("/internal/metrics-a7x9k2/feature-usage")
        assert response.status_code == 401

    def test_feature_usage_with_valid_token(self, client, auth_token, populated_db):
        """GET /feature-usage with valid token should return feature stats."""
        with patch(
            "src.api.routes.admin.get_db_path", return_value=populated_db
        ):
            response = client.get(
                "/internal/metrics-a7x9k2/feature-usage",
                headers={"X-Admin-Token": auth_token},
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have some feature usage entries
        assert len(data) > 0
        # Each entry should have the expected fields
        for entry in data:
            assert "feature" in entry
            assert "usage_count" in entry
            assert "unique_sessions" in entry

    def test_sessions_requires_token(self, client):
        """GET /sessions without token should return 401."""
        response = client.get("/internal/metrics-a7x9k2/sessions")
        assert response.status_code == 401

    def test_sessions_with_valid_token(self, client, auth_token, populated_db):
        """GET /sessions with valid token should return sessions list."""
        with patch(
            "src.api.routes.admin.get_db_path", return_value=populated_db
        ):
            response = client.get(
                "/internal/metrics-a7x9k2/sessions",
                headers={"X-Admin-Token": auth_token},
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3  # We inserted 3 sessions
        # Each session should have expected fields
        for session in data:
            assert "session_id" in session
            assert "browser_id" in session
            assert "started_at" in session
            assert "is_returning_user" in session
            assert "event_count" in session
            assert "query_count" in session
            assert "docs_uploaded" in session

    def test_sessions_limit_parameter(self, client, auth_token, populated_db):
        """GET /sessions should respect limit parameter."""
        with patch(
            "src.api.routes.admin.get_db_path", return_value=populated_db
        ):
            response = client.get(
                "/internal/metrics-a7x9k2/sessions?limit=2",
                headers={"X-Admin-Token": auth_token},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_events_requires_token(self, client):
        """GET /events without token should return 401."""
        response = client.get("/internal/metrics-a7x9k2/events")
        assert response.status_code == 401

    def test_events_with_valid_token(self, client, auth_token, populated_db):
        """GET /events with valid token should return events list."""
        with patch(
            "src.api.routes.admin.get_db_path", return_value=populated_db
        ):
            response = client.get(
                "/internal/metrics-a7x9k2/events",
                headers={"X-Admin-Token": auth_token},
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 10  # We inserted 10 events
        # Each event should have expected fields
        for event in data:
            assert "event_name" in event
            assert "browser_id" in event
            assert "session_id" in event
            assert "properties" in event
            assert "created_at" in event

    def test_events_limit_parameter(self, client, auth_token, populated_db):
        """GET /events should respect limit parameter."""
        with patch(
            "src.api.routes.admin.get_db_path", return_value=populated_db
        ):
            response = client.get(
                "/internal/metrics-a7x9k2/events?limit=5",
                headers={"X-Admin-Token": auth_token},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5


class TestLogoutEndpoint:
    """Tests for POST /internal/metrics-a7x9k2/logout endpoint."""

    def test_logout_invalidates_token(self, client):
        """POST /logout should invalidate the token."""
        # Get a token
        response = client.post(
            "/internal/metrics-a7x9k2/auth",
            json={"password": "change-me-in-production"},
        )
        token = response.json()["token"]

        # Verify token works
        response = client.get(
            "/internal/metrics-a7x9k2/summary",
            headers={"X-Admin-Token": token},
        )
        # Note: may fail if no DB, but should not be 401
        assert response.status_code != 401 or "expired" not in str(response.json())

        # Logout
        response = client.post(
            "/internal/metrics-a7x9k2/logout",
            headers={"X-Admin-Token": token},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        # Token should no longer work
        response = client.get(
            "/internal/metrics-a7x9k2/summary",
            headers={"X-Admin-Token": token},
        )
        assert response.status_code == 401

    def test_logout_without_token(self, client):
        """POST /logout without token should still return ok."""
        response = client.post("/internal/metrics-a7x9k2/logout")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestSummaryMetrics:
    """Tests for summary metrics calculations."""

    @pytest.fixture
    def auth_token(self, client):
        """Get a valid admin token."""
        response = client.post(
            "/internal/metrics-a7x9k2/auth",
            json={"password": "change-me-in-production"},
        )
        return response.json()["token"]

    def test_empty_database_returns_zeros(self, client, auth_token, temp_db):
        """GET /summary on empty database should return zeros."""
        with patch(
            "src.api.routes.admin.get_db_path", return_value=temp_db
        ):
            response = client.get(
                "/internal/metrics-a7x9k2/summary",
                headers={"X-Admin-Token": auth_token},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["daily_active_users"] == 0
        assert data["new_users_today"] == 0
        assert data["returning_users_today"] == 0
        assert data["queries_today"] == 0
        assert data["documents_uploaded_today"] == 0
        assert data["total_browsers"] == 0
        assert data["total_sessions"] == 0
        assert data["total_events"] == 0


class TestFeatureUsageMetrics:
    """Tests for feature usage metrics."""

    @pytest.fixture
    def auth_token(self, client):
        """Get a valid admin token."""
        response = client.post(
            "/internal/metrics-a7x9k2/auth",
            json={"password": "change-me-in-production"},
        )
        return response.json()["token"]

    def test_feature_usage_days_parameter(self, client, auth_token, populated_db):
        """GET /feature-usage should accept days parameter."""
        with patch(
            "src.api.routes.admin.get_db_path", return_value=populated_db
        ):
            response = client.get(
                "/internal/metrics-a7x9k2/feature-usage?days=30",
                headers={"X-Admin-Token": auth_token},
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_feature_usage_filters_correct_events(self, client, auth_token, populated_db):
        """GET /feature-usage should only include _requested/_submitted/_completed events."""
        with patch(
            "src.api.routes.admin.get_db_path", return_value=populated_db
        ):
            response = client.get(
                "/internal/metrics-a7x9k2/feature-usage",
                headers={"X-Admin-Token": auth_token},
            )

        assert response.status_code == 200
        data = response.json()

        # Should not include session_started (doesn't match pattern)
        event_names = [entry["feature"] for entry in data]
        assert "session_started" not in event_names

        # Should include _requested and _submitted events
        matching_patterns = [
            name
            for name in event_names
            if "_requested" in name or "_submitted" in name or "_completed" in name
        ]
        assert len(matching_patterns) == len(event_names)
