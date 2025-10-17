# Traefik HTTPS Deployment Guide

## Quick Deploy to waugh.cloud

### Prerequisites
- Traefik running on waugh.cloud (100.100.2.2)
- Docker network `traefik_network` exists
- DNS: `dashboard.waugh.cloud` points to your VPS

### Step 1: Build the Image
```bash
docker build -t ticket-dashboard:latest .
```

### Step 2: Deploy with Traefik
```bash
# On waugh.cloud VPS
docker-compose -f docker-compose.traefik.yml up -d
```

### Step 3: Verify
```bash
# Check container is running
docker ps | grep ticket-dashboard

# Check Traefik routing
docker logs traefik | grep dashboard

# Test health endpoint
curl http://localhost:8080/health
```

### Step 4: Access
Open: **https://dashboard.waugh.cloud**

---

## Traefik Configuration

The service is configured with:
- **Domain:** `dashboard.waugh.cloud`
- **HTTPS:** Automatic via Let's Encrypt
- **HTTP → HTTPS:** Automatic redirect
- **Port:** Internal 8080 (not exposed externally)
- **Health Check:** `/health` endpoint every 30s

### Traefik Labels Applied:
```yaml
traefik.enable=true
traefik.http.routers.dashboard-https.rule=Host(`dashboard.waugh.cloud`)
traefik.http.routers.dashboard-https.entrypoints=websecure
traefik.http.routers.dashboard-https.tls.certresolver=letsencrypt
```

---

## Troubleshooting

### Container won't start:
```bash
docker logs ticket-dashboard
```

### Traefik not routing:
```bash
# Check Traefik can see the service
docker exec traefik cat /etc/traefik/traefik.yml

# Verify network connection
docker network inspect traefik_network | grep ticket-dashboard
```

### SSL certificate issues:
```bash
# Check Traefik ACME storage
docker exec traefik ls -la /letsencrypt/acme.json
```

### Force rebuild and redeploy:
```bash
docker-compose -f docker-compose.traefik.yml down
docker build --no-cache -t ticket-dashboard:latest .
docker-compose -f docker-compose.traefik.yml up -d
```

---

## Environment Variables

Create `.env` file on waugh.cloud:
```bash
FLASK_SECRET_KEY=your-secret-key-here
HUBSPOT_API_KEY=your-hubspot-key
LIVECHAT_PAT=your-livechat-token
GOOGLE_SHEETS_SPREADSHEET_ID=your-sheet-id
ADMIN_PASSWORD=your-admin-password
GEMINI_API_KEY=your-gemini-key
```

---

## Quick Commands

### Deploy:
```bash
docker-compose -f docker-compose.traefik.yml up -d
```

### Stop:
```bash
docker-compose -f docker-compose.traefik.yml down
```

### Restart:
```bash
docker-compose -f docker-compose.traefik.yml restart
```

### View logs:
```bash
docker-compose -f docker-compose.traefik.yml logs -f
```

### Update after code changes:
```bash
docker build -t ticket-dashboard:latest .
docker-compose -f docker-compose.traefik.yml up -d --force-recreate