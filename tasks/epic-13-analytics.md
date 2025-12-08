# Epic 13: User Analytics & Observability

## Overview

Implement user behavior analytics to track sessions, feature usage, and engagement patterns. Data is stored locally in SQLite for sovereignty, with a password-protected admin dashboard for the PM to monitor metrics without external tools.

## Problem Statement

Currently, there's no visibility into:

- How many users are using the application
- Which features are most/least used
- Where users abandon operations
- Whether users return after first visit

**Goal:** Enable data-driven product decisions while respecting sovereignty (no external analytics services).

## Prerequisites

- Epic 11 (Document Preview) completed
- Epic 12 (Progress Indicators) should ideally be completed first to measure its impact
- Existing SQLite infrastructure (`src/db/sqlite.py`)

## Technical Approach

### Session & User Identification (No Auth)

Since there's no authentication:

- **browser_id** (localStorage): Persistent identifier for the browser
- **session_id** (sessionStorage): Single session/tab lifetime
- **returning_user**: Detected by checking if browser_id exists in database

### Privacy by Design

- No PII collected (no question text, no document content)
- Only track: lengths, counts, durations, feature names
- All data stored locally (sovereignty)
- No external analytics services

## User Stories

---

## US 13.1: Analytics Database Schema

**Status:** ✅ Completed

### Description

Create the database schema for storing analytics events, sessions, and browser records with proper indexes for efficient querying.

### Context

The schema needs to support:

1. Raw event storage (append-only log)
2. Session aggregation (for quick session stats)
3. Browser tracking (for returning user detection)

### Tasks

- [ ] Create `analytics_events` table:
  - `id`, `event_name`, `browser_id`, `session_id`, `properties` (JSON), `created_at`
  - Indexes on `browser_id`, `session_id`, `event_name`, `created_at`
- [ ] Create `analytics_sessions` table:
  - `session_id`, `browser_id`, `started_at`, `ended_at`, `is_returning_user`
  - Aggregated counters: `event_count`, `query_count`, `docs_uploaded`
- [ ] Create `analytics_browsers` table:
  - `browser_id`, `first_seen_at`, `last_seen_at`, `total_sessions`
- [ ] Add migration to create tables on startup
- [ ] Add unit tests for schema creation

### Implementation Details

```sql
-- Analytics events (raw log)
CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name TEXT NOT NULL,
    browser_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    properties TEXT DEFAULT '{}',  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_browser ON analytics_events(browser_id);
CREATE INDEX IF NOT EXISTS idx_events_session ON analytics_events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_name ON analytics_events(event_name);
CREATE INDEX IF NOT EXISTS idx_events_created ON analytics_events(created_at);

-- Sessions (aggregated)
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

CREATE INDEX IF NOT EXISTS idx_sessions_browser ON analytics_sessions(browser_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON analytics_sessions(started_at);

-- Browsers (for returning user detection)
CREATE TABLE IF NOT EXISTS analytics_browsers (
    browser_id TEXT PRIMARY KEY,
    first_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_sessions INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_browsers_first_seen ON analytics_browsers(first_seen_at);
```

### Acceptance Criteria

- [ ] All three tables created on application startup
- [ ] Indexes created for common query patterns
- [ ] Migration is idempotent (safe to run multiple times)
- [ ] Existing `documents` table unaffected
- [ ] Unit tests verify schema creation

### Tests

- **Modified:** `tests/test_sqlite.py` - Add analytics schema tests
- **Run:** `pytest tests/test_sqlite.py -v -k analytics`

### Files to Modify

1. `src/db/sqlite.py` - Add analytics table creation to migrations
2. `tests/test_sqlite.py` - Add schema tests

---

## US 13.2: Backend Analytics API

**Status:** ✅ Completed

### Description

Create the backend API endpoint for receiving and storing analytics events, with logic for session management and returning user detection.

### Context

The endpoint must be:

- Fire-and-forget (non-blocking for UI)
- Lightweight (minimal processing)
- Reliable (background task for storage)

### Tasks

- [ ] Create `src/api/routes/analytics.py` router
- [ ] Implement `POST /analytics/events` endpoint:
  - Accept: `event_name`, `browser_id`, `session_id`, `properties`
  - Process in background task (non-blocking)
  - Return immediately with `{"status": "ok"}`
