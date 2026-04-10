# AEGION Cost Optimization Strategy
# How to Run Multi-LLM Councils Without Going Broke

> **Version**: 1.0.0  
> **Status**: Research Complete  
> **Last Updated**: 2026-03-14

---

## Table of Contents

1. [The Cost Problem](#1-the-cost-problem)
2. [Deployment Platform Comparison](#2-deployment-platform-comparison)
3. [LLM API Pricing Landscape](#3-llm-api-pricing-landscape)
4. [Cost Optimization Techniques](#4-cost-optimization-techniques)
5. [AEGION Cost Architecture](#5-aegion-cost-architecture)
6. [User-Facing Cost Controls](#6-user-facing-cost-controls)
7. [Projected Cost Scenarios](#7-projected-cost-scenarios)

---

## 1. The Cost Problem

AEGION's Council Kernel (ACK) requires **multiple LLM calls per decision**:

| Council Type | LLM Calls per Invocation | When Triggered |
|---|---|---|
| Child AI Council | 3-5 models × 1 round | Every developer question |
| Distillation Council | 2-3 models × 2 rounds | Every session close |
| Parent AI Council | 3-5 models × 3 rounds (max) | Every T2/T3 promotion |
| Sentinel Analysis Council | 2-4 agents × 1 round | Every code change |
| Fresh Eyes Validation | 1 model × 1 call | After synthesis |

**Worst case**: A single T3 architectural decision could trigger **20+ LLM calls**.

Without optimization, this is unsustainable. The strategies below can reduce costs by **80-98%** while maintaining council quality.

---

## 2. Deployment Platform Comparison (Top 5)

### Recommendation: **Hetzner + Supabase**

| Rank | Platform | Starter Cost | Free Tier | Best For | Why |
|---|---|---|---|---|---|
| 🥇 | **Hetzner** | €3.49/mo (1 vCPU, 2GB RAM, 20GB SSD, 20TB traffic) | ❌ No free tier | Production backend | **Cheapest raw compute**, predictable pricing, 20TB included traffic, EU data residency |
| 🥈 | **Render** | $0/mo (750 free instance hours) | ✅ Generous — 750h/mo compute + 1GB Postgres | Staging / early MVP | Free web services + free Postgres (1GB), startup program up to $100K credits |
| 🥉 | **Railway** | $5/mo ($5 credit included) | ✅ $5 credit/mo | Dev/test environments | Easy Git deploys, managed Postgres, good DX, effectively free below $5/mo usage |
| 4 | **Fly.io** | ~$1.94/mo (256MB shared) | ⚠️ $5 one-time credit | Global edge deployment | Run close to users, good for WebSocket-heavy apps, but higher learning curve |
| 5 | **Oracle Cloud** | $0/mo (ARM, 4 cores, 24GB RAM) | ✅ Always-free ARM VMs | Budget-constrained production | Most generous free tier (4 OCPU + 24GB), but complex setup, variable availability |

### 🏆 REVISED: With $300 GCP Credits (Primary Recommendation)

| Component | Provider | Cost | Credits Burn Rate |
|---|---|---|---|
| **Backend** (FastAPI) | **GCP Cloud Run** | ~$5-15/mo (scale-to-zero) | 20-60 months of runway |
| **LLM API** (Gemini) | **Vertex AI** | Gemini Flash: $0.075/M tokens | ~$10-30/mo → 10-30 months |
| **Database + Vector DB + Auth + Realtime** | **Supabase Free** | $0/mo | Free forever (500MB DB) |
| **Frontend** (Next.js) | **Firebase Hosting** | $0/mo (10GB bandwidth) | Free forever |
| **VS Code Extension** | VS Marketplace | $0/mo | — |
| **Object Storage** | GCP Cloud Storage | ~$0.02/mo | Essentially free |
| **Monitoring** | GCP Cloud Monitoring | $0/mo (free tier) | — |
| **Total** | — | **$0/mo** (on credits) | **$300 lasts 12-24 months** |

> [!IMPORTANT]
> **With $300 GCP credits, AEGION runs for FREE for 12-24 months.** When credits expire, fallback to Hetzner (€3.49/mo) + keep Supabase free tier.

### Fallback Stack (Post-Credits)

| Component | Provider | Cost |
|---|---|---|
| **Backend** (FastAPI) | Hetzner CX22 | €3.49/mo |
| **Database + Vector DB + Auth + Realtime** | Supabase Free | $0/mo (up to 500MB DB, 50K MAU) |
| **Frontend** (Next.js) | Render Free | $0/mo (static site) |
| **VS Code Extension** | VS Marketplace | $0/mo |
| **Redis (caching)** | Render Free Redis | $0/mo (or Upstash Free: 10K commands/day) |
| **Total Infra** | — | **~$4/mo** |

> [!TIP]
> **Supabase is the strategic choice** because it eliminates 4 separate services:
> - PostgreSQL database (replaces InMemoryGraph)
> - pgvector for embeddings (replaces separate vector DB)
> - Supabase Auth (can replace Firebase Auth)
> - Realtime subscriptions (WebSocket for collaboration)
> All on a free tier with 500MB storage, scaling to $25/mo for 8GB when needed.

---

## 3. LLM API Pricing Landscape (2025-2026)

### Price per Million Tokens

| Model | Input $/M | Output $/M | Total for 1M in + 1M out | Intelligence | Best For |
|---|---|---|---|---|---|
| **DeepSeek V3** | $0.014 | $0.028 | **$0.04** | High (GPT-4 class) | 💰 Default for everything — 180x cheaper than GPT-4o |
| **Gemini 1.5 Flash** | $0.075 | $0.30 | **$0.38** | Good | Fast tasks, summarization, classification |
| **Gemini 2.5 Flash-Lite** | $0.10 | $0.40 | **$0.50** | Good | Structured output, light reasoning |
| **GPT-4o Mini** | $0.15 | $0.60 | **$0.75** | Good | When you need OpenAI compatibility |
| **Claude Haiku 4.5** | $1.00 | $5.00 | **$6.00** | High | Fast, smart, good at code review |
| **GPT-4o** | $2.50 | $10.00 | **$12.50** | Very High | Complex reasoning, architecture |
| **Claude Sonnet 4.5** | $3.00 | $15.00 | **$18.00** | Very High | Best code generation |
| **Gemini 2.5 Pro** | $1.25 | $10.00 | **$11.25** | Very High | Long-context analysis (1M tokens) |
| **Claude Opus 4.5** | $5.00 | $25.00 | **$30.00** | Highest | Most complex reasoning |
| **Local (Ollama)** | $0.00 | $0.00 | **$0.00** | Variable | Confidential data, infinite usage |

> [!IMPORTANT]
> **DeepSeek V3 is 312x cheaper than Claude Sonnet 4.5** for the same token volume.
> A council that costs $54 with Claude Sonnet costs $0.12 with DeepSeek V3.
> This is the single biggest cost lever.

### User API Key Model

AEGION should **never pay for LLM API calls**. Users provide their own keys:

```
User provides:
  - OpenAI API key       → GPT-4o, GPT-4o Mini
  - Anthropic API key    → Claude Haiku/Sonnet/Opus
  - Google AI key        → Gemini Flash/Pro
  - DeepSeek API key     → DeepSeek V3
  - Ollama endpoint      → Local models (free)
  - Custom endpoint      → Any OpenAI-compatible API

AEGION provides:
  - Council orchestration
  - Governance enforcement
  - Cost optimization layer
  - NO LLM API costs
```

---

## 4. Cost Optimization Techniques

### 4.1 🏗️ Technique 1: LLM Cascade (FrugalGPT Pattern)

**Source**: Stanford FrugalGPT paper (Chen, Zaharia, Zou, 2023)  
**Savings**: 80-98% cost reduction with same accuracy

**Principle**: Start cheap, escalate only when needed.

```
User Query
    │
    ▼
┌────────────────────────────┐
│ TIER 1: DeepSeek V3        │  $0.04/M tokens
│ (cheapest, fast)           │
│                            │
│ → Confidence > 85%?        │
│   YES → Return response    │
│   NO  → Escalate ↓        │
└────────────────────────────┘
    │
    ▼
┌────────────────────────────┐
│ TIER 2: GPT-4o Mini        │  $0.75/M tokens
│ (good balance)             │
│                            │
│ → Confidence > 80%?        │
│   YES → Return response    │
│   NO  → Escalate ↓        │
└────────────────────────────┘
    │
    ▼
┌────────────────────────────┐
│ TIER 3: Claude Sonnet 4.5  │  $18.00/M tokens
│ (best quality)             │
│                            │
│ → Always return response   │
└────────────────────────────┘
```

**Implementation for AEGION:**

```python
# aegion-backend/app/services/council_kernel/cascade.py

class LLMCascade:
    """FrugalGPT-style cascade for cost-optimal model selection."""
    
    TIERS = [
        CascadeTier(
            model="deepseek-v3",
            cost_per_1m_tokens=0.04,
            confidence_threshold=0.85,
            max_latency_ms=3000
        ),
        CascadeTier(
            model="gpt-4o-mini",
            cost_per_1m_tokens=0.75,
            confidence_threshold=0.80,
            max_latency_ms=5000
        ),
        CascadeTier(
            model="claude-sonnet-4.5",
            cost_per_1m_tokens=18.00,
            confidence_threshold=0.0,  # always accept
            max_latency_ms=15000
        ),
    ]
    
    async def query(self, prompt: str, task_type: str) -> CascadeResult:
        for tier in self.TIERS:
            response = await self.call_model(tier.model, prompt)
            confidence = await self.score_confidence(response, task_type)
            
            if confidence >= tier.confidence_threshold:
                return CascadeResult(
                    response=response,
                    model_used=tier.model,
                    cost=self.calculate_cost(prompt, response, tier),
                    confidence=confidence,
                    tier_used=tier.level,
                    tiers_tried=tier.level
                )
        
        # Should never reach here (last tier always accepts)
        return self.TIERS[-1].response

    async def score_confidence(self, response: str, task_type: str) -> float:
        """Score response confidence using a lightweight classifier.
        Uses DistilBERT-based scoring (fast, cheap, local)."""
        # Checks: factual consistency, completeness, uncertainty markers
        return self.confidence_scorer.score(response, task_type)
```

**Expected result**: ~70% of queries answered at Tier 1 (DeepSeek), ~20% at Tier 2, ~10% at Tier 3.
**Cost impact**: Average cost drops from $18/M to ~$1.50/M (**92% savings**).

---

### 4.2 💾 Technique 2: Semantic Caching

**Source**: GPTCache (open-source), academic research on embedding-based caching  
**Savings**: 70-86% fewer API calls, 10x faster responses on cache hits

**Principle**: If someone asked a semantically similar question before, return the cached answer.

```
New Query
    │
    ▼
┌────────────────────────────┐
│ Embed query (via pgvector)  │
│ → vector = embed(query)     │
│                             │
│ Search cache:               │
│ SELECT response, similarity │
│ FROM semantic_cache          │
│ WHERE similarity > 0.92     │
│ ORDER BY similarity DESC     │
│ LIMIT 1                     │
│                             │
│ → HIT?                      │
│   YES → Return cached (0ms) │
│   NO  → Query LLM ↓        │
└────────────────────────────┘
    │ (cache miss)
    ▼
┌────────────────────────────┐
│ Query LLM via Cascade       │
│ → Store in cache:           │
│   INSERT INTO semantic_cache│
│   (embedding, query,        │
│    response, model,         │
│    created_at, ttl)         │
└────────────────────────────┘
```

**Implementation for AEGION (using Supabase pgvector):**

```sql
-- Supabase migration: semantic cache table
CREATE TABLE semantic_cache (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_embedding vector(384) NOT NULL,  -- all-MiniLM-L6-v2 embeddings
    response_text TEXT NOT NULL,
    response_model TEXT NOT NULL,
    council_type TEXT NOT NULL,
    workspace_id UUID NOT NULL,
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT fk_workspace FOREIGN KEY (workspace_id) 
        REFERENCES workspaces(id) ON DELETE CASCADE
);

-- pgvector index for fast similarity search
CREATE INDEX idx_cache_embedding 
ON semantic_cache USING ivfflat (query_embedding vector_cosine_ops)
WITH (lists = 100);

-- Function: find similar cached response
CREATE OR REPLACE FUNCTION find_cached_response(
    p_embedding vector(384),
    p_workspace_id UUID,
    p_similarity_threshold FLOAT DEFAULT 0.92
)
RETURNS TABLE (
    response_text TEXT,
    similarity FLOAT,
    response_model TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sc.response_text,
        1 - (sc.query_embedding <=> p_embedding) AS similarity,
        sc.response_model
    FROM semantic_cache sc
    WHERE sc.workspace_id = p_workspace_id
      AND sc.expires_at > NOW()
      AND 1 - (sc.query_embedding <=> p_embedding) > p_similarity_threshold
    ORDER BY sc.query_embedding <=> p_embedding
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;
```

**TTL Strategy:**

| Content Type | TTL | Reason |
|---|---|---|
| Code explanations | 7 days | Code changes infrequently |
| Architecture Q&A | 30 days | Architecture decisions are stable |
| Security analysis | 1 day | Dependencies update frequently |
| Council debate results | 14 days | Debate outcomes are contextual |

**Expected result**: 40-60% cache hit rate in steady-state usage.

---

### 4.3 ✂️ Technique 3: Prompt Compression (LLMLingua)

**Source**: Microsoft Research — LLMLingua / LongLLMLingua papers  
**Savings**: 5-20x fewer input tokens with <1.5% accuracy loss

**Principle**: Use a small local model to remove unnecessary tokens from prompts before sending to expensive LLMs.

```
Original Prompt (2000 tokens)
    │
    ▼
┌────────────────────────────┐
│ LLMLingua Compressor        │
│ (local, runs on CPU)        │
│                             │
│ Removes:                    │
│ - Filler words              │
│ - Redundant context         │
│ - Non-essential formatting  │
│ - Low-information tokens    │
└────────────────────────────┘
    │
    ▼
Compressed Prompt (400 tokens)  ← 5x reduction
    │
    ▼
Send to LLM API
    │
    ▼
Cost: $0.002 instead of $0.010
```

**Implementation:**

```python
# aegion-backend/app/services/council_kernel/prompt_compressor.py

from llmlingua import PromptCompressor

class AEGIONPromptCompressor:
    """Compress prompts before sending to LLMs to save tokens."""
    
    def __init__(self):
        # Uses a small local model (runs on CPU, ~500MB)
        self.compressor = PromptCompressor(
            model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
            use_llmlingua2=True
        )
    
    async def compress(
        self, 
        prompt: str, 
        target_ratio: float = 0.3,  # Keep 30% of tokens
        context_type: str = "general"
    ) -> CompressedPrompt:
        
        # Don't compress short prompts (overhead not worth it)
        if len(prompt.split()) < 100:
            return CompressedPrompt(
                text=prompt, 
                ratio=1.0, 
                tokens_saved=0
            )
        
        result = self.compressor.compress_prompt(
            prompt,
            rate=target_ratio,
            force_tokens=["Archon", "Sentinel", "Chronos", "governance", 
                         "approve", "reject", "risk", "decision"],
            drop_consecutive=True
        )
        
        return CompressedPrompt(
            text=result["compressed_prompt"],
            ratio=result["ratio"],
            tokens_saved=result["origin_tokens"] - result["compressed_tokens"],
            original_tokens=result["origin_tokens"],
            compressed_tokens=result["compressed_tokens"]
        )
```

**When to compress:**

| Scenario | Compress? | Target Ratio |
|---|---|---|
| Code review context (large diffs) | ✅ Yes | 0.25 (keep 25%) |
| Historical ADR context | ✅ Yes | 0.30 (keep 30%) |
| Council debate context (round 2+) | ✅ Yes | 0.40 (keep 40%) |
| User's direct question | ❌ No | 1.0 (keep all) |
| Governance rules/constitution | ❌ No | 1.0 (keep all) |

---

### 4.4 🎯 Technique 4: Smart Council Sizing

**Principle**: Not every question needs a full 5-model council.

```python
# aegion-backend/app/services/council_kernel/council_sizer.py

class CouncilSizer:
    """Dynamically size councils based on task complexity."""
    
    PROFILES = {
        "trivial": {
            # "What does this function do?"
            "models": 1,
            "rounds": 1,
            "peer_review": False,
            "fresh_eyes": False,
            "estimated_cost_factor": 1.0
        },
        "simple": {
            # "Refactor this function"
            "models": 2,
            "rounds": 1,
            "peer_review": True,
            "fresh_eyes": False,
            "estimated_cost_factor": 2.5
        },
        "moderate": {
            # "Review this PR for security issues"  
            "models": 3,
            "rounds": 2,
            "peer_review": True,
            "fresh_eyes": False,
            "estimated_cost_factor": 7.0
        },
        "complex": {
            # "Should we migrate to microservices?"
            "models": 4,
            "rounds": 3,
            "peer_review": True,
            "fresh_eyes": True,
            "estimated_cost_factor": 15.0
        },
        "critical": {
            # T3 governance decision
            "models": 5,
            "rounds": 3,
            "peer_review": True,
            "fresh_eyes": True,
            "persona_debate": True,
            "estimated_cost_factor": 25.0
        }
    }
    
    async def classify(self, query: str, context: SessionContext) -> str:
        """Classify query complexity using a cheap model."""
        # Uses DeepSeek V3 to classify (costs ~$0.001)
        classification = await self.classifier.classify(
            query=query,
            governance_tier=context.current_tier,
            session_type=context.session_type
        )
        return classification  # Returns profile key
```

**Cost impact**: Most developer interactions use "trivial" or "simple" profiles (1-2 models), not full 5-model councils.

---

### 4.5 📦 Technique 5: Request Batching

**Principle**: Combine multiple small requests into single API calls.

```python
# aegion-backend/app/services/council_kernel/batcher.py

class CouncilBatcher:
    """Batch multiple council requests into single LLM calls."""
    
    def __init__(self, max_batch_size: int = 5, flush_interval_ms: int = 200):
        self.queue: List[CouncilRequest] = []
        self.max_batch_size = max_batch_size
        self.flush_interval_ms = flush_interval_ms
    
    async def add(self, request: CouncilRequest):
        self.queue.append(request)
        
        if len(self.queue) >= self.max_batch_size:
            return await self.flush()
    
    async def flush(self):
        """Combine multiple requests into a single LLM call."""
        if not self.queue:
            return
        
        batch = self.queue[:self.max_batch_size]
        self.queue = self.queue[self.max_batch_size:]
        
        # Combine into single prompt with delimiters
        combined_prompt = self._build_batch_prompt(batch)
        
        # Single API call instead of N calls
        result = await self.llm.generate(combined_prompt)
        
        # Split response and distribute to requesters
        individual_responses = self._split_batch_response(result, len(batch))
        
        for request, response in zip(batch, individual_responses):
            request.resolve(response)
```

**Best for**: Sentinel analysis (multiple files changed at once), batch code review.

---

### 4.6 🏠 Technique 6: Local Model Offloading

**Principle**: Run cheap/fast tasks on local models (Ollama), save API budget for complex reasoning.

| Task | Run Locally? | Model | Why |
|---|---|---|---|
| Code completion | ✅ Yes | DeepSeek Coder 6.7B | Fast, good quality, free |
| Prompt classification | ✅ Yes | Phi-3 Mini | Tiny, fast, good at classification |
| Embedding generation | ✅ Yes | all-MiniLM-L6-v2 | 80MB model, runs on any CPU |
| Confidence scoring | ✅ Yes | DistilBERT | Fast classifier for cascade |
| Prompt compression | ✅ Yes | LLMLingua (BERT) | CPU-compatible |
| Code review | ⚠️ Hybrid | Local draft + cloud refinement | Draft locally, refine via API |
| Architecture debate | ❌ No | Claude/GPT-4o | Requires top-tier reasoning |

**Implementation:**

```python
# aegion-backend/app/services/council_kernel/local_offloader.py

class LocalModelOffloader:
    """Route simple tasks to local models, save API budget for complex work."""
    
    LOCAL_MODELS = {
        "embedding": {
            "model": "sentence-transformers/all-MiniLM-L6-v2",
            "runtime": "sentence-transformers",  # CPU-compatible
            "vram_required": 0,  # Runs on CPU
            "tasks": ["embedding_generation", "similarity_search"]
        },
        "classifier": {
            "model": "distilbert-base-uncased",
            "runtime": "transformers",
            "vram_required": 0,
            "tasks": ["confidence_scoring", "query_classification", "task_routing"]
        },
        "code_completion": {
            "model": "deepseek-coder:6.7b",
            "runtime": "ollama",
            "vram_required": 4096,  # 4GB
            "tasks": ["code_completion", "code_explanation", "docstring_generation"]
        },
        "compressor": {
            "model": "llmlingua-2-bert",
            "runtime": "llmlingua",
            "vram_required": 0,
            "tasks": ["prompt_compression"]
        }
    }
```

---

### 4.7 💰 Technique 7: Provider Pricing Arbitrage

**Principle**: Same model available at different prices across providers.

```python
# aegion-backend/app/services/council_kernel/price_arbitrage.py

PROVIDER_PRICES = {
    "claude-sonnet-4.5": {
        "anthropic_direct": {"input": 3.00, "output": 15.00},
        "openrouter": {"input": 2.70, "output": 13.50},      # 10% cheaper
        "amazon_bedrock": {"input": 3.00, "output": 15.00},
    },
    "gpt-4o": {
        "openai_direct": {"input": 2.50, "output": 10.00},
        "azure_openai": {"input": 2.50, "output": 10.00},
        "openrouter": {"input": 2.25, "output": 9.00},        # 10% cheaper
    },
    "deepseek-v3": {
        "deepseek_direct": {"input": 0.014, "output": 0.028},
        "openrouter": {"input": 0.014, "output": 0.028},
        # Cache hit pricing: 90% cheaper
        "deepseek_cached": {"input": 0.0014, "output": 0.028},
    }
}

class PriceArbitrageur:
    """Find cheapest provider for each model at any given time."""
    
    async def get_cheapest_provider(self, model: str) -> ProviderConfig:
        prices = PROVIDER_PRICES.get(model, {})
        return min(prices.items(), key=lambda p: p[1]["input"] + p[1]["output"])
```

---

### 4.8 🔄 Technique 8: Response Distillation (Fine-Tune Cheap Models)

**Principle**: Use expensive model outputs to train a cheap model for your specific domain.

```
Phase 1: Collect training data
──────────────────────────────
Run councils with expensive models (Claude, GPT-4o)
Log all (prompt, response) pairs
Focus on AEGION governance domain

Phase 2: Fine-tune cheap model
──────────────────────────────
Take DeepSeek V3 or Gemini Flash
Fine-tune on your logged (prompt, response) pairs
Result: A model that's 180x cheaper but domain-specialized

Phase 3: Deploy as primary
──────────────────────────────
Replace expensive model with fine-tuned cheap model
for common governance tasks
Reserve expensive models for edge cases only
```

**When to do this**: After ~10,000 council interactions have been logged.

---

## 5. AEGION Cost Architecture

### Combined Optimization Pipeline

```
User Query
    │
    ▼
┌────────────────────────┐
│ 1. Semantic Cache Check │ ← 40-60% of queries stop here
│    (pgvector in Supa)   │    Cost: $0.00
└──────────┬─────────────┘
           │ Cache miss
           ▼
┌────────────────────────┐
│ 2. Council Sizer       │ ← Classifies complexity
│    (local classifier)  │    Cost: $0.00
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│ 3. Prompt Compression  │ ← 5-20x token reduction
│    (LLMLingua, local)  │    Cost: $0.00
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│ 4. LLM Cascade         │ ← Start with cheapest model
│    (FrugalGPT pattern) │    70% answered at Tier 1
│                        │
│    T1: DeepSeek V3     │    $0.04/M
│    T2: GPT-4o Mini     │    $0.75/M
│    T3: Claude Sonnet   │    $18.00/M
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│ 5. Cache Store         │ ← Save for future hits
│    + Cost Tracking     │
└────────────────────────┘
```

### Net Effect

| Without Optimization | With Full Pipeline |
|---|---|
| 100% queries hit LLM | 40-60% served from cache |
| All queries use expensive model | 70% use cheapest model |
| Full-length prompts | 5-20x compressed prompts |
| 5-model councils for everything | Right-sized per complexity |
| **~$18/1M tokens average** | **~$0.15/1M tokens average** |

**Overall savings: 99%+**

---

## 6. User-Facing Cost Controls

### 6.1 User Cost Dashboard

```python
# aegion-backend/app/api/v1/cost.py

@router.get("/cost/summary")
async def get_cost_summary(
    workspace_id: UUID = Depends(get_workspace),
    period: str = Query("month")
):
    return {
        "period": period,
        "total_api_calls": 1247,
        "total_tokens_used": 2_340_000,
        "total_cost_usd": 3.42,
        "savings_from_cache": 1.89,
        "savings_from_cascade": 4.56,
        "savings_from_compression": 0.87,
        "total_savings_usd": 7.32,
        "breakdown_by_model": {
            "deepseek-v3": {"calls": 892, "cost": 0.45},
            "gpt-4o-mini": {"calls": 287, "cost": 1.23},
            "claude-sonnet-4.5": {"calls": 68, "cost": 1.74}
        },
        "breakdown_by_council": {
            "child": {"calls": 1100, "cost": 1.20},
            "distillation": {"calls": 89, "cost": 0.67},
            "parent": {"calls": 42, "cost": 1.12},
            "sentinel": {"calls": 16, "cost": 0.43}
        }
    }
```

### 6.2 Configurable Budget Limits

```python
# aegion-backend/app/services/council_kernel/budget_manager.py

class BudgetManager:
    """Per-user and per-workspace budget controls."""
    
    async def check_budget(self, workspace_id: UUID, estimated_cost: float) -> bool:
        budget = await self.get_workspace_budget(workspace_id)
        spent = await self.get_period_spending(workspace_id)
        
        if spent + estimated_cost > budget.hard_limit:
            raise BudgetExceededError(
                f"Budget limit ${budget.hard_limit}/month reached. "
                f"Spent: ${spent:.2f}. "
                f"Consider upgrading or adjusting council depth."
            )
        
        if spent + estimated_cost > budget.soft_limit:
            await self.notify_user(
                workspace_id, 
                f"⚠️ Approaching budget limit: ${spent:.2f}/${budget.soft_limit}"
            )
        
        return True
    
    DEFAULT_BUDGETS = {
        "free": {"soft_limit": 5.0, "hard_limit": 10.0},
        "hobby": {"soft_limit": 25.0, "hard_limit": 50.0},
        "pro": {"soft_limit": 100.0, "hard_limit": 200.0},
        "enterprise": {"soft_limit": 1000.0, "hard_limit": float("inf")}
    }
```

### 6.3 Cost-Quality Slider

Let users choose their trade-off:

```python
QUALITY_PRESETS = {
    "economy": {
        # Maximum savings, acceptable quality
        "cascade_enabled": True,
        "cache_enabled": True,
        "compression_enabled": True,
        "max_council_size": 2,
        "max_debate_rounds": 1,
        "primary_model": "deepseek-v3",
        "estimated_cost_per_query": "$0.001"
    },
    "balanced": {
        # Good quality, good savings
        "cascade_enabled": True,
        "cache_enabled": True,
        "compression_enabled": True,
        "max_council_size": 3,
        "max_debate_rounds": 2,
        "primary_model": "gpt-4o-mini",
        "estimated_cost_per_query": "$0.008"
    },
    "premium": {
        # Best quality, higher cost
        "cascade_enabled": False,  # Always use best model
        "cache_enabled": True,
        "compression_enabled": True,
        "max_council_size": 5,
        "max_debate_rounds": 3,
        "primary_model": "claude-sonnet-4.5",
        "estimated_cost_per_query": "$0.05"
    }
}
```

---

## 7. Projected Cost Scenarios

### Scenario: Solo Developer, 8 hours/day

| Activity | Frequency | Without Optimization | With Optimization |
|---|---|---|---|
| Code questions | 50/day | $2.50 | $0.05 |
| Code reviews | 10/day | $1.80 | $0.12 |
| Session closures | 3/day | $0.90 | $0.08 |
| Architecture decisions | 1/week | $2.00 | $0.15 |
| **Daily total** | — | **$7.20** | **$0.28** |
| **Monthly total** | — | **$158** | **$6.16** |

### Scenario: 5-Person Team

| Activity | Frequency | Without Optimization | With Optimization |
|---|---|---|---|
| All dev activities | 5x solo | $36/day | $1.10/day |
| T2/T3 decisions | 5/week | $10/week | $0.75/week |
| **Monthly total** | — | **$830** | **$27** |

> [!TIP]
> **The bottom line**: A solo developer using AEGION with full cost optimization spends roughly **$6/month** on LLM API calls — less than a cup of coffee per week. The infrastructure cost (Hetzner + Supabase free) adds ~$4/month. **Total: ~$10/month** for a fully governed AI development environment.

---

## Appendix: Key Research References

| Paper / Tool | Key Finding | AEGION Application |
|---|---|---|
| **FrugalGPT** (Stanford, 2023) | 98% cost reduction via LLM cascade with confidence scoring | Model Router cascade |
| **GPTCache** (Zilliz, 2023) | 70-86% fewer API calls via semantic similarity caching | Semantic cache layer |
| **LLMLingua** (Microsoft, 2023) | 20x prompt compression with <1.5% accuracy loss | Prompt compressor |
| **LongLLMLingua** (Microsoft, 2024) | 21.4% quality improvement + 4x fewer tokens for long context | Context compression |
| **"Talk Isn't Always Cheap"** (Xiong, 2025) | Extended debate increases confidence but decreases accuracy | 3-round hard limit |
| **DistilBERT** (Hugging Face) | Fast, lightweight confidence scoring | Cascade tier classifier |
| **500xCompressor** (2024) | Up to 480x compression into single token | Future: extreme compression |
