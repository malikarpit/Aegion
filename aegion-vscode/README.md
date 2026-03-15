# Aegion: Governed AI Assistant

<p align="center">
  <img src="./resources/aegion-icon.svg" alt="Aegion Logo" width="128" height="128">
</p>

<p align="center">
  <strong>AI-Powered Coding with Built-in Governance</strong><br>
  Decision tracking • Collaborative approvals • Audit trails
</p>

---

## ✨ Features

### 🤖 AI Council
Invoke AI assistance with full context awareness and structured reasoning.

### 🛡️ Tiered Governance
- **T0**: Instant auto-approval for trivial changes
- **T1**: Single engineer review
- **T2**: Multi-stakeholder quorum
- **T3**: Human escalation (War Room)

### 📊 Decision Tracking
Every AI suggestion becomes a tracked decision with:
- Full provenance and reasoning
- Evidence snapshots
- Audit compliance

### 👥 Collaborative Workflows
- Real-time proposal reviews
- Workspace collaboration
- Team visibility on active sessions

### 🕐 Chronos Memory
- Session history and artifacts
- Architecture Decision Records (ADRs)
- Time-travel to past states

---

## 🚀 Quick Start

### 1. Install Extension
Search for "Aegion" in VS Code Extensions, or install from VSIX.

### 2. Configure Backend
```json
{
    "aegion.backendUrl": "http://localhost:8000",
    "aegion.autoStartSession": false
}
```

### 3. Start a Session
- Open **Command Palette** (`Cmd+Shift+P`)
- Run **Aegion: Start Session**

### 4. Create Proposals
- Right-click in editor → **Aegion: Create Proposal**
- Or use Command Palette → **Aegion: Create Proposal**

---

## 📸 Screenshots

### Governance Sidebar
The sidebar shows your active session, recent decisions, and team activity.

### Decision Governance Center
Review proposals, vote on changes, and track approval status.

### Chronos Explorer
Browse session history and architecture decisions.

---

## 🎛️ Commands

| Command | Description |
|---------|-------------|
| `Aegion: Start Session` | Begin a governed AI session |
| `Aegion: Close Session` | End current session |
| `Aegion: Create Proposal` | Submit a new proposal |
| `Aegion: Invoke AI Council` | Get AI recommendations |
| `Aegion: Approve Proposal` | Approve a pending proposal |
| `Aegion: Show ADR Graph` | View architecture decisions |
| `Aegion: Open Dashboard` | Open system overview |
| `Aegion: Open War Room` | T3 escalation interface |

---

## ⚙️ Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `aegion.backendUrl` | `http://localhost:8000` | Backend API URL |
| `aegion.autoStartSession` | `false` | Auto-start on VS Code open |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   VS Code Extension                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │ Sidebar │ │Dashboard│ │ Chronos │ │War Room │  │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘  │
└───────┼───────────┼───────────┼───────────┼────────┘
        └───────────┴───────────┴───────────┘
                         │
                    Aegion API
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────▼────┐     ┌────▼────┐     ┌────▼────┐
   │ Archon  │     │ Chronos │     │Sentinel │
   │Governance│    │ Memory  │     │ Health  │
   └─────────┘     └─────────┘     └─────────┘
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

<p align="center">
  <sub>Built with ❤️ for enterprise AI governance</sub>
</p>