- [ ] Implement `store_event()` background function:
  - Check if browser_id is returning user
  - Upsert browser record
  - Upsert session record (on `session_started` event)
  - Update session counters
  - Store raw event
- [ ] Register router in `src/api/main.py`
- [ ] Add unit tests for analytics endpoint

### Implementation Details

```python
# src/api/routes/analytics.py

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime
import json
import sqlite3

router = APIRouter(tags=["analytics"])


class AnalyticsEvent(BaseModel):
    event_name: str
    browser_id: str
    session_id: str
    properties: dict = {}


@router.post("/analytics/events")
async def track_event(
    event: AnalyticsEvent,
    background_tasks: BackgroundTasks,
):
    """Track analytics event (fire-and-forget)."""
    background_tasks.add_task(store_event, event)
    return {"status": "ok"}


def store_event(event: AnalyticsEvent):
    """Store event in SQLite (runs in background)."""
    from src.db.sqlite import get_db_path

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Check if browser is returning
        cursor.execute(
            "SELECT 1 FROM analytics_browsers WHERE browser_id = ?",
            (event.browser_id,)
        )
        is_returning = cursor.fetchone() is not None

        # 2. Upsert browser record
        cursor.execute("""
            INSERT INTO analytics_browsers (browser_id, first_seen_at, last_seen_at, total_sessions)
            VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
            ON CONFLICT(browser_id) DO UPDATE SET
                last_seen_at = CURRENT_TIMESTAMP,
                total_sessions = total_sessions + CASE
                    WHEN ? = 'session_started' THEN 1
                    ELSE 0
                END
        """, (event.browser_id, event.event_name))

        # 3. Create/update session record
        if event.event_name == 'session_started':
            cursor.execute("""
                INSERT OR IGNORE INTO analytics_sessions
                (session_id, browser_id, started_at, is_returning_user, event_count)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, 0)
            """, (event.session_id, event.browser_id, is_returning))

        # 4. Update session counters
        cursor.execute("""
            UPDATE analytics_sessions SET
                ended_at = CURRENT_TIMESTAMP,
                event_count = event_count + 1,
                query_count = query_count + CASE WHEN ? = 'query_submitted' THEN 1 ELSE 0 END,
                docs_uploaded = docs_uploaded + CASE WHEN ? = 'document_uploaded' THEN 1 ELSE 0 END
            WHERE session_id = ?
        """, (event.event_name, event.event_name, event.session_id))

        # 5. Store raw event
        cursor.execute("""
            INSERT INTO analytics_events (event_name, browser_id, session_id, properties)
            VALUES (?, ?, ?, ?)
        """, (
            event.event_name,
            event.browser_id,
            event.session_id,
            json.dumps(event.properties),
        ))

        conn.commit()
    except Exception as e:
        # Log but don't fail - analytics should never break the app
        import logging
        logging.getLogger(__name__).warning(f"Analytics storage failed: {e}")
    finally:
        conn.close()
```

### Acceptance Criteria

- [ ] `POST /analytics/events` returns 200 immediately
- [ ] Events stored in background (non-blocking)
- [ ] Browser records created/updated correctly
- [ ] Session records created on `session_started`
- [ ] Session counters increment correctly
- [ ] Returning user detected correctly
- [ ] Errors logged but don't crash the app
- [ ] Unit tests pass

### Tests

- **New:** `tests/test_analytics.py` - Test analytics endpoint and storage
- **Run:** `pytest tests/test_analytics.py -v`

### Files to Create/Modify

1. `src/api/routes/analytics.py` - New analytics router
2. `src/api/main.py` - Register analytics router
3. `tests/test_analytics.py` - New tests

---

## US 13.3: Frontend Event Tracking

**Status:** ✅ Completed

### Description

Add JavaScript tracking to the Web UI to capture user behavior events and send them to the backend API.

### Context

Events to track (quick wins first):

1. `session_started` - New session began
2. `session_ended` - Page unload (best effort)
3. `document_uploaded` - File uploaded successfully
4. `document_upload_failed` - Upload failed
5. `query_submitted` - User asked a question
6. `query_completed` - Answer received
7. `query_failed` - Query error
8. `summarize_requested` - Summarize clicked
9. `risks_requested` - Risk analysis clicked
10. `compare_requested` - Compare clicked

### Tasks

