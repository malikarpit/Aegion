# Aegion System Architecture

## Overview

Aegion is a **Governed AI Development Platform** designed to ensure safety, auditability, and human oversight in autonomous software development. It functions as a bridge between high-level intent and low-level code execution.

### Architectural Principles

1.  **Governance First**: Every action is audited and validated against a set of policies.
2.  **Graph-Based Memory**: All context, decisions, and outcomes are stored in a persistent knowledge graph.
3.  **Human-in-the-Loop**: High-impact decisions require explicit human approval; AI is an advisor, not a ruler.

---

## High-Level Design

The system is composed of two main components:
1.  **Aegion VS Code Extension (`aegion-vscode`)**: The frontend interface for developers, integrated directly into their IDE.
2.  **Aegion Backend (`aegion-backend`)**: The core intelligence and governance engine, running as a separate service (FastAPI/Django).

### Component Diagram

```mermaid
graph TD
    User[Human Developer] -->|Interacts via| VSCode[VS Code Extension]
    VSCode -->|HTTP/REST + WebSocket| Backend[Aegion Backend Container]
    
    subgraph "Aegion Runtime Environment (Docker Compose)"
        Backend -->|Persist Events/Cache| Redis[Redis (Cache & PubSub)]
        Backend -->|Store Knowledge Graph| Neo4j[Neo4j (Graph DB)]
        
        subgraph "Backend Services (Monolith)"
            Backend --> Archon[Archon (Governance)]
            Backend --> Council[Council (AI Agents)]
            Backend --> Chronos[Chronos (Memory)]
        end
    end
    
    subgraph "External Integration"
        Backend -->|LLM API| OpenAI[OpenAI / Anthropic]
        Backend -->|Git Operations| LocalGit[Local Git Repo]
    end
```

## Data Foundation (Phase 1)

Aegion uses an **Event Sourcing** architecture where the **Event Log** is the single source of truth.
- **Local Mode**: Uses `SQLite` or JSONL for events, `NetworkX` for graph.
- **Team Mode**: Uses `PostgreSQL` or Firestore for events, `Neo4j` for graph.
- **Identity**: All actions are traced via `workspace_id`, `actor_id`, and `correlation_id` (ULID/UUIDv7).

---

## Core Services (The Micro-Agents)

The backend is composed of several specialized "micro-agents" or services, each with a distinct responsibility.

### 1. Archon (The Gatekeeper)
*   **Role**: Governance & Policy Enforcement.
*   **Responsibility**:
    *   Classifies incoming `DecisionIntents` into tiers (T0-T3).
    *   Enforces quorum requirements for approvals.
    *   Blocks unsafe actions based on Sentinel feedback.
    *   Manages the "constitution" or rule set of the project.

### 2. Chronos (The Timekeeper)
*   **Role**: Memory & Session Management.
*   **Responsibility**:
    *   Manages the lifecycle of development sessions.
    *   Stores immutable session artifacts (logs, diffs, chat history).
    *   Handles "time travel" (rollback/replay of decisions).
    *   Distills completed sessions for long-term storage.

### 3. Council (The Advisors)
*   **Role**: AI Collaboration & Consensus.
*   **Responsibility**:
    *   Simulates a multi-agent debate (Proposer, Critic, Auditor).
    *   Synthesizes diverse perspectives into a coherent recommendation.
    *   Provides non-binding advisory opinions to human approvers.
    *   Detects biases or blind spots in proposals.

### 4. Noesis (The Brain)
*   **Role**: Knowledge Graph Management.
*   **Responsibility**:
    *   Stores entities (Decisions, Evidence, Users, Code Artifacts).
    *   Tracks semantic relationships (e.g., "Decision A *supports* Feature B", "Evidence C *contradicts* Assumption D").
    *   Provides semantic search and context retrieval for the startup of new tasks.

### 5. Praxis (The Actor)
*   **Role**: Execution & Tooling.
*   **Responsibility**:
    *   Safely executes code and tests in isolated environments.
    *   Manages development environments and dependencies.
    *   Captures execution snapshots (inputs/outputs) for evidence.

### 6. Sentinel (The Watcher)
*   **Role**: Risk & Safety Monitoring.
*   **Responsibility**:
    *   Calculates real-time risk scores for every proposed change.
    *   Detects pattern drift and code anomalies.
    *   Monitors the "cognitive load" of the system and human operators.
    *   Triggers emergency stops if risk thresholds are breached.

---

## Data Flow: The Decision Lifecycle

Understanding how a decision moves through the system is key to understanding Aegion.

1.  **Proposal**: A User or AI agent proposes a change by creating a `DecisionIntent`.
2.  **Classification**: **Archon** analyzes the intent and calculates a `DecisionTier`:
    *   **T0 (Routine)**: Low risk, auto-approved.
    *   **T1 (Standard)**: Medium risk, peer review required.
    *   **T2 (Critical)**: High risk, rigorous review and evidence required.
    *   **T3 (Existential)**: Extreme risk, multi-stakeholder consensus required.
3.  **Analysis**:
    *   **Sentinel** calculates a risk score (0.0 - 1.0).
    *   **Noesis** checks for contradictions with past decisions.
    *   **The Council** debates the proposal and provides an advisory opinion.
4.  **Review**: The proposal enters the review queue.
    *   Approvers (Human or AI, depending on Tier) cast votes.
    *   If **Sentinel** detects high risk, it may block approval even with human votes.
5.  **Decision**: Once approved, the proposal becomes a `Decision` (Immutable record).
6.  **Execution**: **Praxis** applies the changes and verifies them against the intent.
7.  **Distillation**: **Chronos** archives the session, linking the `Decision`, `Evidence`, and final code `Commit`.

---

## Data Model Examples

### Decision Intent (JSON)

```json
{
  "title": "Migrate to Pydantic V2",
  "description": "Update all models to use ConfigDict for better performance.",
  "impact_level": "cross_module",
  "reversibility": "moderate",
  "affected_modules": ["contracts", "models"],
  "reasoning": {
    "problem_framing": "Deprecation warnings in logs are noisy.",
    "assumptions": ["V2 is backward compatible with minor tweaks."],
    "constraints": ["Must complete by Q3."]
  }
}
```

### Risk Score (JSON)

```json
{
  "overall_score": 0.85,
  "level": "HIGH",
  "component_scores": {
    "complexity": 0.9,
    "test_coverage": 0.4,
    "security_implications": 0.1
  }
}
```
