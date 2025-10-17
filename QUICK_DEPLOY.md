# Quick Deploy to waugh.cloud

## From loom to waugh.cloud:

### Step 1: Transfer files
```bash
# From loom
scp docker-compose.traefik.yml Dockerfile requirements.txt .env root@waugh.cloud:/root/ticket-dashboard/
scp -r . root@waugh.cloud:/root/ticket-dashboard/
```

### Step 2: SSH to waugh.cloud and build
```bash
ssh root@waugh.cloud
cd /root/ticket-dashboard
docker build -t ticket-dashboard:latest .
```

### Step 3: Deploy
```bash
docker-compose -f docker-compose.traefik.yml up -d
```

### Step 4: Verify
```bash
docker ps | grep ticket-dashboard
docker logs ticket-dashboard
curl http://localhost:8080/health
```

### Access:
https://dashboard.waugh.cloud

---

## ONE-LINE DEPLOY:

```bash
./deploy-to-waugh.sh
```

---

## If container won't start:

```bash
# Check logs
docker-compose -f docker-compose.traefik.yml logs

# Check if FLASK_SECRET_KEY is set
docker-compose -f docker-compose.traefik.yml config | grep FLASK_SECRET_KEY