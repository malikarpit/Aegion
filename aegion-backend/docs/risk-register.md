# Risk Register — Aegion

> Formal risk assessment: 12 identified threats with likelihood, impact, mitigation, and residual risk.

| ID | Threat | Likelihood | Impact | Mitigation | Owner | Residual |
|----|--------|-----------|--------|------------|-------|----------|
| R-001 | Sandbox escape | Low | Critical | Seccomp profile, cap-drop ALL, no-new-privileges, execution bridge | Platform | Very Low |
| R-002 | Privilege escalation | Low | Critical | AuthorityContext, T3 governance, guard_writable on all endpoints | Security | Low |
| R-003 | Cross-tenant data leak | Low | Critical | Workspace isolation, per-workspace encryption keys (HKDF) | Platform | Low |
| R-004 | Audit log tampering | Medium | High | Hash-chained audit store, HMAC-signed decisions, immutable append-only | Security | Low |
| R-005 | Token replay attack | Medium | High | Short-lived tokens, revocation list, session fingerprinting, token binding | Security | Low |
| R-006 | AI prompt injection | Medium | Medium | Injection detector (pattern + scoring), PII redaction, governance-aware classification | AI Safety | Medium |
| R-007 | Denial of service | Medium | Medium | Multi-layer rate limiting (WS/SSE/API/AI), circuit breakers, NGINX rate zones | Platform | Low |
| R-008 | Supply chain compromise | Low | High | Dependabot, SBOM (CycloneDX), cosign image signing, SLSA Level 2, pip-audit | DevOps | Low |
| R-009 | Split brain (multi-instance) | High* | Critical | Leader election (SET NX EX), single-writer constraint, heartbeat renewal | Platform | Medium |
| R-010 | Secrets exposure | Low | Critical | AES-256-GCM vault, per-workspace HKDF keys, access logging, tamper detection | Security | Very Low |
| R-011 | Signing key compromise | Low | Critical | Key rotation, revocation, batch re-signing, trust chain versioning, freeze escalation | Security | Low |
| R-012 | Training data leakage | Medium | High | Context window filtering, output checker, internal reference blocking | AI Safety | Medium |

*\*R-009: High likelihood only if deployed multi-instance without leader election enabled*

## Risk Review Cadence

| Activity | Frequency | Owner |
|----------|-----------|-------|
| Risk register review | Quarterly | Security Lead |
| Threat model update | Quarterly + trigger-based | Security Team |
| Penetration testing | Annually | External vendor |
| Tabletop exercise | Semi-annually | Incident Response Team |
