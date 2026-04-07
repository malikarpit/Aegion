#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Aegion Environment Bootstrap...${NC}"

# 1. Check Prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: docker is not installed.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Warning: docker-compose not found, trying 'docker compose'...${NC}"
    if ! docker compose version &> /dev/null; then
        echo -e "${RED}Error: docker compose is not available.${NC}"
        exit 1
    fi
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# 2. Setup Environment Variables
echo -e "\n${YELLOW}Setting up environment variables...${NC}"
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "Creating .env from .env.example"
        cp .env.example .env
    else
        echo -e "${RED}Error: .env.example not found.${NC}"
        exit 1
    fi
else
    echo ".env already exists."
fi

# 3. Build and Start Services
echo -e "\n${YELLOW}Building and starting services...${NC}"
$DOCKER_COMPOSE down --remove-orphans
$DOCKER_COMPOSE build
$DOCKER_COMPOSE up -d

# 4. Wait for Health Checks
echo -e "\n${YELLOW}Waiting for services to be ready...${NC}"
MAX_RETRIES=30
RETRY_COUNT=0
BACKEND_URL="http://localhost:8000/api/v1/health/ready"

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s "$BACKEND_URL" | grep -q '"status":"healthy"'; then
        echo -e "${GREEN}✅ Backend is healthy!${NC}"
        echo -e "\n${GREEN}🎉 Aegion Environment is Ready!${NC}"
        echo -e "Backend:    http://localhost:8000"
        echo -e "Docs:       http://localhost:8000/docs"
        echo -e "Neo4j:      http://localhost:7474"
        echo -e "Redis:      localhost:6379"
        exit 0
    fi
    echo -n "."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT+1))
done

echo -e "\n${RED}❌ Timeout waiting for backend health.${NC}"
$DOCKER_COMPOSE logs --tail=50 backend
exit 1
