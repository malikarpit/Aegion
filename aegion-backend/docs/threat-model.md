# Aegion Threat Model

## 1. System Overview

Aegion is a governance-first AI coding assistant. This threat model documents trust boundaries, threat actors, attack vectors, and mitigations.

## 2. Trust Boundaries

```
┌──────────────────────────────────────────────────────────────────┐
│  CLIENT ZONE (Untrusted)                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐        │
│  │  VS Code     │  │  Browser    │  │  CLI / API       │        │
│  │  Extension   │  │  Dashboard  │  │  Consumers       │        │
│  └──────┬───────┘  └──────┬──────┘  └────────┬─────────┘        │
│         │                  │                   │                  │
├─────────┼──────────────────┼───────────────────┼──────────────────┤
│  DMZ / BOUNDARY                                                  │
│  ┌──────┴──────────────────┴───────────────────┴─────────────┐   │
│  │  SessionGuard Middleware                                    │  │
│  │  • Session ID enforcement                                  │  │
│  │  • Intent declaration (provenance)                         │  │
│  │  • Fingerprint verification                                │  │
│  │  • Rate limiting (60-120 req/min per category)             │  │
│  │  • Token binding                                           │  │
│  └───────────────────────────────────────────────────────────┘   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  Firebase/JWT Auth (get_current_user)                      │  │
│  │  • Token verification (Firebase ID tokens / JWKS)          │  │
│  │  • Workspace role resolution                               │  │
│  │  • AuthorityContext construction (RBAC)                     │  │
│  └───────────────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────────────┤
│  APPLICATION ZONE (Trusted)                                      │
│  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  Archon    │  │  Noesis  │  │  Praxis  │  │  Chronos     │   │
│  │  Govern.   │  │  AI/Graph│  │  Exec.   │  │  Time/Audit  │   │
│  └───────────┘  └──────────┘  └──────────┘  └──────────────┘   │
├──────────────────────────────────────────────────────────────────┤
│  DATA ZONE (Protected)                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ Firestore │  │  Neo4j   │  │  GCS Bucket  │  │  Audit Log │  │
│  │  (Users)  │  │  (Graph) │  │  (Artifacts) │  │  (Chain)   │  │
│  └──────────┘  └──────────┘  └──────────────┘  └────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## 3. Threat Actors

| Actor | Capability | Motivation |
|---|---|---|
| **External Attacker** | Network access, credential theft | Data exfiltration, system disruption |
| **Malicious User** | Valid credentials, workspace access | Governance bypass, unauthorized changes |
| **Compromised AI Agent** | API access via tool server | Arbitrary code execution, data tampering |
| **Insider Threat** | Admin credentials, code access | Policy override, audit trail manipulation |
| **Supply Chain** | Dependency poisoning | Backdoor installation |

## 4. Attack Vectors & Mitigations

### 4.1 Authentication Bypass
| Vector | Risk | Mitigation | Status |
|---|---|---|---|
| Stolen Firebase token | HIGH | Token expiry (1hr), token binding to session | ✅ Implemented |
| JWT replay | HIGH | JTI tracking, session fingerprint check | ✅ Implemented |
| Mock token in production | CRITICAL | `AEGION_DEBUG` must be `false` in prod | ✅ Guarded |

### 4.2 Authorization Escalation
| Vector | Risk | Mitigation | Status |
|---|---|---|---|
| Role manipulation | HIGH | Role resolved server-side from workspace membership | ✅ Implemented |
| T2+ approval without authority | CRITICAL | `can_approve_t2` only for ADMIN role | ✅ Enforced |
| Cross-workspace data access | MEDIUM | Workspace isolation middleware | ✅ Implemented |

### 4.3 Governance Bypass
| Vector | Risk | Mitigation | Status |
|---|---|---|---|
| Direct graph mutation | HIGH | `guard_writable()` on all mutating endpoints | ✅ Enforced |
| Freeze bypass | CRITICAL | Only `/unfreeze` with ADMIN role exempt | ✅ Designed |
| Re-approval attack | MEDIUM | Decision deduplication (409 on duplicate) | ✅ Implemented |
| Evidence tampering | CRITICAL | Immutable nodes (update/delete blocked) | ✅ Enforced |

### 4.4 AI Jailbreak
| Vector | Risk | Mitigation | Status |
|---|---|---|---|
| Prompt injection | HIGH | AI output safety classifier | ✅ Implemented |
| Hallucinated evidence | MEDIUM | Hallucination guard (cross-ref graph) | ✅ Implemented |
| AI-generated governance bypass | HIGH | All AI actions require governance proposal | ✅ Enforced |
| Cost explosion | MEDIUM | Per-workspace daily budget enforcement | ✅ Implemented |

### 4.5 Execution Plane
| Vector | Risk | Mitigation | Status |
|---|---|---|---|
| Container escape | CRITICAL | seccomp profile, cap-drop=ALL, no-new-privileges | ✅ Hardened |
| Resource exhaustion | HIGH | Memory limit (256MB), CPU limit (1.0), timeout | ✅ Enforced |
| Network exfiltration | HIGH | `--network=none` by default | ✅ Default |
| Filesystem write | MEDIUM | `--read-only` + tmpfs for /tmp only | ✅ Hardened |

### 4.6 Audit Integrity
| Vector | Risk | Mitigation | Status |
|---|---|---|---|
| Log tampering | CRITICAL | SHA-256 hash chain + HMAC-SHA256 signing | ✅ Implemented |
| Chain gap injection | HIGH | Chain verification (verify_chain) | ✅ Implemented |
| Signing key compromise | HIGH | Key rotation with overlap window | ✅ Implemented |

## 5. Data Classification

| Data Type | Sensitivity | Encryption | Retention |
|---|---|---|---|
| User credentials | CRITICAL | Firebase-managed (never stored locally) | N/A |
| Session transcripts | HIGH | At-rest (GCS server-side) | 1 year |
| Decision records | HIGH | Signed (HMAC chain) | Indefinite |
| Evidence nodes | MEDIUM | Integrity-protected (immutable) | Indefinite |
| AI outputs | MEDIUM | In transit (TLS) | 180 days |
| Audit logs | HIGH | Hash-chained + signed | Indefinite |

## 6. Residual Risks

1. **Firebase dependency** — Single auth provider. Mitigated by multi-provider auth config.
2. **In-memory graph volatility** — Dev mode uses InMemoryKnowledgeGraph. Production uses Neo4j.
3. **AI model trust** — AI outputs are advisory, never directly authoritative. All actions require governance.
