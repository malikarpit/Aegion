# Aegion Backend

The governed AI development platform.

## Documentation

- [Runtime Flow & Architecture](docs/runtime-flow.md)
- [Threat Model](docs/threat-model.md)
- [SOC 2 Control Mapping](docs/soc2-control-mapping.md)
- [Database Model](docs/database-model.md)
- [Graph Scaling Strategy](docs/graph-scaling-strategy.md)
- [Risk Register](docs/risk-register.md)
- [Secure SDLC](docs/secure-sdlc.md)
- [Key Compromise Recovery](docs/key-compromise-recovery.md)
- [Database Migration](docs/database-migration.md)

## Getting Started

### Prerequisites
- Python 3.9+
- Neo4j (optional — for production graph adapter)
- Redis (optional — for production rate limiter)

### Installation

**Using pip (recommended):**
```bash
pip install -r requirements.txt
```

**Using Poetry:**
```bash
poetry install
```

### Running Tests
```bash
pytest tests/
```

### Running the Server
```bash
uvicorn app.main:app --reload
```

## API

The OpenAPI spec is the single source of truth: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

Interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).