- [x] Create `Analytics` JavaScript object:
  - `getBrowserId()` - Get/create persistent browser ID (localStorage)
  - `getSessionId()` - Get/create session ID (sessionStorage)
  - `track(eventName, properties)` - Send event to backend
  - `init()` - Initialize tracking, send `session_started`
- [x] Track session lifecycle:
  - `session_started` on page load
  - `session_ended` on `beforeunload`
- [x] Track document operations:
  - `document_uploaded` with `file_type`, `duration_ms`
  - `document_upload_failed` with `error_type`, `file_type`, `duration_ms`
- [x] Track query operations:
  - `query_submitted` with `question_length`
  - `query_completed` with `duration_ms`, `confidence`, `citation_count`, `language`
  - `query_failed` with `error_type`, `duration_ms`
- [x] Track feature usage:
  - `summarize_requested`, `summarize_completed`, `summarize_failed`
  - `risks_requested`, `risks_completed`, `risks_failed`
  - `compare_requested`, `compare_completed`, `compare_failed`
- [x] Integrate into existing UI functions

### Implementation Details

```javascript
// ui/index.html - Add to <script>

const Analytics = {
  getBrowserId() {
    let browserId = localStorage.getItem('lexard_browser_id');
    if (!browserId) {
      browserId = crypto.randomUUID();
      localStorage.setItem('lexard_browser_id', browserId);
    }
    return browserId;
  },

  getSessionId() {
    let sessionId = sessionStorage.getItem('lexard_session_id');
    if (!sessionId) {
      sessionId = crypto.randomUUID();
      sessionStorage.setItem('lexard_session_id', sessionId);
      // Auto-track session start
      this._send('session_started', {});
    }
    return sessionId;
  },

  track(eventName, properties = {}) {
    // Ensure session is initialized
    this.getSessionId();
    this._send(eventName, properties);
  },

  _send(eventName, properties) {
    const payload = {
      event_name: eventName,
      browser_id: this.getBrowserId(),
      session_id: sessionStorage.getItem('lexard_session_id'),
      properties: properties,
    };

    // Fire-and-forget with keepalive for page unload
    fetch('/analytics/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => {}); // Silently ignore errors
  },

  init() {
    // Initialize session (triggers session_started)
    this.getSessionId();

    // Track session end on page unload
    window.addEventListener('beforeunload', () => {
      this._send('session_ended', {});
    });
  },
};

// Initialize on page load
Analytics.init();
```

### Integration Example

```javascript
// Modify existing askQuestion() function
async function askQuestion() {
    const startTime = Date.now();

    Analytics.track('query_submitted', {
        question_length: question.length,
    });

    try {
        const response = await fetch('/query', { ... });
        const data = await response.json();

        Analytics.track('query_completed', {
            duration_ms: Date.now() - startTime,
            confidence: data.confidence,
            citation_count: data.citation_chunks?.length || 0,
            language: data.language,
        });

        renderAnswer(data);
    } catch (error) {
        Analytics.track('query_failed', {
            error_type: error.message,
            duration_ms: Date.now() - startTime,
        });
        showError(resultBox, error.message);
    }
}
```

### Acceptance Criteria

- [x] `browser_id` persists in localStorage across sessions
- [x] `session_id` is unique per tab/session
- [x] `session_started` fires on page load
- [x] `session_ended` fires on page unload (best effort)
- [x] All document operations tracked
- [x] All query operations tracked with timing
- [x] All feature usage tracked
- [x] Tracking failures don't affect UI functionality
- [x] No PII in tracked data (no question text, no doc content)

### Tests

- **None:** UI-only changes (manual testing)
- **Manual:** Verify events in database via DBeaver
- **Run:** Manual browser testing

### Files to Modify

1. `ui/index.html` - Add Analytics object and tracking calls

---

## US 13.4: Admin Analytics Dashboard

**Status:** 🔲 Not Started

### Description

Create a password-protected admin dashboard page for viewing analytics metrics, accessible via a non-obvious URL.

### Context

Security requirements:

- URL should not be guessable (e.g., `/internal/metrics-a7x9k2` not `/admin`)
- Password protection (simple, no user accounts needed)
- Session-based auth (password checked once, valid for browser session)

### Tasks

- [ ] Create admin dashboard HTML page (`ui/admin-a7x9k2.html`)
- [ ] Add password protection:
  - `POST /internal/metrics-a7x9k2/auth` - Verify password
  - Password stored in config (not hardcoded)
  - Session token stored in sessionStorage
