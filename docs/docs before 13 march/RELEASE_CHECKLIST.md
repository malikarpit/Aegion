# Aegion Release Checklist

## Pre-Release (Automated Gates)
- [ ] **Governance Check**: `verify_governance_invariants.py` passed in CI.
    - No open "Critical" issues.
    - All PRs linked to Governance Proposals.
- [ ] **Security Scan**: `bandit` and `trivy` scans passed.
- [ ] **Contracts**: All API contract tests passed.
- [ ] **End-to-End**: Full interaction tests passed.

## Release Artifacts
- [ ] **Backend Container**: `aegion-backend:latest` built and pushed.
- [ ] **VS Code Extension**: `aegion-{version}.vsix` packaged.
- [ ] **Signatures**: `SHA256SUMS` generated for all artifacts.

## Deployment checks
- [ ] **Database Migration**: Schema migration completed (if applicable).
- [ ] **Smoke Test**: Key flows verified in staging.
- [ ] **Monitoring**: Dashboards show healthy state (Latency < 200ms, Errors < 1%).

## Post-Release
- [ ] **Tag**: Git tag `v{version}` created and pushed.
- [ ] **Changelog**: `CHANGELOG.md` updated.
- [ ] **Announcement**: Notify stakeholders via Council channel.
