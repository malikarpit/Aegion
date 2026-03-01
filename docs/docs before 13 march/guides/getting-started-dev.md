# Getting Started: Developer Guide

Welcome to Aegion! This guide will help you set up your environment and start coding with the AI Council.

## 1. Prerequisites
- **VS Code**: Version 1.85+
- **Docker**: For running the local backend.
- **Python 3.11+**: If you plan to run the backend without Docker (Advanced).

## 2. Installation
1.  **Backend**:
    ```bash
    git clone https://github.com/aegion/aegion.git
    cd aegion
    ./scripts/bootstrap_dev.sh
    ```
    This script starts the core services. Check `http://localhost:8000/api/v1/health` to confirm it's running.

2.  **Extension**:
    - Install "Aegion" from the VS Code Marketplace (Coming Soon).
    - Or build from source: `cd aegion-vscode && npm install && npm run package`.

## 3. Your First Governed Workflow

### Step 1: Start a Session
Open your Command Palette (`Cmd+Shift+P`) and run:
`> Aegion: Start Session`
*   **Why?**: Aegion tracks your work in "Sessions". This groups your thoughts, code changes, and decisions into a single context.

### Step 2: Ghost Text (Intent)
In any file, type a comment explaining what you want to do, then press `Cmd+K` (or your configured binding):
```python
# Create a robust user model with Pydantic V2
```
The Council will generate a **Thought Proposal** along with the code.

### Step 3: Consult the Council
Unsure about a security implication?
`> Aegion: Invoke AI Council`
Ask: *"Does this auth implementation follow our Zero Trust policy?"*
The Council will debate (Proposer vs. Security Auditor) and give you a consensus recommendation.

### Step 4: Commit
When you're ready, don't just `git commit`. Use the Aegion Commit workflow (in the sidebar).
Aegion generates a **Thought-Commit**:
> **feat(auth): enforce strict session timeouts**
>
> *Reasoning*: Mitigate session hijacking risk.
> *Evidence*: Passed `test_auth_contracts.py`.
> *Sign-off*: Approved by Council (T1).

## 4. Troubleshooting
- **Backend Unreachable?**: Check if Docker is running (`docker ps`).
- **Extension Error?**: Check "Output" -> "Aegion" in VS Code.
