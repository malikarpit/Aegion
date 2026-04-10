# Secure SDLC & Incident Response — Aegion

## 1. Code Review Policy

| Change Type | Required Reviewers | Auto-merge |
|---|---|---|
| Non-security code | 1 reviewer | After CI pass |
| Security-sensitive (auth, crypto, sandbox) | Security team member | Never |
| Governance logic (proposals, decisions) | 2 reviewers (1 security) | Never |
| Infrastructure (Dockerfile, deploy/) | Platform team member | Never |

## 2. Security Checklist (PR Template)

- [ ] Input validation on all user-facing endpoints
- [ ] `guard_writable()` called for mutation endpoints
- [ ] Workspace isolation verified (no cross-tenant access)
- [ ] Rate limiting applied to new endpoints
- [ ] Audit logging for security-relevant operations
- [ ] No secrets hardcoded in source code
- [ ] Error messages don't leak internal state
- [ ] PII redaction applied to log output

## 3. Security Event Classification Matrix

| Event | Severity | Response SLA | Auto-action |
|---|---|---|---|
| Sandbox escape / violation | P0 | Immediate | EMERGENCY freeze |
| Governance bypass attempt | P0 | Immediate | FULL freeze |
| Audit chain integrity failure | P0 | Immediate | FULL freeze + alert |
| Token replay / binding mismatch | P1 | 4 hours | Revoke token |
| Cross-workspace access attempt | P1 | 4 hours | Log + alert |
| Rate limit sustained abuse | P2 | 24 hours | Auto-block IP |
| Unusual AI cost spike | P2 | 24 hours | Circuit breaker |
| Fingerprint drift (non-strict) | P3 | Next business day | Log only |

## 4. Incident Response Workflow

```
Detect → Triage → Contain → Eradicate → Recover → Post-mortem
```

| Phase | Actions | Owner |
|---|---|---|
| **Detect** | Monitoring alerts, audit chain verification, user reports | On-call |
| **Triage** | Classify severity (P0-P3), assign incident commander | Security Lead |
| **Contain** | Freeze affected workspaces, revoke tokens, isolate services | Incident Commander |
| **Eradicate** | Patch vulnerability, rotate keys, update policies | Engineering |
| **Recover** | Unfreeze (multi-party for EMERGENCY), restore from backup, verify integrity | Platform + Security |
| **Post-mortem** | Root cause analysis, timeline, lessons learned, update risk register | All |

## 5. Threat Model Review Triggers

Review the threat model when any of these occur:
- New external integration added
- Authentication flow modified
- New data store introduced
- Sandbox execution model changed
- New AI model provider added
