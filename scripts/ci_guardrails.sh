#!/bin/bash
set -e

echo "🛡️  Aegion Phase 0 Guardrails"
echo "============================="

# 1. Python Compilation Check (Backend)
echo "🐍 Checking Python Compilation..."
if python3 -m compileall -q aegion-backend/app; then
    echo "✅ Python compilation passed."
else
    echo "❌ Python compilation failed."
    exit 1
fi

# 2. Forbidden Capability Check (Grep)
echo "🕵️  Checking for Forbidden Capabilities..."
# We explicitly forbid AgentCapability.APPROVE in orchestrator code except in specific allowed definition files
if grep -r "AgentCapability.APPROVE" aegion-backend/app/adapters/langgraph/orchestrator.py; then
   echo "❌ Forbidden capability 'APPROVE' found in orchestrator.py"
   exit 1
else
   echo "✅ No forbidden capabilities found in orchestrator."
fi

# 3. Health Endpoint Contract Check
echo "🏥 Checking Health Endpoint Contracts..."
# Check Dockerfile
if grep -q "/api/v1/health" aegion-backend/Dockerfile; then
    echo "✅ Dockerfile uses /api/v1/health"
else
    echo "❌ Dockerfile missing /api/v1/health"
    exit 1
fi

# Check Docker Compose
if grep -q "/api/v1/health" docker-compose.yml; then
    echo "✅ Docker Compose uses /api/v1/health"
else
    echo "❌ Docker Compose missing /api/v1/health"
    exit 1
fi

echo "============================="
echo "🎉 All Phase 0 Guardrails Passed!"
