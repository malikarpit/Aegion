# Introduction to Aegion

## What is Aegion?

Aegion is a **Governed Cognitive Layer** for architectural decision-making, designed to integrate seamlessly into your development workflow via VS Code. It serves as an intelligent guardian that ensures every significant code change is intentional, safe, and recorded.

Unlike standard AI coding assistants that simply generate code, Aegion focuses on **Governance, Memory, and Intent**. It acts as a bridge between high-level architectural goals and low-level code implementation, ensuring that the "why" behind every change is preserved alongside the "how".

## Core Value Proposition

In modern software development, context is often lost in transient chat logs or mental models. Aegion solves this by attempting to:

1.  **Capture Intent**: Force explicit declaration of *why* a change is being made before a single line of code is written.
2.  **Preserve Memory**: Store every decision in an immutable, graph-based memory structure (`Noesis`) that persists across sessions and developers.
3.  **Enforce Safety**: Automatically analyze the risk of changes (`Sentinel`) and enforce approval workflows based on impact.
4.  **Democratize Architecture**: Allow developers to propose architectural changes with the support of AI agents (`The Council`) that provide feedback and critique.

## Key Philosophies (The Doctrine)

Aegion operates on a set of core principles known as the "Doctrine":

### 1. The Graph Remembers
> *"All knowledge is connected. The graph remembers."*

Every decision, piece of evidence, and user action is recorded in the Knowledge Graph. Context is never lost, only archived. Deleting data is rare; we archive or "tombstone" it instead to maintain a perfect audit trail.

### 2. Approval is Consensus
> *"Approval is consensus, not authority."*

Governance isn't about a single gatekeeper saying "yes". It's about reaching consensus among stakeholders (human and AI) that a change is safe and beneficial. High-impact decisions require quorum.

### 3. Memory is Governed
> *"Memory is governed, not generated."*

Session history and artifacts are immutable. We don't "generate" history; we record it as it happens. This ensures that the history of your project is factual and tamper-proof.

### 4. AI Proposes, Humans Dispose
> *"AI proposes, humans dispose."*

AI agents can analyze, critique, and suggest, but they **never** have final authority on high-stakes decisions. Humans must always be in the loop for critical changes.

### 5. Start with Why
> *"Reasoning precedes action."*

Every decision must include a reasoning phase defining the problem, assumptions, and constraints *before* implementation begins. Code without intent is considered technical debt.

## Key Capabilities

-   **Role-Aware Governance**: Different users have different powers (`Developer`, `Team Lead / Architect`, `Architect / Exec`).
-   **Session Lifecycle Management**: Auto-closes sessions on inactivity, generating summaries and artifacts.
-   **Tier Classification Engine**: Automatically classifies changes as `T0` (Low Risk), `T1` (Task), `T2` (Architectural), or `T3` (Critical).
-   **The Council**: A multi-agent AI system that debates proposals, offering diverse perspectives (Proposer, Critic, Auditor).
-   **Chronos Memory Explorer**: A time-travel interface to explore past decisions and their contexts.
-   **Sentinel Risk Engine**: Real-time risk analysis and drift detection to prevent architectural erosion.
-   **Evidence-Based Decisions**: Requires concrete evidence (logs, test results) for high-impact approvals.

## Next Steps

-   Explore the [System Architecture](02-Architecture.md) to understand how Aegion works under the hood.
-   Read the [Governance Model](03-Governance-Model.md) to learn about Tiers and Roles.
-   Check the [User Guide](04-User-Guide.md) to start using Aegion in your daily workflow.
