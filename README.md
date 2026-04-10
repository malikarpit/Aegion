# Aegion — Where Every Software Decision Gains Memory, Governance, and Meaning.

**A governed multi-agent AI council that turns decisions into lasting architectural memory.**

Aegion combines cutting-edge Cost Optimization (FrugalGPT) with Multi-Agent debate. It injects governance directly into the IDE, ensuring your software team's code is reasoned about, mathematically constrained, and compliant before it is committed.

![Aegion Banner](resources/banner.png)

## 🚀 Status: Phase 75 (Release Candidate)
The active codebase is **Production-Ready**, featuring robust E2E testing, Hypotheses fuzzing, and CNCF telemetry.

- **Governance**: Hierarchical Archon T0-T3 decision gates.
- **Cost Optimization**: FrugalGPT token mapping & multi-model fallback engines.
- **Intelligence**: Real-time git diff analysis natively tracked in PostgreSQL via pgvector.
- **Resilience**: Chaos-tested 502 routing & fallback execution tracking.

## ✨ Key Features

### 1. Zero-Drift Governance
Policy is code. Define rules (e.g., "No direct DB access in controllers"), and the Council enforces them on every save. Violations are formatted as real-time IDE diagnostics.

### 2. Thought-Commit Protocol
Every code change is linked to a "Thought" (Why) and "Evidence" (Proof). Aegion maintains a semantic knowledge graph in Postgres connecting business intent to git commits.

### 3. Frugal Multi-Agent Council
The Council orchestrates specialized AI agents (Architect, Security, QA) to review proposals instantly. Intelligent routing automatically delegates to cheaper LLMs (Anthropic, Gemini) for simpler queries to preserve token budgets.

### 4. Sandboxed Execution
Dangerous operations (file writes, shell commands) run in isolated, ephemeral Docker containers with strict resource limits and network policies.

## 🏁 Getting Started

### Prerequisites
*   **Docker** & Docker Compose (Required for Backend & Next.js UI)
*   **Python 3.12+**
*   **Node.js 18+** (for VS Code Extension & Next.js)

### Quickstart (Backend & Dashboard)
```bash
git clone https://github.com/aegion/aegion.git
cd aegion

# Start services (Backend, Next.js Dashboard, Postgres/Supabase, Redis)
docker-compose up -d

# Verify health
curl http://localhost:8080/api/v1/health/ready
```

### Quickstart (Extension)
1.  Open `aegion-vscode` in VS Code.
2.  Run `npm install`.
3.  Press `F5` to launch the extension in a debug window.
4.  Open Command Palette (`Cmd+Shift+P`) -> `Aegion: Start Session`.

## 📚 Documentation

### Guides
*   [**User Guide**](docs/04-User-Guide.md): specialized for Developers and Architects.
*   [**Developer Guide**](docs/05-Developer-Guide.md): Architecture and contribution.
*   [**Configuration**](docs/07-Configuration.md): Environment variables and settings.

### References
*   [**API Reference**](docs/06-API-Reference.md): Backend API endpoints.
*   [**Command Map**](docs/COMMAND_API_MAP.md): VS Code commands → API mapping.
*   [**Product Spec**](docs/PRODUCT_SPEC.md): Core vision and personas.

## 🧪 Testing

### Run Cutting-Edge Tests
```bash
cd aegion-backend
# Run Pytest (includes Hypothesis Property Fuzzing)
poetry run pytest

# Run Locust Chaos Tests
locust -f tests/load/locust_chaos.py --headless -u 100 -r 10 --run-time 60s
```

## 🏗️ Architecture
Aegion runs as a sidecar to your development flow:
*   **Dashboard (Next.js)**: Central observability and council metrics.
*   **Extension (Client)**: Captures intent, displays Council feedback.
*   **Core (Brain)**: FastAPI manages governance sessions and AI agents.
*   **Database (Memory)**: Supabase/PostgreSQL stores the lineage (pgvector) of every thought.

---
*Built with ❤️ by the Aegion Team.*
