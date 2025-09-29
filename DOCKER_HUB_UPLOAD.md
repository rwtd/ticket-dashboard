# Docker Hub Upload Instructions

## Prerequisites
1. Create a Docker Hub account at https://hub.docker.com/
2. Log in to Docker Hub from your terminal

## Step-by-Step Upload Process

### 1. Login to Docker Hub
```bash
docker login
# Enter your Docker Hub username and password when prompted
```

### 2. Tag your image for Docker Hub
```bash
# Replace YOUR_USERNAME with your Docker Hub username
docker tag ticket-dashboard:working YOUR_USERNAME/ticket-dashboard:latest
docker tag ticket-dashboard:working YOUR_USERNAME/ticket-dashboard:v1.0
```

### 3. Push to Docker Hub
```bash
# Push both tags
docker push YOUR_USERNAME/ticket-dashboard:latest
docker push YOUR_USERNAME/ticket-dashboard:v1.0
```

### 4. Verify Upload
Visit https://hub.docker.com/r/YOUR_USERNAME/ticket-dashboard to see your uploaded image

## Usage by Others
Others can now pull and run your image with:
```bash
# Pull the image
docker pull YOUR_USERNAME/ticket-dashboard:latest

# Run the container
docker run -d -p 8080:8080 --name ticket-dashboard YOUR_USERNAME/ticket-dashboard:latest
```

## Image Details
- **Base Image**: python:3.11-slim
- **Port**: 8080
- **Server**: Gunicorn
- **Size**: ~1.4GB (includes all analytics dependencies)
- **Features**: Complete ticket analytics dashboard with web UI

## Tags Explanation
- `latest`: Most recent stable version
- `v1.0`: Version 1.0 with Docker deployment fixes