#!/bin/bash
set -e

# Deploy script for lang-forge on HostGator VPS
# Run this on your local machine

VPS_IP="143.95.214.60"
VPS_USER="root"  # Adjust if you use a different user
PROJECT_DIR="/opt/lang-forge"

echo "🚀 Deploying lang-forge to VPS..."

# 1. Build frontend (Astro)
echo "📦 Building Astro frontend..."
cd frontend
pnpm install
pnpm build
cd ..

# 2. Sync files to VPS
echo "📤 Syncing files to VPS..."
rsync -avz --delete \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.env' \
  --exclude='data/*.db' \
  ./ ${VPS_USER}@${VPS_IP}:${PROJECT_DIR}/

# 3. SSH into VPS and rebuild containers
echo "🐳 Rebuilding Docker containers on VPS..."
ssh ${VPS_USER}@${VPS_IP} << 'ENDSSH'
  cd /opt/lang-forge
  
  # Pull latest and rebuild
  docker-compose down
  docker-compose build --no-cache
  docker-compose up -d
  
  # Wait for health check
  echo "⏳ Waiting for service to be healthy..."
  sleep 10
  
  # Check status
  docker-compose ps
  docker-compose logs --tail=20
  
  echo "✅ Deploy complete!"
ENDSSH

echo "🎉 Deploy finished!"
echo "🌐 Check: https://forge.novasanchez.com/health"
