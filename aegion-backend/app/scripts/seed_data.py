"""
Aegion Seed Data Generator — Big, Realistic, Production-Like.

Generates ~500+ rows across all tables mimicking 6 months of real usage
for a mature software team workspace.

Tables seeded:
  - workspaces (3 workspaces)
  - timeline_events (150+ events)
  - decisions (60+ decisions with verdicts, evidence, consensus)
  - risk_signals (40+ risks across severity levels)
  - adrs (15+ ADRs with status lifecycle)
  - rejection_log (25+ rejections with patterns)
  - cost_tracking (monthly cost records)
  - vault_secrets (8 secrets)
  - vault_audit_log (20+ audit entries)
  - custom_rubrics (3 workspace-specific rubrics)
  - workspace_model_settings (3 settings)
  - alerts (15+ historical alerts)

Run: python3 -m app.scripts.seed_data
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone

# Seed for reproducibility
random.seed(42)

# ══════════════════════════════════════════════
# Workspace definitions
# ══════════════════════════════════════════════

WORKSPACES = [
    {
        "id": "ws-aegion-core",
        "name": "aegion-core",
        "display_name": "Aegion Core Platform",
        "description": "Main Aegion governance platform — backend, frontend, VS Code extension",
        "owner_id": "user-arpit-001",
    },
    {
        "id": "ws-fintech-api",
        "name": "fintech-api",
        "display_name": "FinTech Payment Gateway",
        "description": "High-security payment processing API with PCI-DSS compliance",
        "owner_id": "user-arpit-001",
    },
    {
        "id": "ws-ml-pipeline",
        "name": "ml-pipeline",
        "display_name": "ML Inference Pipeline",
        "description": "Real-time ML model serving with A/B testing and feature stores",
        "owner_id": "user-arpit-001",
    },
]

# Time range: last 180 days
NOW = datetime.now(timezone.utc)
def random_time(days_ago_min: int, days_ago_max: int) -> str:
    delta = timedelta(
        days=random.randint(days_ago_min, days_ago_max),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return (NOW - delta).isoformat()


# ══════════════════════════════════════════════
# Timeline Events (~150)
# ══════════════════════════════════════════════

EVENT_TYPES = [
    "council_consulted", "decision_made", "proposal_created", "proposal_approved",
    "proposal_rejected", "risk_detected", "risk_resolved", "adr_created",
    "adr_accepted", "code_reviewed", "deployment_started", "deployment_completed",
    "security_scan", "cascade_escalated", "freeze_activated", "freeze_deactivated",
    "error", "config_changed", "model_switched", "budget_warning",
]

ENTITY_TYPES = [
    "proposal", "decision", "risk_signal", "adr", "deployment", "config",
    "code_change", "security_finding", "model_profile",
]

DESCRIPTIONS = {
    "council_consulted": [
        "Council consulted on database migration strategy from MongoDB to PostgreSQL",
        "PARENT council evaluated microservice decomposition proposal for auth service",
        "SENTINEL council security scan triggered for dependency update PR #347",
        "CHILD council quick review of API endpoint naming convention change",
        "Council consulted on implementing rate limiting with token bucket algorithm",
        "PARENT council evaluated GraphQL vs REST decision for public API",
        "Council consulted on Redis cluster vs single-node for session cache",
        "SENTINEL scan for new npm package trust-but-verify@2.1.0",
        "CHILD council reviewed error handling standardization proposal",
        "Council consulted on event sourcing vs traditional CRUD for audit trail",
    ],
    "decision_made": [
        "Approved: Migrate to PostgreSQL with pgvector extension for semantic search",
        "Approved: Implement circuit breaker pattern for external API calls",
        "Rejected: Replace FastAPI with Django — insufficient justification for migration cost",
        "Approved: Adopt conventional commits standard across all repositories",
        "Approved: Implement blue-green deployment strategy for zero-downtime releases",
        "Rejected: Add Redis as primary data store — contradicts ADR-007 (PostgreSQL first)",
        "Approved: Implement OAuth 2.0 PKCE flow for mobile client authentication",
        "Approved: Add OpenTelemetry tracing to all service boundaries",
    ],
    "risk_detected": [
        "Critical: Hardcoded AWS credentials found in config/legacy.py line 47",
        "High: SQL injection vulnerability in /api/v1/search endpoint — unparameterized query",
        "Medium: Dependency lodash@4.17.20 has known prototype pollution CVE-2021-23337",
        "High: CORS wildcard (*) configured in production API — data exfiltration risk",
        "Medium: No rate limiting on /api/v1/auth/login — brute force attack vector",
        "Critical: pickle.loads() used for deserialization of user-supplied data",
        "Low: Missing Content-Security-Policy header on frontend deployment",
    ],
    "deployment_completed": [
        "v2.14.0 deployed to production — 3 services, 0 rollbacks",
        "v2.13.2 hotfix deployed — fixed auth token expiry regression",
        "v2.15.0-rc1 deployed to staging — new council analytics module",
        "v2.12.0 deployed — GraphRAG memory engine live in production",
    ],
}

def generate_timeline_events():
    events = []
    for ws in WORKSPACES:
        ws_id = ws["id"]
        for i in range(50):  # 50 events per workspace = 150 total
            event_type = random.choice(EVENT_TYPES)
            descs = DESCRIPTIONS.get(event_type, [f"Event: {event_type} #{i}"])
            events.append({
                "id": str(uuid.uuid4()),
                "workspace_id": ws_id,
                "event_type": event_type,
                "entity_type": random.choice(ENTITY_TYPES),
                "entity_id": str(uuid.uuid4()),
                "payload": {
                    "description": random.choice(descs),
                    "actor": random.choice(["user-arpit-001", "council-engine", "sentinel-auto", "archon-governance"]),
                    "metadata": {"session_id": f"sess-{uuid.uuid4().hex[:8]}"},
                },
                "timestamp": random_time(1, 180),
            })
    return events


# ══════════════════════════════════════════════
# Decisions (~60)
# ══════════════════════════════════════════════

DECISION_TOPICS = [
    ("Database migration from MongoDB to PostgreSQL with pgvector", "approved", 0.87),
    ("Implement circuit breaker pattern for external payment API", "approved", 0.92),
    ("Replace FastAPI with Django REST Framework", "rejected", 0.34),
    ("Adopt Kubernetes for container orchestration", "approved", 0.78),
    ("Implement event sourcing for audit trail", "approved", 0.85),
    ("Add Redis cluster as primary session store", "rejected", 0.45),
    ("Migrate authentication from Firebase to Keycloak", "rejected", 0.38),
    ("Implement WebSocket-based real-time notifications", "approved", 0.91),
    ("Add GraphQL federation for microservice API gateway", "approved", 0.73),
    ("Implement blue-green deployment with Cloud Run revisions", "approved", 0.89),
    ("Replace REST endpoints with gRPC for internal services", "rejected", 0.52),
    ("Add OpenTelemetry distributed tracing", "approved", 0.94),
    ("Implement secrets rotation with 90-day policy", "approved", 0.88),
    ("Adopt trunk-based development replacing gitflow", "approved", 0.71),
    ("Add PII detection pipeline before data storage", "approved", 0.96),
    ("Migrate from Supabase to self-hosted PostgreSQL", "rejected", 0.29),
    ("Implement CQRS pattern for read-heavy analytics queries", "approved", 0.82),
    ("Add canary deployment strategy for ML model rollouts", "approved", 0.86),
    ("Replace pytest with unittest for test standardization", "rejected", 0.21),
    ("Implement rate limiting with sliding window algorithm", "approved", 0.93),
]

MODELS_USED = [
    ["gemini-2.5-pro", "claude-sonnet-4", "gpt-4o"],
    ["gemini-2.0-flash", "claude-haiku", "gpt-4o-mini"],
    ["gemini-2.5-pro", "gpt-4o"],
    ["gemini-2.5-flash", "claude-sonnet-4"],
    ["gemini-2.0-flash"],
]

def generate_decisions():
    decisions = []
    for ws in WORKSPACES:
        ws_id = ws["id"]
        for i, (topic, verdict, consensus) in enumerate(DECISION_TOPICS):
            # Add some variance per workspace
            adj_consensus = max(0.1, min(1.0, consensus + random.uniform(-0.1, 0.1)))
            decisions.append({
                "id": str(uuid.uuid4()),
                "workspace_id": ws_id,
                "title": topic,
                "verdict": verdict,
                "evidence": {
                    "consensus_score": round(adj_consensus, 3),
                    "rubric_score": round(random.uniform(0.55, 0.95), 3),
                    "models_used": random.choice(MODELS_USED),
                    "total_cost_usd": round(random.uniform(0.003, 0.15), 4),
                    "reasoning_depth": random.randint(3, 8),
                    "dissenting_views": random.randint(0, 3),
                    "quality": round(random.uniform(0.60, 0.95), 3),
                },
                "created_at": random_time(1, 180),
            })
    return decisions


# ══════════════════════════════════════════════
# Risk Signals (~40)
# ══════════════════════════════════════════════

RISK_SIGNALS_DATA = [
    ("security", "critical", "Hardcoded AWS access key in config/legacy.py", True),
    ("security", "critical", "pickle.loads() used for user-supplied data deserialization", True),
    ("security", "high", "SQL injection in /api/v1/search — unparameterized query", True),
    ("security", "high", "CORS wildcard (*) in production API configuration", False),
    ("security", "medium", "Missing CSRF protection on state-changing POST endpoints", False),
    ("security", "high", "JWT secret stored as plaintext environment variable", True),
    ("security", "critical", "eval() called on user-provided webhook template", False),
    ("dependency", "high", "lodash@4.17.20 — CVE-2021-23337 prototype pollution", True),
    ("dependency", "medium", "axios@0.21.0 — CVE-2021-3749 server-side request forgery", True),
    ("dependency", "low", "moment.js deprecated — migrate to dayjs or date-fns", False),
    ("dependency", "medium", "jsonwebtoken@8.5.1 — attacker-controlled algorithm bypass", True),
    ("breaking_change", "high", "API v1 /users endpoint removed without deprecation notice", False),
    ("breaking_change", "medium", "Database migration drops column user.legacy_id without backfill", False),
    ("data_schema", "high", "ALTER TABLE users DROP COLUMN without migration rollback plan", True),
    ("data_schema", "medium", "New NOT NULL constraint on payments.currency without default", False),
    ("performance", "medium", "N+1 query pattern in /api/v1/proposals — 47 queries per request load", False),
    ("performance", "high", "Full table scan on 2.3M row analytics_events table — missing index", True),
    ("performance", "low", "Synchronous file I/O in async request handler", False),
    ("code_quality", "low", "Function decision_pipeline.execute() is 347 lines — extract methods", False),
    ("code_quality", "medium", "No error handling in external payment webhook processor", False),
    ("secrets_exposure", "critical", "API key for Stripe in committed .env file", True),
    ("secrets_exposure", "high", "Database connection string with password in docker-compose.yml", True),
    ("configuration", "medium", "DEBUG=True in production configuration", False),
    ("configuration", "low", "Logging level set to DEBUG in production — performance impact", False),
]

def generate_risk_signals():
    signals = []
    for ws in WORKSPACES[:2]:  # Risks for first 2 workspaces
        ws_id = ws["id"]
        for signal_type, severity, description, resolved in RISK_SIGNALS_DATA:
            signals.append({
                "id": str(uuid.uuid4()),
                "workspace_id": ws_id,
                "signal_type": signal_type,
                "severity": severity,
                "source": random.choice(["sentinel_auto", "manual_review", "ci_pipeline", "dependency_scan"]),
                "description": description,
                "resolved": resolved if random.random() > 0.3 else not resolved,  # Some variance
                "created_at": random_time(1, 120),
            })
    return signals


# ══════════════════════════════════════════════
# ADRs (~15)
# ══════════════════════════════════════════════

ADRS = [
    ("ADR-001: Use PostgreSQL as Primary Database", "accepted",
     "All persistent data must use PostgreSQL via Supabase. No additional database technologies without T2+ approval.",
     ["No MongoDB, Redis as primary store, or DynamoDB", "All queries must use parameterized statements", "pgvector for semantic search"]),
    ("ADR-002: FastAPI for Backend Services", "accepted",
     "All backend services use FastAPI with async handlers. No synchronous frameworks.",
     ["No Django, Flask, or Express.js for backend", "All endpoints must be async", "Pydantic models for request/response validation"]),
    ("ADR-003: Firebase Authentication", "accepted",
     "Firebase Auth handles all user authentication. Backend validates Firebase tokens.",
     ["No custom auth implementation", "JWT verification on every protected endpoint", "Token refresh handled client-side"]),
    ("ADR-004: Conventional Commits", "accepted",
     "All commits follow Conventional Commits specification (feat:, fix:, chore:, etc.)",
     ["No freeform commit messages", "Breaking changes must use BREAKING CHANGE footer"]),
    ("ADR-005: Cloud Run for Deployments", "accepted",
     "All backend services deploy to GCP Cloud Run. No VMs or Kubernetes.",
     ["Container-based deployments only", "Auto-scaling 0-10 instances", "Max 512MB memory per instance"]),
    ("ADR-006: Next.js for Frontend", "accepted",
     "Frontend uses Next.js with App Router. Server-side rendering where beneficial.",
     ["No Create React App or Vite", "TailwindCSS for styling", "Firebase Hosting for deployment"]),
    ("ADR-007: No Redis as Primary Store", "accepted",
     "Redis may be used as a cache layer only, never as a primary data store.",
     ["Cache TTL must be set on all Redis keys", "Application must function without Redis (graceful degradation)"]),
    ("ADR-008: Event Sourcing for Audit Trail", "accepted",
     "All governance decisions are event-sourced via Chronos. Events are immutable.",
     ["No UPDATE/DELETE on timeline_events", "SHA256 chain hashing for tamper detection"]),
    ("ADR-009: Semantic Versioning", "accepted",
     "All releases follow SemVer. MAJOR.MINOR.PATCH with pre-release identifiers.",
     ["Breaking API changes require MAJOR bump", "New features are MINOR", "Bug fixes are PATCH"]),
    ("ADR-010: LLM Cost Budget", "accepted",
     "Monthly LLM spend must not exceed $50/workspace. FrugalGPT cascade is mandatory.",
     ["Cheapest capable model first", "Semantic cache required", "Budget alerts at 80% threshold"]),
    ("ADR-011: Replace MongoDB with pgvector", "superseded",
     "Original: Use MongoDB for document storage. Superseded by ADR-001.",
     ["MongoDB was the original choice", "Migrated to PostgreSQL+pgvector for unified stack"]),
    ("ADR-012: Zero Trust Agent Identity", "accepted",
     "All inter-service calls require agent identity tokens. No implicit trust.",
     ["mTLS between services", "Agent identity verified on every request", "No shared service accounts"]),
    ("ADR-013: GraphRAG for Knowledge Retrieval", "accepted",
     "Knowledge retrieval uses entity-centric GraphRAG (not flat vector similarity).",
     ["Entity extraction from all stored memories", "Multi-hop graph traversal for context", "Community detection for summarization"]),
    ("ADR-014: Self-Optimizing Prompts", "accepted",
     "All council prompts are managed by the PromptRegistry with auto-mutation.",
     ["No hardcoded prompt strings in business logic", "Prompt versions tracked", "Automatic mutation when rubric scores drop below 0.55"]),
    ("ADR-015: MCTS for Complex Reasoning", "proposed",
     "Complex architectural decisions use Monte Carlo Tree Search for reasoning.",
     ["MCTS for T2+ governance decisions", "Linear chain-of-thought for T0-T1", "Critic model required for Q-value scoring"]),
]

def generate_adrs():
    adr_records = []
    for ws in WORKSPACES[:2]:
        ws_id = ws["id"]
        for title, status, description, constraints in ADRS:
            adr_records.append({
                "id": str(uuid.uuid4()),
                "workspace_id": ws_id,
                "title": title,
                "description": description,
                "status": status,
                "constraints": constraints,
                "created_at": random_time(30, 180),
            })
    return adr_records


# ══════════════════════════════════════════════
# Rejection Log (~25)
# ══════════════════════════════════════════════

REJECTIONS = [
    ("Proposal contradicts ADR-007 — uses Redis as primary store",
     {"title": "Implement Redis as main session database", "description": "Replace PostgreSQL sessions with Redis for speed"}),
    ("Security risk — proposal introduces eval() for user templates",
     {"title": "Dynamic webhook template engine", "description": "Allow users to write custom webhook templates with eval"}),
    ("Cost exceeds budget — proposal requires GPT-4 for every request",
     {"title": "Use GPT-4 as sole model for all queries", "description": "Replace cascade with single GPT-4 model"}),
    ("Breaking change without migration path",
     {"title": "Remove legacy API v1 endpoints", "description": "Drop all /api/v1/ endpoints, force migration to v2"}),
    ("Insufficient evidence — no benchmark data provided",
     {"title": "Migrate from PostgreSQL to ScyllaDB", "description": "ScyllaDB would be faster for our workload"}),
    ("Governance violation — T3 decision attempted without Archon approval",
     {"title": "Replace entire auth system with custom JWT", "description": "Build custom auth from scratch"}),
    ("Over-engineered — YAGNI principle violated",
     {"title": "Implement saga orchestrator for 2-step checkout", "description": "Full saga pattern for a simple checkout flow"}),
    ("Conflicts with ADR-002 — proposes Django migration",
     {"title": "Migrate backend to Django REST Framework", "description": "Django has better ORM and admin panel"}),
    ("No rollback plan for database schema change",
     {"title": "Drop legacy columns from users table", "description": "Remove 5 unused columns to clean up schema"}),
    ("Dependency has known CVE — cannot approve until patched",
     {"title": "Add node-fetch@2.6.0 for HTTP client", "description": "Use node-fetch instead of axios"}),
    ("Performance regression — proposal adds N+1 query pattern",
     {"title": "Eager load all relationships in list endpoints", "description": "Load all related data in every list query"}),
    ("Violates zero-trust principle — shared service account",
     {"title": "Use shared API key for inter-service calls", "description": "Single API key for all microservices"}),
]

def generate_rejections():
    rejections = []
    for ws in WORKSPACES:
        ws_id = ws["id"]
        for reason, context in random.sample(REJECTIONS, min(8, len(REJECTIONS))):
            rejections.append({
                "id": str(uuid.uuid4()),
                "workspace_id": ws_id,
                "proposal_id": str(uuid.uuid4()),
                "rejection_reason": reason,
                "proposal_context": context,
                "council_output": {
                    "synthesis": f"Council recommended approval but user rejected: {reason}",
                    "consensus_score": round(random.uniform(0.3, 0.7), 3),
                    "models_used": random.choice(MODELS_USED),
                },
                "created_at": random_time(1, 120),
            })
    return rejections


# ══════════════════════════════════════════════
# Cost Tracking
# ══════════════════════════════════════════════

def generate_cost_tracking():
    records = []
    for ws in WORKSPACES:
        ws_id = ws["id"]
        for month_offset in range(6):
            month_date = NOW - timedelta(days=month_offset * 30)
            records.append({
                "id": str(uuid.uuid4()),
                "workspace_id": ws_id,
                "month": month_date.strftime("%Y-%m"),
                "total_cost_usd": round(random.uniform(8.0, 45.0), 2),
                "monthly_budget_usd": 50.00,
                "model_breakdown": {
                    "gemini-2.0-flash": round(random.uniform(1.0, 5.0), 2),
                    "gemini-2.5-pro": round(random.uniform(5.0, 20.0), 2),
                    "claude-sonnet-4": round(random.uniform(2.0, 10.0), 2),
                    "gpt-4o-mini": round(random.uniform(0.5, 3.0), 2),
                    "gpt-4o": round(random.uniform(3.0, 12.0), 2),
                },
                "cache_savings_usd": round(random.uniform(5.0, 25.0), 2),
                "cascade_savings_usd": round(random.uniform(3.0, 15.0), 2),
                "total_requests": random.randint(200, 2000),
                "cache_hit_rate": round(random.uniform(0.15, 0.45), 3),
                "created_at": month_date.isoformat(),
            })
    return records


# ══════════════════════════════════════════════
# Alerts
# ══════════════════════════════════════════════

def generate_alerts():
    alerts = []
    alert_templates = [
        ("high_error_rate", "High API Error Rate", "warning",
         "API error rate exceeded 10% in the last 5 minutes",
         {"error_rate": 0.14, "errors": 23, "total": 164}),
        ("cascade_exhaustion", "Council Cascade Exhausted", "critical",
         "All LLM cascade tiers failed — no model could serve the request",
         {"exhaustion_count": 3}),
        ("budget_exceeded", "Budget Threshold Exceeded", "warning",
         "Workspace has used >80% of its monthly LLM budget",
         {"spent_usd": 42.50, "budget_usd": 50.00, "usage_pct": 0.85}),
        ("sentinel_critical", "Sentinel Critical Risk", "critical",
         "Risk score >= 0.9 detected by Sentinel",
         {"critical_risks": 2, "descriptions": ["Hardcoded AWS credentials", "eval() on user input"]}),
        ("governance_degraded", "Governance Health Degraded", "warning",
         "Governance health score dropped to D grade",
         {"grade": "D", "score": 0.38}),
        ("cognitive_drift", "Cognitive Drift Detected", "info",
         "Council reasoning patterns have shifted significantly",
         {"alerts": ["Approval rate increased significantly — possible rubber-stamping"], "approval_delta": 0.22}),
    ]

    for ws in WORKSPACES[:2]:
        ws_id = ws["id"]
        for rule_id, name, severity, description, details in alert_templates:
            for j in range(random.randint(1, 3)):
                alerts.append({
                    "id": str(uuid.uuid4()),
                    "rule_id": rule_id,
                    "name": name,
                    "severity": severity,
                    "description": description,
                    "details": details,
                    "workspace_id": ws_id,
                    "fired_at": random_time(1, 60),
                    "acknowledged": random.choice([True, False]),
                    "acknowledged_by": "user-arpit-001" if random.random() > 0.5 else None,
                })
    return alerts


# ══════════════════════════════════════════════
# Vault Secrets & Audit
# ══════════════════════════════════════════════

def generate_vault_data():
    secrets = [
        ("stripe_api_key", "ws-fintech-api", 3),
        ("openai_api_key", "ws-aegion-core", 2),
        ("anthropic_api_key", "ws-aegion-core", 1),
        ("google_ai_key", "ws-aegion-core", 1),
        ("database_password", "ws-aegion-core", 5),
        ("jwt_signing_secret", "ws-aegion-core", 2),
        ("webhook_secret", "ws-fintech-api", 1),
        ("ml_model_api_key", "ws-ml-pipeline", 1),
    ]

    vault_secrets = []
    audit_entries = []

    for key, ws_id, version in secrets:
        vault_secrets.append({
            "id": str(uuid.uuid4()),
            "key": key,
            "encrypted_value": f"gAAAAAB_encrypted_{key}_{uuid.uuid4().hex[:16]}",
            "version": version,
            "workspace_id": ws_id,
            "max_age_hours": random.choice([None, 720, 2160, 8760]),
            "is_active": True,
            "created_at": random_time(1, 90),
        })

        # Audit entries for each secret
        for action in ["store"] + (["access"] * random.randint(1, 5)) + (["rotate"] * (version - 1)):
            audit_entries.append({
                "id": str(uuid.uuid4()),
                "key": key,
                "action": action,
                "actor_id": random.choice(["user-arpit-001", "model_registry", "system", "council-engine"]),
                "workspace_id": ws_id,
                "details": {},
                "timestamp": random_time(1, 90),
            })

    return vault_secrets, audit_entries


# ══════════════════════════════════════════════
# Custom Rubrics
# ══════════════════════════════════════════════

CUSTOM_RUBRICS = [
    {
        "name": "fintech_compliance",
        "workspace_id": "ws-fintech-api",
        "criteria": {
            "pci_compliance": {"weight": 0.30, "description": "Adheres to PCI-DSS requirements"},
            "data_encryption": {"weight": 0.25, "description": "All PII encrypted at rest and in transit"},
            "audit_trail": {"weight": 0.20, "description": "Complete audit trail for financial transactions"},
            "access_control": {"weight": 0.15, "description": "Role-based access with least-privilege"},
            "incident_response": {"weight": 0.10, "description": "Incident response plan exists and is tested"},
        },
    },
    {
        "name": "ml_model_quality",
        "workspace_id": "ws-ml-pipeline",
        "criteria": {
            "accuracy": {"weight": 0.25, "description": "Model accuracy meets production threshold (>95%)"},
            "fairness": {"weight": 0.20, "description": "No demographic bias in predictions"},
            "latency": {"weight": 0.20, "description": "P99 inference latency under 100ms"},
            "explainability": {"weight": 0.20, "description": "Model decisions are explainable to end users"},
            "data_quality": {"weight": 0.15, "description": "Training data is clean, representative, and fresh"},
        },
    },
    {
        "name": "api_design",
        "workspace_id": "ws-aegion-core",
        "criteria": {
            "restful_conventions": {"weight": 0.25, "description": "Follows REST conventions (proper verbs, status codes)"},
            "backward_compatibility": {"weight": 0.25, "description": "No breaking changes to existing clients"},
            "documentation": {"weight": 0.20, "description": "OpenAPI spec is complete and accurate"},
            "error_handling": {"weight": 0.15, "description": "Consistent error format with actionable messages"},
            "pagination": {"weight": 0.15, "description": "Large collections are paginated with cursor support"},
        },
    },
]


# ══════════════════════════════════════════════
# Workspace Model Settings
# ══════════════════════════════════════════════

MODEL_SETTINGS = [
    {"workspace_id": "ws-aegion-core", "active_profile": "quality"},
    {"workspace_id": "ws-fintech-api", "active_profile": "anthropic"},
    {"workspace_id": "ws-ml-pipeline", "active_profile": "fast"},
]


# ══════════════════════════════════════════════
# Main generator
# ══════════════════════════════════════════════

def generate_all():
    """Generate all seed data and return as dict of table → rows."""
    vault_secrets, vault_audit = generate_vault_data()

    data = {
        "workspaces": WORKSPACES,
        "timeline_events": generate_timeline_events(),
        "decisions": generate_decisions(),
        "risk_signals": generate_risk_signals(),
        "adrs": generate_adrs(),
        "rejection_log": generate_rejections(),
        "cost_tracking": generate_cost_tracking(),
        "vault_secrets": vault_secrets,
        "vault_audit_log": vault_audit,
        "custom_rubrics": CUSTOM_RUBRICS,
        "workspace_model_settings": MODEL_SETTINGS,
        "alerts": generate_alerts(),
    }

    total_rows = sum(len(v) for v in data.values())
    print(f"\n{'='*60}")
    print(f"  AEGION SEED DATA GENERATED")
    print(f"{'='*60}")
    for table, rows in data.items():
        print(f"  {table:.<40} {len(rows):>4} rows")
    print(f"{'='*60}")
    print(f"  TOTAL: {total_rows} rows across {len(data)} tables")
    print(f"{'='*60}\n")

    return data


def insert_to_supabase(data: dict):
    """Insert all seed data into Supabase."""
    from app.db.supabase_client import get_supabase_client
    client = get_supabase_client()

    for table, rows in data.items():
        if not rows:
            continue
        try:
            # Batch insert in chunks of 50
            for i in range(0, len(rows), 50):
                chunk = rows[i:i+50]
                client.table(table).upsert(chunk).execute()
            print(f"  ✅ {table}: {len(rows)} rows inserted")
        except Exception as exc:
            print(f"  ❌ {table}: {exc}")


if __name__ == "__main__":
    import sys
    data = generate_all()

    if "--dry-run" not in sys.argv:
        print("Inserting into Supabase...")
        try:
            insert_to_supabase(data)
            print("\n✅ Seed data insertion complete!")
        except Exception as e:
            print(f"\n❌ Supabase insertion failed: {e}")
            print("Run with --dry-run to see generated data without insertion.")
    else:
        print("Dry run — data generated but not inserted.")
        # Write to JSON for inspection
        output_path = "seed_data_output.json"
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Data written to {output_path}")
