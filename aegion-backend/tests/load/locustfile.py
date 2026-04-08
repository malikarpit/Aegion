"""
Locust Load Tests for Aegion Backend — Phase 71.

Simulates concurrent user load against key API endpoints:
  - Health checks (high concurrency)
  - Council consultations (medium concurrency)
  - Session CRUD (medium concurrency)
  - Timeline queries (low concurrency)

Run:
  locust -f tests/load/locustfile.py --headless -u 100 -r 10 --run-time 60s \
    --host http://localhost:8080
"""

from locust import HttpUser, task, between, tag


class HealthCheckUser(HttpUser):
    """Simulates monitoring systems hitting health endpoints."""
    wait_time = between(0.1, 0.5)
    weight = 5  # 5x more likely to spawn

    @tag("health")
    @task(10)
    def health_basic(self):
        self.client.get("/api/v1/health", name="Health - Basic")

    @tag("health")
    @task(3)
    def health_ready(self):
        self.client.get("/api/v1/health/ready", name="Health - Ready")

    @tag("health")
    @task(1)
    def health_detailed(self):
        self.client.get("/api/v1/health/detailed", name="Health - Detailed")


class CouncilUser(HttpUser):
    """Simulates developers using the AI council."""
    wait_time = between(2, 8)
    weight = 3

    headers = {"Authorization": "Bearer load-test-token"}

    @tag("council")
    @task(5)
    def consult_child(self):
        self.client.post(
            "/api/v1/council/consult",
            json={
                "query": "How to implement connection pooling in Python?",
                "council_type": "child",
                "workspace_id": "load-test-ws",
            },
            headers=self.headers,
            name="Council - Child Consult",
        )

    @tag("council")
    @task(2)
    def consult_parent(self):
        self.client.post(
            "/api/v1/council/consult",
            json={
                "query": "Design a microservice architecture for our payment system with event sourcing and CQRS",
                "council_type": "parent",
                "workspace_id": "load-test-ws",
            },
            headers=self.headers,
            name="Council - Parent Consult",
        )

    @tag("council")
    @task(1)
    def consult_sentinel(self):
        self.client.post(
            "/api/v1/council/consult",
            json={
                "query": "Review the authentication module for security vulnerabilities",
                "council_type": "sentinel",
                "workspace_id": "load-test-ws",
            },
            headers=self.headers,
            name="Council - Sentinel Consult",
        )


class SessionUser(HttpUser):
    """Simulates session CRUD operations."""
    wait_time = between(1, 5)
    weight = 2

    headers = {"Authorization": "Bearer load-test-token"}

    @tag("sessions")
    @task(3)
    def list_sessions(self):
        self.client.get(
            "/api/v1/sessions",
            headers=self.headers,
            name="Sessions - List",
        )

    @tag("sessions")
    @task(2)
    def create_session(self):
        self.client.post(
            "/api/v1/sessions",
            json={"workspace_id": "load-test-ws"},
            headers=self.headers,
            name="Sessions - Create",
        )

    @tag("sessions")
    @task(1)
    def get_session(self):
        self.client.get(
            "/api/v1/sessions/sess-load-test-001",
            headers=self.headers,
            name="Sessions - Get",
        )


class TimelineUser(HttpUser):
    """Simulates dashboard users querying timeline."""
    wait_time = between(3, 10)
    weight = 1

    headers = {"Authorization": "Bearer load-test-token"}

    @tag("timeline")
    @task(5)
    def get_timeline(self):
        self.client.get(
            "/api/v1/timeline/events?workspace_id=load-test-ws&limit=50",
            headers=self.headers,
            name="Timeline - Events",
        )

    @tag("timeline")
    @task(2)
    def get_timeline_filtered(self):
        self.client.get(
            "/api/v1/timeline/events?workspace_id=load-test-ws&entity_type=decision&limit=20",
            headers=self.headers,
            name="Timeline - Filtered",
        )

    @tag("governance")
    @task(3)
    def list_proposals(self):
        self.client.get(
            "/api/v1/proposals?workspace_id=load-test-ws",
            headers=self.headers,
            name="Governance - List Proposals",
        )

    @tag("governance")
    @task(1)
    def list_adrs(self):
        self.client.get(
            "/api/v1/adrs?workspace_id=load-test-ws",
            headers=self.headers,
            name="Governance - List ADRs",
        )

class BatchUser(HttpUser):
    """Simulates background systems submitting and checking deferred jobs."""
    wait_time = between(5, 15)
    weight = 1

    headers = {"Authorization": "Bearer load-test-token"}

    @tag("batch")
    @task(3)
    def enqueue_job(self):
        self.client.post(
            "/api/v1/batch/enqueue",
            json={
                "query": "Review the impact of migrating to structured logging across the entire mono-repo.",
                "priority": "deferred"
            },
            headers=self.headers,
            name="Batch - Enqueue",
        )

    @tag("batch")
    @task(5)
    def check_status(self):
        self.client.get(
            "/api/v1/batch/status",
            headers=self.headers,
            name="Batch - Status",
        )
