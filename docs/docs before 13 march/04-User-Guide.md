# Aegion User Guide

## Getting Started

### Installation
1.  Install the **Aegion** extension from the VS Code Marketplace.
2.  Open your project folder.
3.  Ensure the Aegion Backend is running (see [Developer Guide](05-Developer-Guide.md) for local setup, or ask your admin for the URL).
4.  Run `Aegion: Set Role` to configure your user role.

---

## Daily Workflow

### 1. Starting a Session
Before writing code, start a session to capture your intent.
1.  Open the Command Palette (`Cmd+Shift+P`).
2.  Run `Aegion: Start Session`.
3.  (Optional) The session will automatically track your activity.

### 2. Making Decisions
When you reach a decision point (e.g., "Should we use JWT or PASETO?"):
1.  Run `Aegion: Create Proposal`.
2.  Fill out the interactive prompts:
    *   **Title**: Short summary.
    *   **Description**: Detailed explanation.
    *   **Impact Level**: Select from Trivial to System-Wide.
    *   **Reversibility**: Select from Trivial to Irreversible.
3.  A proposal will be created and the session stage will update to 'proposed'.

### 3. Seeking Guidance & Approval
1.  **Ask the Council**: Run `Aegion: Invoke AI Council` and ask a question. The AI will provide guidance or code diffs.
2.  **Approve**: For T1 decisions, run `Aegion: Approve Proposal`. You will be prompted for justification.
3.  **Reject**: If needed, run `Aegion: Reject Proposal`.

### 4. Implementing & Verifying
1.  Write your code.
2.  Run tests.
3.  Real-time governance warnings will appear if you save ungoverned changes without an active session.

### 5. Closing a Session
1.  Run `Aegion: Close Session`.
2.  You will be asked if you want to "Distill artifacts" (save memory/docs) or discard the session.

---

## Key Commands

| Command | Description |
| :--- | :--- |
| `Aegion: Start Session` | Begins a new governed development session. |
| `Aegion: Close Session` | Ends the current session and optionally distills artifacts. |
| `Aegion: Create Proposal` | Opens prompts to submit a new architectural decision. |
| `Aegion: Invoke AI Council` | Spawns a lightweight AI chat to discuss ideas or generate code. |
| `Aegion: Approve Proposal` | Approves a pending proposal (with justification). |
| `Aegion: Open Dashboard` | Opens the main Aegion dashboard. |
| `Aegion: Generate ADR` | Creates a markdown Architecture Decision Record from a decision. |
| `Aegion: Show Session Menu` | Quick access to common session actions. |

---

## Visualizations

### Chronos Memory Explorer
View the history of the project as a timeline of decisions.
*   **Access**: `Aegion: Query Memory` -> Select "Timeline View".
*   **Use**: Trace back why a piece of code exists and who approved it.

### Sentinel Health
View real-time risk metrics.
*   **Access**: Status bar icon (colored dot). Green = Safe, Red = High Risk.
*   **Data**: Shows "Code churn", "Test failures", and "Unapproved drift".