- [ ] Create metrics API endpoints:
  - `GET /internal/metrics-a7x9k2/summary` - Dashboard summary
  - `GET /internal/metrics-a7x9k2/sessions` - Recent sessions
  - `GET /internal/metrics-a7x9k2/events` - Recent events
- [ ] Dashboard displays:
  - Daily active users (browsers)
  - New vs returning users
  - Feature usage breakdown
  - Recent sessions list
  - Query success/failure rates
- [ ] Add password to config.yaml

### Implementation Details

#### Config Addition

```yaml
# config/config.yaml
admin:
  analytics_password: 'change-me-in-production' # MUST be changed
  dashboard_path: 'metrics-a7x9k2' # Non-obvious path segment
```

#### Password Protection Flow

```
1. User visits /internal/metrics-a7x9k2
2. Page checks sessionStorage for valid token
3. If no token → show password form
4. On submit → POST /internal/metrics-a7x9k2/auth with password
5. If correct → receive token, store in sessionStorage, show dashboard
6. If wrong → show error
7. All /internal/metrics-a7x9k2/* endpoints require valid token header
```

#### Backend Auth Endpoint

```python
# src/api/routes/admin.py

from fastapi import APIRouter, HTTPException, Header, Depends
from src.config import get_settings
import secrets
import hashlib

router = APIRouter(tags=["admin"], prefix="/internal/metrics-a7x9k2")

# In-memory token store (simple, resets on restart)
_valid_tokens: set[str] = set()


@router.post("/auth")
async def authenticate(password: str):
    """Verify admin password and return session token."""
    settings = get_settings()

    if password != settings.admin.analytics_password:
        raise HTTPException(status_code=401, detail="Invalid password")

    # Generate session token
    token = secrets.token_urlsafe(32)
    _valid_tokens.add(token)

    return {"token": token}


def require_admin_token(x_admin_token: str = Header(...)):
    """Dependency to verify admin token."""
    if x_admin_token not in _valid_tokens:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return True


@router.get("/summary")
async def get_summary(_: bool = Depends(require_admin_token)):
    """Get dashboard summary metrics."""
    # ... query database for metrics
    pass


@router.get("/sessions")
async def get_sessions(
    limit: int = 50,
    _: bool = Depends(require_admin_token),
):
    """Get recent sessions."""
    # ... query database
    pass
```

#### Dashboard HTML Structure

```html
<!-- ui/admin-a7x9k2.html -->
<!DOCTYPE html>
<html>
  <head>
    <title>Lexard Analytics</title>
    <!-- Styles -->
  </head>
  <body>
    <!-- Password Form (shown initially) -->
    <div id="auth-form">
      <h1>Analytics Dashboard</h1>
      <input type="password" id="password" placeholder="Password" />
      <button onclick="authenticate()">Login</button>
      <p id="auth-error" style="color: red; display: none;"></p>
    </div>

    <!-- Dashboard (hidden until authenticated) -->
    <div id="dashboard" style="display: none;">
      <h1>Lexard Analytics</h1>

      <!-- Summary Cards -->
      <div class="metrics-grid">
        <div class="metric-card">
          <h3>Daily Active Users</h3>
          <p id="dau">-</p>
        </div>
        <div class="metric-card">
          <h3>New Users Today</h3>
          <p id="new-users">-</p>
        </div>
        <div class="metric-card">
          <h3>Returning Users</h3>
          <p id="returning-users">-</p>
        </div>
        <div class="metric-card">
          <h3>Queries Today</h3>
          <p id="queries-today">-</p>
        </div>
      </div>

      <!-- Feature Usage -->
      <div class="section">
        <h2>Feature Usage (Last 7 Days)</h2>
        <table id="feature-usage">
          <tr>
            <th>Feature</th>
            <th>Usage Count</th>
            <th>Unique Sessions</th>
          </tr>
        </table>
      </div>

      <!-- Recent Sessions -->
      <div class="section">
        <h2>Recent Sessions</h2>
        <table id="sessions-table">
          <tr>
            <th>Session</th>
            <th>Started</th>
            <th>Queries</th>
            <th>Returning</th>
          </tr>
        </table>
      </div>
    </div>

    <script>
      let adminToken = sessionStorage.getItem('lexard_admin_token');

      if (adminToken) {
        showDashboard();
      }

      async function authenticate() {
        const password = document.getElementById('password').value;

        try {
          const response = await fetch('/internal/metrics-a7x9k2/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password }),
          });

          if (!response.ok) {
            document.getElementById('auth-error').textContent =
              'Invalid password';
            document.getElementById('auth-error').style.display = 'block';
            return;
          }

          const data = await response.json();
          adminToken = data.token;
          sessionStorage.setItem('lexard_admin_token', adminToken);
          showDashboard();
        } catch (error) {
          document.getElementById('auth-error').textContent =
            'Connection error';
          document.getElementById('auth-error').style.display = 'block';
        }
      }

      async function showDashboard() {
        document.getElementById('auth-form').style.display = 'none';
        document.getElementById('dashboard').style.display = 'block';
        await loadMetrics();
      }

      async function loadMetrics() {
        const headers = { 'X-Admin-Token': adminToken };

        // Load summary
        const summary = await fetch('/internal/metrics-a7x9k2/summary', {
          headers,
        }).then((r) => r.json());
        document.getElementById('dau').textContent = summary.daily_active_users;
        document.getElementById('new-users').textContent =
          summary.new_users_today;
        document.getElementById('returning-users').textContent =
          summary.returning_users_today;
        document.getElementById('queries-today').textContent =
          summary.queries_today;

        // Load sessions
        const sessions = await fetch('/internal/metrics-a7x9k2/sessions', {
          headers,
        }).then((r) => r.json());
        // ... render sessions table
      }
    </script>
  </body>
</html>
```

