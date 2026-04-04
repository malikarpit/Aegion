#!/bin/bash
set -e

# Run backend tests inside Docker container
# This ensures tests run in the exact production-like environment (locked dependencies)

echo "🐳 Building test environment..."
docker-compose build backend

echo "🧪 Running tests in container..."
docker-compose run --rm \
  -e ENVIRONMENT=test \
  -e POSTGRES_HOST=postgres \
  backend \
  poetry run pytest tests/unit tests/integration --ignore=tests/quarantine
