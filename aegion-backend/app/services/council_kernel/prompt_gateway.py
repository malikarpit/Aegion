"""Prompt Gateway: processes queries before council. Initial passthrough version."""

from .model_router import ModelRouter


class PromptGateway:
    """Forwards prompts to council without preprocessing."""
    GATEWAY_MODEL = ("google", "gemini-2.0-flash")

    def __init__(self, model_router: ModelRouter = None):
        self.router = model_router or ModelRouter()

    async def process(self, workspace_id: str, raw_query: str) -> dict:
        """Pass query through without analysis. Full gateway logic TBD."""
        return {
            "raw_query": raw_query,
            "analysis": {"intent": "general", "ambiguity_score": 0.0},
            "needs_clarification": False,
            "clarifying_questions": [],
            "optimized_prompt": raw_query,
            "suggested_council_type": "child",
            "complexity": "medium",
            "gateway_cost_usd": 0.0,
            "token_savings_estimate": 0,
        }


prompt_gateway = PromptGateway()
