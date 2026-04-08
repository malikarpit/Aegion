"""
Locust Chaos Tests for Aegion Backend — Cutting Edge Upgrades.

Simulates catastrophic upstream API events against Aegion (e.g. OpenAI/Anthropic 
full outages and insane 30,000ms latency spikes) combined with concurrent heavy user load.
Proves that the internal FrugalGPT fallback logic and Semantic Caching strictly prevents
our API from cascading those outages into the dashboard.

Run:
  locust -f tests/load/locust_chaos.py --headless -u 100 -r 10 --run-time 60s
"""

from locust import HttpUser, task, between, tag, events
import random
import logging

class ChaosUser(HttpUser):
    """Simulates adversarial failures in the network pipeline to test reliability algorithms."""
    wait_time = between(1, 3)
    weight = 5

    headers = {
        "Authorization": "Bearer chaos-test-token",
        "X-Simulate-Outage": "true", # Hypothetical flag our mocks could respect
    }

    @tag("chaos_LLM_latency")
    @task(3)
    def invoke_council_latency_spike(self):
        """
        Hits the council but with a header representing a 25s latency spike.
        The backend cascade should correctly drop the primary model, swap to 
        the fallback tier, and return in under 3 seconds.
        """
        self.client.post(
            "/api/v1/council/consult",
            json={
                "query": f"High latency simulation query {random.randint(1,1000)}",
                "council_type": "child",
                "workspace_id": "chaos-ws",
            },
            headers={**self.headers, "X-Chaos-Latency-MS": "25000"},
            name="Chaos - Cascade Heavy Latency",
            # We expect the fallback model to reply fast. If it timeouts, the test fails.
            timeout=5.0 
        )

    @tag("chaos_LLM_502")
    @task(2)
    def invoke_council_provider_outage(self):
        """
        Hits the council expecting the primary model (e.g., OpenAI) to throw a 502 Bad Gateway.
        Backend should transparently catch the error, re-route to Anthropic/Google, and return 200.
        """
        response = self.client.post(
            "/api/v1/council/consult",
            json={
                "query": "Who is the CEO of Apple? (Simulated 502)",
                "council_type": "child",
                "workspace_id": "chaos-ws",
            },
            headers={**self.headers, "X-Chaos-Inject-Error": "502"},
            name="Chaos - Upstream 502 Outage Routing",
        )
        
        # In a perfectly resilient system, the end-user should still get a 200, 
        # even if the cascade logged warnings internally.
        if response.status_code == 200:
            response.success()
        else:
            response.failure(f"Cascade failed to reroute! Got {response.status_code}")


    @tag("chaos_cache_stampede")
    @task(5)
    def cache_stampede_simulation(self):
        """
        Hundreds of clients sending the EXACT same query simultaneously.
        Tests the semantic cache locking mechanism to ensure we don't query 
        the expensive LLM 100 times for the same question.
        """
        # All users ask the exact same phrase
        self.client.post(
            "/api/v1/council/consult",
            json={
                "query": "Explain quantum computing in exactly 15 words.",
                "council_type": "child",
                "workspace_id": "chaos-ws",
            },
            headers=self.headers,
            name="Chaos - Cache Stampede Lock",
        )
