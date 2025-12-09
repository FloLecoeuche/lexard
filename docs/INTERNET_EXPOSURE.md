# Internet Exposure Guide

This guide explains how to securely expose your Lexard instance to the internet for external testers using Cloudflare Tunnel. This approach provides zero-trust access without exposing your home IP or opening router ports.

## Overview

Cloudflare Tunnel creates an **outbound-only** connection from your local machine to Cloudflare's edge network. Benefits:

- **No inbound ports** - Your firewall stays closed
- **IP hidden** - Your home/office IP is never exposed
- **Automatic HTTPS** - Valid SSL certificates provided by Cloudflare
- **Easy control** - Stop the tunnel process = instant disconnection

## Prerequisites

- **Lexard running locally** on port 8000 (default)
- **Cloudflare account** (free tier is sufficient)
- **cloudflared CLI** installed on your machine

### Installing cloudflared

**Linux (Debian/Ubuntu):**
```bash
# Using package manager
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared jammy main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update
sudo apt install cloudflared

# Or download directly
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
```

**macOS:**
```bash
brew install cloudflared
```

**Windows:**
```powershell
# Using winget
winget install --id Cloudflare.cloudflared

# Or download from GitHub releases
# https://github.com/cloudflare/cloudflared/releases
```

Verify installation:
```bash
cloudflared --version
```

---

## Quick Start (No Domain Required)

The fastest way to expose Lexard - no Cloudflare account login required:

```bash
# Make sure Lexard is running
docker-compose up -d

# Start the tunnel (generates a random URL)
cloudflared tunnel --url http://localhost:8000
```

You'll see output like:
```
2024-01-15T10:30:00Z INF +-----------------------------------------------------------+
2024-01-15T10:30:00Z INF |  Your quick Tunnel has been created! Visit it at:        |
2024-01-15T10:30:00Z INF |  https://random-words-here.trycloudflare.com             |
2024-01-15T10:30:00Z INF +-----------------------------------------------------------+
```

Share this URL with testers. The tunnel stays active as long as the process runs.

**Using the helper script:**
```bash
./scripts/tunnel.sh --quick
```

---

## Production Setup (With Custom Domain)

For a stable, memorable URL like `demo.yourdomain.com`:

### Step 1: Login to Cloudflare

```bash
cloudflared login
```

This opens a browser to authenticate with your Cloudflare account. Select the domain you want to use.

### Step 2: Create a Named Tunnel

```bash
cloudflared tunnel create lexard-demo
```

This creates a tunnel and saves credentials to `~/.cloudflared/`.

### Step 3: Configure DNS

```bash
# Create a CNAME record pointing to your tunnel
cloudflared tunnel route dns lexard-demo demo.yourdomain.com
```

### Step 4: Create Tunnel Configuration

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: lexard-demo
credentials-file: /home/YOUR_USER/.cloudflared/TUNNEL_ID.json

ingress:
  - hostname: demo.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

Replace:
- `YOUR_USER` with your username
- `TUNNEL_ID` with the ID from `cloudflared tunnel list`

### Step 5: Run the Tunnel

```bash
cloudflared tunnel run lexard-demo
```

Or use the helper script:
```bash
./scripts/tunnel.sh
```

---

## Security Checklist

Before exposing Lexard to the internet, complete this checklist:

### Required Steps

- [ ] **Change the default password**
  ```yaml
  # config/config.yaml
  admin:
    analytics_password: "YOUR_STRONG_PASSWORD_HERE"  # NOT "admin123"
  ```

- [ ] **Restart the application** after changing password
  ```bash
  docker-compose restart api
  ```

- [ ] **Test login works** with new password at `/login`

- [ ] **Note the public URL** for sharing with testers

- [ ] **Know how to stop** the tunnel (see Shutdown section)

### Recommended Steps

- [ ] **Limit testing duration** - Only run tunnel when actively testing

- [ ] **Monitor access** - Watch cloudflared logs for connection attempts

- [ ] **Use quick tunnel for short tests** - Random URLs are harder to discover

- [ ] **Change password after testing** - Rotate credentials when done

---

## Monitoring Access

Watch tunnel logs for connection information:

