# Getting Started: Admin Guide

This guide is for Platform Engineers or Architects setting up Aegion for a team.

## 1. Concepts
- **Workspace**: A logical boundary for a team or project (e.g., "Payment Service").
- **Policy**: The set of rules the Council enforces (e.g., "No unpinned dependencies").
- **Tier**: The risk level of a change (T0=Routine, T3=Existential).

## 2. Deployment
Aegion is designed to run "On-Prem" (in your VPC) or locally.

### Production Deployment
Refrence `docker-compose.prod.yml` for a production-ready template.
Key differences from dev:
- **Database**: Use managed Neo4j Aura or Enterprise Standalone.
- **Events**: Use Google PubSub or Kafka instead of Redis.
- **Security**: Enable Firebase Auth middleware.

### Environment Variables
| Variable | Description |
| :--- | :--- |
| `ARCHON_MODE` | `strict` (blocks dangerous actions) or `audit` (logs only). |
| `NEO4J_URI` | Connection string for Graph DB. |
| `OPENAI_API_KEY` | Key for the LLM Brain (or Azure/Anthropic equivalent). |

## 3. Configuration
### Governance Policy (`policy.yaml`)
You can define custom invariants in `aegion-backend/config/policy.yaml`:

```yaml
invariants:
  - name: "No Direct SQL"
    severity: "critical"
    pattern: "execute_raw_sql"
    paths: ["controllers/*"]
    remediation: "Use the repository pattern."
```

## 4. Monitoring
Aegion exposes Prometheus metrics at `/metrics`.
Key indicators:
- `decision_latency_ms`: Time to classify/approve a proposal.
- `block_rate`: Percentage of actions blocked by Sentinel.
