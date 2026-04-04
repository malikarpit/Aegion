#!/bin/bash
# Start Aegion Operational Harness
# Launches Backend + Neo4j + Redis + Prometheus + Grafana + Jaeger

set -e

echo "🚀 Starting Aegion Ops Stack..."
echo "📦 Services: Backend, Neo4j, Redis, Prometheus, Grafana, Jaeger"

# Ensure docker daemon is running
if ! docker info > /dev/null 2>&1; then
  echo "❌ Docker is not running. Please start Docker."
  exit 1
fi

# Run docker-compose with both config files
docker-compose -f docker-compose.yml -f docker-compose.ops.yml up -d

echo ""
echo "✅ Stack is running!"
echo "🔗 Backend:     http://localhost:8000"
echo "🔗 Neo4j:       http://localhost:7474"
echo "🔗 Prometheus:  http://localhost:9090"
echo "🔗 Grafana:     http://localhost:3000 (admin/aegion-dev)"
echo "🔗 Jaeger:      http://localhost:16686"
echo ""
echo "Use 'docker-compose logs -f' to follow logs."
