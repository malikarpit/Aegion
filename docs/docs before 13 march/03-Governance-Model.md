# Aegion Governance Model

## Overview

The governance model is the core of Aegion. It defines *who* can do *what*, and *how* decisions are made. It replaces ad-hoc verbal agreements with codified, enforceable rules.

## Users & Roles

Aegion uses a role-based access control (RBAC) system to determine permissions.

### 1. Developer
*   **Context**: Individual contributors working on tasks.
*   **Capabilities**:
    *   Start sessions.
    *   Propose T0 and T1 changes.
    *   Execute approved changes.
    *   Participate in peer reviews.

### 2. Team Lead / Architect
*   **Context**: Senior engineers responsible for a domain or component.
*   **Capabilities**:
    *   All Developer capabilities.
    *   Propose T2 changes.
    *   Approve T1 changes.
    *   Veto T0 changes.

### 3. Architect / Executive
*   **Context**: Principal engineers or CTOs responsible for system-wide integrity.
*   **Capabilities**:
    *   All Team Lead capabilities.
    *   Propose T3 changes.
    *   Approve T2 and T3 changes.
    *   Override Sentinel locks (in emergencies).

---

## Decision Tiers

Every proposed change is automatically classified into a "Tier" by the Archon engine. The tier determines the required rigor for approval.

| Tier | Name | Description | Examples | Approval Requirements |
| :--- | :--- | :--- | :--- | :--- |
| **T0** | **Routine** | Safe, local changes with no architectural impact. | Refactoring a private method, updating a comment, fixing a typo. | **Auto-Approved** (if tests pass). |
| **T1** | **Standard** | Changes that affect a single component's public interface. | Adding a new API endpoint, changing a function signature within a module. | **1 Peer Review**. |
| **T2** | **Critical** | Changes that affect multiple components or data schemas. | Database schema migration, changing a core library version, modifying auth logic. | **1 Architect Approval** + **Evidence** (Logs/Tests). |
| **T3** | **Existential** | High-risk changes that could endanger the project. | Switching cloud providers, rewriting the core engine, changing license. | **Quorum (2+ Architects)** + **Board Notification**. |

---

## The Approval Workflow

1.  **Submission**: A user submits a `DecisionIntent`.
2.  **Tiering**: Archon calculates the Tier.
3.  **Risk Analysis**: Sentinel calculates a risk score.
    *   *If Risk > 0.8*: The Tier is automatically escalated (e.g., T1 -> T2).
4.  **Debate**: The Council (AI Agents) reviews the proposal.
    *   *Proposer Agent*: Argues for the change.
    *   *Critic Agent*: Highlights potential flaws.
    *   *Auditor Agent*: checks against the "Constitution".
5.  **Voting**:
    *   Reviewers cast votes in the Archon UI (`Approve`, `Reject`, `Request Changes`).
    *   If evidence is required (T2/T3), it must be attached before approval is possible.
6.  **Ratification**: Once quorum is met, the decision generates a `Decision ID`.
7.  **Implementation**: The decision moves to the "Execution" phase.

## Drill Detection & Enforcement

Aegion monitors the codebase for "Drift" — changes that were not approved.

*   **Active Monitoring**: Sentinel runs periodically to diff the codebase against the approved Decision Graph.
*   **Drift Alert**: If unauthorized code is detected, an alert is raised.
*   **Strict Mode**: In strict environments, the CI/CD pipeline will reject commits that do not link to an approved Decision ID.
