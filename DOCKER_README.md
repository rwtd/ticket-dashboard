# 🐳 Docker Deployment Guide

## Quick Deploy

### From Docker Hub
```bash
# Pull and run (replace YOUR_USERNAME)
docker pull YOUR_USERNAME/ticket-dashboard:latest
docker run -d -p 8080:8080 --name ticket-dashboard YOUR_USERNAME/ticket-dashboard:latest

# Access at http://localhost:8080
```

### Build Locally
```bash
git clone https://github.com/YOUR_USERNAME/ticket-dashboard.git
cd ticket-dashboard
docker build -t ticket-dashboard .
docker run -d -p 8080:8080 ticket-dashboard
```

## Container Details
- **Port**: 8080
- **Server**: Gunicorn
- **Base**: python:3.11-slim
- **Size**: ~1.4GB
- **User**: Non-root (appuser)

## What's Included
✅ Complete analytics dashboard
✅ All Python dependencies
✅ Web interface on port 8080
✅ File upload functionality
✅ Interactive charts with Plotly
✅ Export capabilities

## Environment Variables
```bash
# Optional configurations
docker run -d -p 8080:8080 \
  -e GEMINI_API_KEY="your-api-key" \
  -e CHART_MODE="interactive" \
  YOUR_USERNAME/ticket-dashboard:latest
```

## Data Persistence
Mount volumes for data persistence:
```bash
docker run -d -p 8080:8080 \
  -v $(pwd)/data:/app/uploads \
  -v $(pwd)/results:/app/results \
  YOUR_USERNAME/ticket-dashboard:latest
```

## Health Check
```bash
curl http://localhost:8080/
# Should return the dashboard HTML
```