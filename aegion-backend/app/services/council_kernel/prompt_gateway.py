"""Prompt Gateway: Cheap model preprocesses queries before council."""

from collections import deque
from .model_router import ModelRouter
from .types import ModelResponse

class PromptGateway:
    GATEWAY_MODEL = ("google", "gemini-2.0-flash")  # ~$0.00001/query
    MAX_SESSION_MEMORY = 5  # Keep last 5 turns for context
    
    def __init__(self, model_router: ModelRouter = None):
        self.router = model_router or ModelRouter()
        self._session_memory: dict[str, deque] = {}  # workspace_id -> deque
    
    def _get_memory(self, workspace_id: str) -> deque:
        if workspace_id not in self._session_memory:
            self._session_memory[workspace_id] = deque(maxlen=self.MAX_SESSION_MEMORY)
        return self._session_memory[workspace_id]
    
    async def process(self, workspace_id: str, raw_query: str) -> dict:
        """Analyze, clarify, and optimize user query before council."""
        memory = self._get_memory(workspace_id)
        context = "\n".join(f"- {m['role']}: {m['content'][:200]}" 
                           for m in memory) if memory else "No previous context."
        
        analysis_prompt = f"""You are a Prompt Gateway for an AI Council system.
Analyze the user's query and determine:
1. INTENT: What is the user actually asking? (code_review, architecture, debug, explain, generate, security, general)
2. AMBIGUITY_SCORE: 0.0 (crystal clear) to 1.0 (completely unclear)
3. MISSING_INFO: What information is missing that would help the council?
4. CLARIFYING_QUESTIONS: If ambiguity > 0.5, list 1-3 specific questions to ask
5. OPTIMIZED_PROMPT: Rewrite the query to be specific, structured, and token-efficient
6. COMPLEXITY: simple | medium | complex
7. ESTIMATED_COUNCIL_TYPE: child | parent | sentinel

Previous conversation context:
{context}

User's raw query: "{raw_query}"

Respond in JSON format only."""

        provider, model = self.GATEWAY_MODEL
        
        # Ensure we have the provider registered, otherwise fallback to mock/openai
        try:
            if provider not in self.router.providers:
                # If Gemini isn't registered via keys, fallback to whatever is registered (usually openai)
                if self.router.providers:
                    provider = list(self.router.providers.keys())[0]
                    # Attempt to grab the cheapest model from the fallback provider
                    spec_list = self.router.providers[provider].list_models()
                    if spec_list:
                        spec_list.sort(key=lambda s: s.input_price_per_m)
                        model = spec_list[0].model_id
            
            result = await self.router.call(provider, model, analysis_prompt, json_mode=True)
            
            import json
            try:
                analysis = json.loads(result.response)
            except json.JSONDecodeError:
                # Attempt to extract JSON if the model returns markdown guards
                clean_json = result.response.replace("```json", "").replace("```", "").strip()
                try:
                    analysis = json.loads(clean_json)
                except json.JSONDecodeError:
                    analysis = {
                        "intent": "general", "ambiguity_score": 0.0,
                        "missing_info": [], "clarifying_questions": [],
                        "optimized_prompt": raw_query, "complexity": "medium",
                        "estimated_council_type": "child"
                    }
                    
            cost_usd = result.cost_usd
            tokens_in = result.tokens_in
            tokens_out = result.tokens_out
            
        except Exception as e:
            # Fallback if any router error occurs (no keys, network fail, etc)
            analysis = {
                "intent": "general", "ambiguity_score": 0.0,
                "missing_info": [], "clarifying_questions": [],
                "optimized_prompt": raw_query, "complexity": "medium",
                "estimated_council_type": "child",
                "error": str(e)
            }
            cost_usd = 0.0
            tokens_in = 0
            tokens_out = 0
            model = "fallback"
            provider = "none"
        
        # Store in session memory
        memory.append({"role": "user", "content": raw_query})
        
        # We simulate DB tracking if supabase_client fails since we're optimizing
        try:
            from app.db.supabase_client import SupabaseDB
            db = SupabaseDB()
            await db.client.table("cost_tracking").insert({
                "workspace_id": workspace_id, "provider": provider,
                "model": model, "input_tokens": tokens_in,
                "output_tokens": tokens_out, "cost_usd": cost_usd,
                "request_type": "prompt_gateway"
            }).execute()
        except Exception as db_exc:
            from ...core.logging import logger as _gw_logger
            _gw_logger.debug(f"Prompt gateway cost tracking DB write skipped: {db_exc}")
        
        # Fallback assignment for raw string prompts
        optimized_prompt = analysis.get("optimized_prompt", raw_query)
        if not isinstance(optimized_prompt, str):
            optimized_prompt = raw_query
            
        return {
            "raw_query": raw_query,
            "analysis": analysis,
            "needs_clarification": float(analysis.get("ambiguity_score", 0)) > 0.5,
            "clarifying_questions": analysis.get("clarifying_questions", []),
            "optimized_prompt": optimized_prompt,
            "suggested_council_type": analysis.get("estimated_council_type", "child"),
            "complexity": analysis.get("complexity", "medium"),
            "gateway_cost_usd": cost_usd,
            "token_savings_estimate": max(0, len(raw_query.split()) - len(optimized_prompt.split()))
        }
    
    async def submit_approved_prompt(self, workspace_id: str, 
                                       approved_prompt: str,
                                       user_edits: str = None) -> str:
        """User approved/edited the optimized prompt. Store and return final."""
        final = user_edits if user_edits else approved_prompt
        memory = self._get_memory(workspace_id)
        memory.append({"role": "assistant", "content": f"[Optimized]: {final[:200]}"})
        return final

# Global singleton will be instantiated with engine's router inside engine.py, 
# but we provide a default empty construct here if accessed directly
prompt_gateway = PromptGateway()
