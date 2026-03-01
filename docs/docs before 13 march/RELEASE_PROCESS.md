# Aegion Release Process

## Release Channels

### 1. Insiders (Nightly)
- **Frequency**: Daily (Automated via CI).
- **Tag**: `v0.x.y-insiders`.
- **Audience**: Internal team, early adopters.
- **Stability**: Bleeding edge, may have bugs.
- **Governance**: T1 (Standard) approval required for features.

### 2. Stable (Production)
- **Frequency**: Bi-weekly or Monthly.
- **Tag**: `v0.x.y`.
- **Audience**: General public, enterprise customers.
- **Stability**: Production-grade, verified by QA.
- **Governance**: T3 (Existential) approval required for release manifest.

## Release Workflow

### Step 1: Governance Check
Run the governance gate to ensure all invariants are met.
```bash
./scripts/verify_governance_invariants.py
```

### Step 2: Artifact Signing
Generate SHA256 checksums for all build artifacts (Backend Docker image, VS Code VSIX).
```bash
./scripts/sign_artifacts.sh
```

### Step 3: Tag and Push
```bash
git tag -a v0.2.0 -m "Release v0.2.0: Feature Flags & Invariant Packs"
git push origin v0.2.0
```

### Step 4: GitHub Release
The `release-gate.yml` workflow will automatically:
1.  Build the Docker image.
2.  Package the VS Code extension.
3.  Upload artifacts to the GitHub Release.
4.  Publish the VSIX to the Marketplace (if secrets configured).

## Hotfix Process
For critical bugs in Stable:
1.  Create `hotfix/v0.x.z` branch from `main`.
2.  Cherry-pick the fix.
3.  Run `verify_governance_invariants.py`.
4.  Tag and release.