### Acceptance Criteria

- [ ] Dashboard accessible at non-obvious URL (`/internal/metrics-a7x9k2`)
- [ ] Password required to view (from config, not hardcoded)
- [ ] Session token persists in browser session (no re-auth per page load)
- [ ] Token validated on all metrics endpoints
- [ ] Dashboard shows:
  - Daily active users
  - New vs returning users
  - Feature usage breakdown
  - Recent sessions
- [ ] Auto-refresh every 60 seconds (optional)
- [ ] Logout clears token

### Tests

- **New:** `tests/test_admin.py` - Test auth and metrics endpoints
- **Run:** `pytest tests/test_admin.py -v`

### Files to Create/Modify

1. `src/api/routes/admin.py` - New admin router
2. `ui/admin-a7x9k2.html` - New dashboard page
3. `src/api/main.py` - Register admin router, serve admin page
4. `config/config.yaml` - Add admin password config
5. `src/config.py` - Add admin config model
6. `tests/test_admin.py` - New tests

---

## Definition of Done (Epic 13)

- [ ] All 4 User Stories completed
- [ ] Analytics tables created in SQLite
- [ ] Events tracked from UI and stored in database
- [ ] Session/browser identification working
- [ ] Returning user detection accurate
- [ ] Admin dashboard accessible with password
- [ ] All tests pass
- [ ] Password changed from default in production config

## Security Considerations

| Risk                     | Mitigation                             |
| ------------------------ | -------------------------------------- |
| Dashboard URL guessed    | Non-obvious path segment               |
| Password brute force     | Rate limiting (optional, future)       |
| Token stolen             | Session-only, expires on browser close |
| Analytics endpoint abuse | Fire-and-forget, no response data      |

## DBeaver Quick Queries (for PM)

```sql
-- Daily Active Users
SELECT DATE(created_at) as day, COUNT(DISTINCT browser_id) as users
FROM analytics_events
WHERE created_at >= DATE('now', '-30 days')
GROUP BY day ORDER BY day DESC;

-- Returning vs New
SELECT
    DATE(started_at) as day,
    SUM(is_returning_user) as returning,
    SUM(NOT is_returning_user) as new
FROM analytics_sessions
GROUP BY day ORDER BY day DESC;

-- Feature Adoption
SELECT event_name, COUNT(*) as count
FROM analytics_events
WHERE event_name LIKE '%_requested' OR event_name LIKE '%_submitted'
GROUP BY event_name ORDER BY count DESC;
```

## Dependencies

```
US 13.1 (Schema)
    ↓
US 13.2 (Backend API)
    ↓
US 13.3 (Frontend Tracking)
    ↓
US 13.4 (Admin Dashboard)
```
