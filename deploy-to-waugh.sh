#!/bin/bash
# Quick deployment script for waugh.cloud
# Usage: ./deploy-to-waugh.sh

set -e

echo "🔥 Deploying Ticket Dashboard to waugh.cloud..."
echo "================================================"

# Check if we're on the VPS or need to SSH
if [ "$(hostname)" = "waugh" ] || [ "$(hostname)" = "waugh.cloud" ]; then
    echo "✅ Running on VPS"
    LOCAL_DEPLOY=true
else
    echo "📡 Deploying from remote machine"
    LOCAL_DEPLOY=false
    VPS_HOST="waugh.cloud"
    
    # Check if Tailscale IP is reachable
    if ping -c 1 100.100.2.2 &> /dev/null; then
        echo "✅ Tailscale connection active"
        VPS_HOST="waugh.cloud"
    fi
fi

# Build the Docker image
echo ""
echo "🔨 Building Docker image..."
docker build -t ticket-dashboard:latest .

if [ "$LOCAL_DEPLOY" = false ]; then
    # Save and transfer image to VPS
    echo ""
    echo "📦 Saving image for transfer..."
    docker save ticket-dashboard:latest | gzip > /tmp/ticket-dashboard.tar.gz
    
    echo "📤 Transferring to VPS..."
    scp /tmp/ticket-dashboard.tar.gz ${VPS_HOST}:/tmp/
    
    echo "📥 Loading image on VPS..."
    ssh ${VPS_HOST} "docker load < /tmp/ticket-dashboard.tar.gz && rm /tmp/ticket-dashboard.tar.gz"
    
    echo "📋 Transferring docker-compose file..."
    scp docker-compose.traefik.yml ${VPS_HOST}:~/ticket-dashboard/
    
    echo "🚀 Deploying on VPS..."
    ssh ${VPS_HOST} "cd ~/ticket-dashboard && docker-compose -f docker-compose.traefik.yml up -d"
    
    rm /tmp/ticket-dashboard.tar.gz
else
    # Local deployment
    echo ""
    echo "🚀 Deploying locally..."
    docker-compose -f docker-compose.traefik.yml up -d
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Your dashboard is available at:"
echo "   https://dashboard.waugh.cloud"
echo ""
echo "📊 Health check:"
echo "   curl https://dashboard.waugh.cloud/health"
echo ""
echo "📝 View logs:"
echo "   docker-compose -f docker-compose.traefik.yml logs -f"