```bash
# Quick tunnel shows connections in terminal
cloudflared tunnel --url http://localhost:8000

# Named tunnel with verbose logging
cloudflared tunnel --loglevel debug run lexard-demo
```

Check Cloudflare dashboard for detailed analytics:
1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Navigate to **Zero Trust** > **Access** > **Tunnels**
3. Click on your tunnel name for connection metrics

---

## Shutdown

### Stop the Tunnel

**Method 1: Keyboard interrupt**
```bash
# In the terminal running cloudflared
Ctrl+C
```

**Method 2: Kill the process**
```bash
pkill cloudflared
```

**Method 3: Find and kill by PID**
```bash
ps aux | grep cloudflared
kill <PID>
```

### What Happens When You Stop

- **Instant disconnection** - All active connections terminate immediately
- **URL becomes unreachable** - Returns connection error
- **No cleanup needed** - Tunnel state is ephemeral (for quick tunnels)
- **DNS remains** (named tunnels) - But points to nothing until tunnel restarts

### Complete Teardown (Named Tunnels Only)

If you want to fully remove a named tunnel:

```bash
# Delete the tunnel
cloudflared tunnel delete lexard-demo

# Remove DNS record (optional - can also do via dashboard)
cloudflared tunnel route dns --remove demo.yourdomain.com
```

---

## Troubleshooting

### Tunnel won't start

**Error: "failed to connect to edge"**
```
Check your internet connection and firewall settings.
Cloudflared needs outbound access to Cloudflare's network.
```

**Error: "bind: address already in use"**
```bash
# Another cloudflared might be running
pkill cloudflared
# Try again
```

### Can't access the URL

**Browser shows "Connection refused"**
- Verify Lexard is running: `docker-compose ps`
- Check API is accessible locally: `curl http://localhost:8000/health`

**Browser shows Cloudflare error page**
- Tunnel might have crashed - check terminal for errors
- Restart the tunnel

### Login page not working

**Password rejected but is correct**
- Check API is running: `docker-compose ps api`
- Verify password in config: `grep analytics_password config/config.yaml`
- Restart API after config change: `docker-compose restart api`

**Redirect loop (keeps going back to login)**
- Clear browser localStorage: DevTools > Application > Local Storage > Clear
- Try incognito/private browsing window

### Slow performance

**Pages load slowly through tunnel**
- This is normal - adds latency for the round trip to Cloudflare
- Quick tunnels may be slower than named tunnels
- Consider using a named tunnel with closer Cloudflare region

### Named tunnel issues

**Error: "tunnel not found"**
```bash
# List available tunnels
cloudflared tunnel list

# Make sure tunnel name matches
cloudflared tunnel run <exact-tunnel-name>
```

**Error: "credentials file not found"**
```bash
# Check credentials exist
ls ~/.cloudflared/

# Re-create tunnel if missing
cloudflared tunnel delete <name>
cloudflared tunnel create <name>
```

---

## FAQ

**Q: Is this secure enough for production?**

A: This setup is designed for **demo/testing purposes**. For production:
- Add API authentication (currently APIs are open)
- Implement rate limiting
- Use Cloudflare Access policies
- Enable audit logging

**Q: Can I restrict who can access?**

A: Yes, with Cloudflare Access (Zero Trust):
1. Go to Cloudflare Dashboard > Zero Trust > Access > Applications
2. Create an application for your tunnel hostname
3. Add access policies (email domain, specific emails, etc.)

**Q: Does this work behind corporate firewalls?**

A: Usually yes - cloudflared uses outbound HTTPS (port 443), which most firewalls allow. If blocked, try:
```bash
cloudflared tunnel --edge-ip-version 4 --protocol http2
```

**Q: Can multiple people access at once?**

A: Yes, Cloudflare handles multiple concurrent connections.

**Q: Will my URL change?**

A: Quick tunnels get a new random URL each time. Named tunnels keep the same URL.

---

## Additional Resources

- [Cloudflare Tunnel Documentation](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [cloudflared GitHub Repository](https://github.com/cloudflare/cloudflared)
- [Cloudflare Zero Trust](https://developers.cloudflare.com/cloudflare-one/)
