# Key Compromise Recovery Plan

> Aegion Enterprise Hardening — Phase 2.5

## 1. Key Revocation Process

When a signing key is suspected or confirmed compromised:

1. **Immediate revocation**: Mark the compromised `key_id` as revoked in `KeyRotationManager`
2. **Refuse verification**: All signature verification against the revoked `key_id` must return `INVALID`
3. **Force rotation**: Trigger immediate key rotation via `KeyRotationManager.rotate()`
4. **Freeze affected workspaces**: Escalate to `FULL` freeze via `FreezeEscalationManager`
5. **Notify operators**: Emit `KEY_COMPROMISE_DETECTED` audit event

```python
# Example revocation flow
key_manager.rotate()  # Promote current → previous, generate new
freeze_manager.escalate(workspace_id, FreezeTier.FULL, "system", "key_compromise")
```

## 2. Re-signing Historical Decisions

After key rotation, all decisions signed with the compromised key must be re-signed:

1. Query all DECISION nodes with `.key_id == compromised_key_id`
2. Use `DecisionResigner.re_sign_decision()` for each
3. Each re-signed decision gets:
   - New `signature` from current key
   - `re_signed_at` timestamp
   - `trust_chain_version` incremented

```python
resigner = DecisionResigner(signer)
for decision in affected_decisions:
    resigner.re_sign_decision(
        decision_id=decision.id,
        proposal_id=decision.proposal_id,
        decided_at=decision.decided_at,
        approver_id=decision.approver_id,
        current_trust_version=decision.trust_chain_version,
    )
```

## 3. Decision Trust Chain Versioning

Each decision node maintains a `trust_chain_version` field:

| Version | Meaning |
|---------|---------|
| 1 | Original signature |
| 2+ | Re-signed after key rotation/compromise |

Auditors can distinguish original signatures from re-signed ones by comparing versions.

## 4. Key Rotation Audit Proof

Every rotation is logged with:

| Field | Description |
|-------|-------------|
| `old_key_id` | ID of the outgoing key |
| `new_key_id` | ID of the incoming key |
| `reason` | "scheduled" / "compromise" / "manual" |
| `operator` | Actor who triggered rotation |
| `timestamp` | UTC ISO 8601 |

These records are immutable and stored in the audit log.

## 5. Recovery Timeline

| Step | SLA | Owner |
|------|-----|-------|
| Detect compromise | Immediate | Monitoring |
| Revoke key + freeze | < 5 min | System |
| Rotate to new key | < 5 min | System |
| Re-sign decisions | < 1 hour | Batch job |
| Verify re-signing | < 1 hour | Audit |
| Unfreeze (multi-party) | < 4 hours | Admin + Architect |
