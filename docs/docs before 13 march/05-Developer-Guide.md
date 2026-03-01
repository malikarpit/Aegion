# Aegion Developer Guide

## System Requirements
-   **OS**: macOS / Linux (Windows via WSL2)
-   **Runtime**: Python 3.12+ (Backend), Node.js 18+ (VS Code Extension)
-   **Package Managers**: `poetry` (Python), `npm` (Node)
-   **Databases**:
    -   Firestore (default dev) or PostreSQL
    -   Neo4j (optional, for graph features)

---

## Backend Setup (`aegion-backend`)

The backend is built with **FastAPI** and uses **Poetry** for dependency management.

### 1. Installation
Navigate to the backend directory:
```bash
cd aegion-backend
poetry install
```

### 2. Configuration
Copy the example environment file:
```bash
cp .env.example .env.development
```
Edit `.env.development` to set your local GCP project ID and credentials.

### 3. Running Locally
Start the development server with hot reload:
```bash
poetry run uvicorn app.main:app --reload
```
The API will be available at `http://localhost:8000`. Swagger UI at `http://localhost:8000/docs`.

### 4. Running Tests
Run the pytest suite:
```bash
poetry run pytest tests/
```

---

## Extension Setup (`aegion-vscode`)

The IDE extension is built with **TypeScript** and the VS Code Extension API.

### 1. Installation
Navigate to the extension directory:
```bash
cd aegion-vscode
npm install
```

### 2. Running in Debug Mode
1.  Open the project in VS Code.
2.  Press `F5` to launch a new "Extension Development Host" window.
3.  In the new window, the Aegion extension will be active.

### 3. Building
To compile the TypeScript code:
```bash
npm run compile
```
To package for distribution (`.vsix`):
```bash
npm run package
```

---

## Contribution Workflow

1.  **Find a Task**: Check the issue tracker for `T1` items.
2.  **Start a Session**: Use Aegion to track your own work on Aegion (dogfooding!).
3.  **Create a Branch**: `feature/my-new-feature`.
4.  **Implement**: Write code and tests.
5.  **Verify**: Ensure all tests pass.
6.  **Submit PR**: detailed description linked to the Decision ID.

## Project Structure

### Backend
-   `app/api`: FastAPI routers (v1).
-   `app/core`: Configuration and global dependencies.
-   `app/services`: Business logic (Archon, Chronos, etc.).
-   `app/models`: Pydantic data models.
-   `app/adapters`: Interfaces for external systems (DB, AI).

### Extension
-   `src/api`: Client for communicating with backend.
-   `src/views`: Webview UI components (Archon UI, Dashboard).
-   `src/services`: VS Code specific logic (Decorators, CodeLens).
