.PHONY: bootstrap test smoke dev lint clean help

# ─── Phase 91: One-Command Local Bootstrap ───

help: ## Show available targets
	@echo "Aegion Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

bootstrap: ## Full setup: venv, deps, Supabase, migrations, smoke
	@./scripts/bootstrap.sh

test: ## Run full backend test suite
	cd aegion-backend && python -m pytest tests/ -x -q --tb=short

smoke: ## Quick config + import validation (<10s)
	@echo "→ Smoke testing backend config..."
	cd aegion-backend && python -c \
		"from app.core.config import settings; print('✅ Config loaded:', settings.APP_NAME)"
	@echo "→ Smoke testing core imports..."
	cd aegion-backend && python -c \
		"from app.services.graph_provider import get_shared_graph; print('✅ Graph provider OK')"
	cd aegion-backend && python -c \
		"from app.services.session_manager import get_session_manager; print('✅ Session manager OK')"
	cd aegion-backend && python -c \
		"from app.adapters.postgres.council_store import PostgresCouncilStore; print('✅ Council store OK')"
	@echo "✅ All smoke tests passed"

dev: ## Start Supabase + backend dev server
	@echo "→ Starting Supabase..."
	supabase start || true
	@echo "→ Starting backend..."
	cd aegion-backend && uvicorn app.main:app --reload --port 8000

dev-frontend: ## Start Next.js frontend dev server
	cd aegion-frontend && npm run dev

dev-all: ## Start all services (backend + frontend)
	@$(MAKE) dev &
	@sleep 3
	@$(MAKE) dev-frontend

lint: ## Lint backend + frontend + extension
	cd aegion-backend && python -m ruff check . || true
	cd aegion-frontend && npm run lint || true
	cd aegion-vscode && npm run compile || true

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .next -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -not -path "./.venv/*" -exec echo "Skipping {}" \; 2>/dev/null || true
	@echo "✅ Cleaned caches"

benchmark: ## Run SWE-bench Lite subset (Phase 110)
	cd aegion-backend && python scripts/swe_bench_runner.py --subset 30
