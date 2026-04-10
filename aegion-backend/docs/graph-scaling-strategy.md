# Graph Scaling Strategy — Aegion

> Current: In-memory NetworkX (Single Instance)
> Target: Neo4j Causal Cluster (Horizontal Scale)

## 1. Architecture Stages

| Stage | Backend | Scale | Consistency | Durability |
|---|---|---|---|---|
| **dev / test** | `NetworkX` | Single process | Strong | None (rehydrated) |
| **Stage 1 (MVP)** | `Neo4j` (Single) | Single instance | Strong | Disk |
| **Stage 2 (Pro)** | `Neo4j` (Cluster) | 3+ instances | Causal | Multi-AZ |
| **Stage 3 (Ent)** | `Neo4j` (Sharded) | Federated | Eventual | Multi-Region |

## 2. Migration Path (Memory → Neo4j)

### Step 1: Feature Flag
- Introduce `GRAPH_BACKEND` env var (`memory` or `neo4j`).
- Abstract `GraphProvider` interface to support both backends.

### Step 2: Data Dual-Write (Zero Downtime)
1. Enable `GRAPH_DUAL_WRITE=true`.
2. Writes go to BOTH Memory and Neo4j.
3. Reads still come from Memory.
4. Verify Neo4j data integrity via background job.

### Step 3: Read Switchover
1. Set `GRAPH_READ_SOURCE=neo4j`.
2. Reads now served by Neo4j.
3. Writes still go to both (safety net).

### Step 4: Deprecate Memory
1. Disable `GRAPH_DUAL_WRITE`.
2. Remove `NetworkX` dependency.

## 3. Neo4j Cluster Configuration

### Core Servers (Leader + Followers)
- **Leader**: Handles writes (RAFT consensus).
- **Followers**: Handle reads (scale-out).
- **Discovery**: `bolt+routing://neo4j-core:7687`

### Read Replicas
- Asynchronous replication from Core.
- High-volume analytical queries (e.g., PageRank, Community Detection).

## 4. Sharding Strategy (Stage 3)

### Workspace Sharding
- Physical isolation of workspaces into distinct Neo4j databases.
- `neo4j-admin copy` for moving heavy workspaces to dedicated hardware.

### Fabric Pattern
- Federated queries across shards using Neo4j Fabric.
- Example: "Find all users in Organization X across all workspace shards".
