# Epic 14: Temporary Internet Exposure

## Overview

Enable secure temporary internet exposure of the Lexard UI for external testers. This epic adds password protection to the main UI (reusing the admin password) and provides documentation for setting up a Cloudflare Tunnel for secure, zero-trust access without exposing the home IP or opening router ports.

## Prerequisites

- Epic 13 completed (analytics dashboard with password auth pattern)
- Cloudflare account (free tier sufficient)
- `cloudflared` CLI tool

## User Stories

---

## US 14.1: UI Password Protection

**Status:** ✅ Completed

### Description

Add a login gate to the main UI that requires the admin password before granting access. This ensures only authorized testers can use the application when exposed to the internet.

### Context

Currently, the main UI at `/` is publicly accessible without authentication. The admin dashboard already has password protection using `admin.analytics_password` from config. We'll reuse the same password for the main UI, with a simple login page that stores authenticated state in localStorage. This is UI-only protection (APIs remain open) - sufficient for demo purposes since Cloudflare Tunnel controls network access.

### Tasks

- [x] Create login HTML page (`ui/login.html`) with password form
- [x] Modify `index.html` to check auth state and redirect to login if needed
- [x] Add logout button to main UI
- [x] Reuse existing admin auth endpoint for password verification

### Implementation Details

**Auth Flow (Simple):**
```
[User visits /] → [JS checks localStorage.authenticated]
    ↓ not set                    ↓ is set
[Redirect to /login]         [Show UI]
    ↓
[Enter password]
    ↓
[POST to existing admin auth endpoint]
    ↓ success
[Set localStorage.authenticated = true, redirect to /]
```

**Key Simplifications:**
- Reuse existing `/internal/{dashboard_path}/auth` endpoint from admin.py
- Store simple boolean flag in localStorage (not token)
- No new API endpoints needed
- Password verification happens client-side via existing admin auth

### Acceptance Criteria

- [x] Visiting `/` without auth redirects to `/login`
- [x] Login page accepts password and redirects to `/` on success
- [x] Invalid password shows error message
- [x] Valid session persists across page refreshes (localStorage)
- [x] Logout clears session and redirects to login
- [x] Same password works for both main UI and admin dashboard

### Tests

- **Manual:** Test login flow in browser
- **Existing:** Admin auth endpoint already tested

### Files to Create/Modify

1. `ui/login.html` - New login page
2. `ui/index.html` - Add auth check on load + logout button
3. `src/api/routes/static.py` - Add login route

---

## US 14.2: Cloudflare Tunnel Setup Guide

**Status:** 🔶 In Progress

### Description

Provide comprehensive documentation and helper scripts for setting up Cloudflare Tunnel to securely expose the application to the internet without port forwarding or exposing the home IP address.

### Context

Cloudflare Tunnel (formerly Argo Tunnel) creates an outbound-only connection from the local machine to Cloudflare's edge network. This means:
- No inbound ports need to be opened
- Home IP address remains hidden
- Automatic HTTPS with valid certificates
- Easy to start/stop (just kill the process)

### Tasks

- [ ] Create `docs/INTERNET_EXPOSURE.md` with step-by-step setup guide
- [ ] Create `scripts/tunnel.sh` helper script for starting tunnel
- [ ] Document security checklist (password change, monitoring, shutdown)
- [ ] Add troubleshooting section for common issues

### Implementation Details

**Documentation Structure:**

```markdown
# Internet Exposure Guide

## Prerequisites
- Cloudflare account (free)
- Domain added to Cloudflare (or use *.trycloudflare.com for quick testing)

## Quick Start (No Domain Required)
cloudflared tunnel --url http://localhost:8000

## Production Setup (With Domain)
1. Install cloudflared
2. Login: cloudflared login
3. Create tunnel: cloudflared tunnel create lexard-demo
4. Configure DNS
5. Run tunnel

## Security Checklist
- [ ] Changed default password in config.yaml
- [ ] Noted the public URL
- [ ] Tested login works
- [ ] Know how to stop (Ctrl+C or kill process)

## Shutdown
- Stop tunnel: Ctrl+C or `pkill cloudflared`
- Tunnel stops = instant disconnection, no cleanup needed
```

**Helper Script (`scripts/tunnel.sh`):**

```bash
#!/bin/bash
# Start Cloudflare Tunnel for Lexard
# Usage: ./scripts/tunnel.sh [--quick]

if [ "$1" == "--quick" ]; then
    # Quick mode: temporary URL, no setup required
    echo "Starting quick tunnel (temporary URL)..."
    cloudflared tunnel --url http://localhost:8000
else
    # Named tunnel mode (requires prior setup)
    cloudflared tunnel run lexard-demo
fi
```

### Acceptance Criteria

- [ ] `docs/INTERNET_EXPOSURE.md` contains complete setup instructions
- [ ] Quick-start option works without domain (trycloudflare.com)
- [ ] Production setup documented for custom domain
- [ ] Security checklist included
- [ ] Shutdown/cleanup instructions clear
- [ ] `scripts/tunnel.sh` helper script works

### Tests

- **Manual:** Follow the quick-start guide and verify access works
- **No automated tests** (infrastructure documentation)

### Files to Create/Modify

1. `docs/INTERNET_EXPOSURE.md` - Complete setup guide
2. `scripts/tunnel.sh` - Helper script for starting tunnel

---

## Definition of Done (Epic 14)

- [ ] All User Stories completed (2/2 US)
- [ ] Main UI requires password to access (UI-only gate)
- [ ] Same password works for UI and admin dashboard
- [ ] Cloudflare Tunnel documentation complete
- [ ] Helper script for easy tunnel startup
- [ ] Security checklist documented
