# SOC2 Control Mapping: Aegion

> Maps SOC2 Trust Services Criteria (CC1–CC9) to Aegion implementations.

| SOC2 Criteria | Control | Aegion Implementation | Evidence |
|---|---|---|---|
| **CC1** Control Environment | Organization structure, roles, oversight | `AuthorityContext` + `Role` enum (T0-T3), `guard_writable()` on all endpoints | `app/core/authority.py` |
| **CC2** Communication & Information | Internal/external communication controls | `SessionGuardMiddleware` (structured audit logging), correlation IDs, X-Correlation-ID propagation | `app/middleware/forensic_readiness.py` |
| **CC3** Risk Assessment | Identify, analyze, manage risks | STRIDE threat model, formal risk register (12 risks), quarterly review cadence | `docs/risk-register.md`, `docs/threat-model.md` |
| **CC4** Monitoring | Continuous monitoring activities | `observability.py` (Prometheus + OTel), alert thresholds (>5 violations/hr), metric cardinality controls | `app/middleware/observability.py` |
| **CC5** Control Activities | Policies and procedures | `state_machines.py` (6 lifecycles), Archon freeze guard, freeze escalation tiers | `app/services/archon/freeze_escalation.py` |
| **CC6** Access Control | Logical/physical access | Multi-provider auth, workspace isolation, session fingerprint, token binding, token revocation | `app/core/security.py` |
| **CC7** System Operations | Change detection, incident response | Hash-chained audit logs, `data_governance/` retention + GDPR erasure, backup/restore drills | `app/services/archon/audit_store.py` |
| **CC8** Change Management | Authorized changes only | Tiered governance (T0-T3), proposal flow, HMAC-signed decisions, admin gates | `app/services/archon/decision_integrity.py` |
| **CC9** Risk Mitigation | Address identified risks | AI safety pipeline, sandbox seccomp, rate limiting, secrets vault encryption | `app/services/ai_safety/`, `app/services/praxis/sandbox.py` |

## Audit Evidence Collection

| Evidence Type | Location | Retention |
|---|---|---|
| Decision audit trail | `audit_store` (hash-chained) | 7 years |
| Session logs | Structured JSON logs | 90 days |
| AI interaction logs | AI safety pipeline output | 30 days |
| Access logs | NGINX + application | 1 year |
| Security events | SIEM export (CEF/JSON) | 7 years |
