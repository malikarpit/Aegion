"""
Aegion Nexus - Pipeline Service.

Phase 3: The Cognitive Plane
Manages decision pipelines (Hypothesis → Eval → Decision).
"""

from typing import List, Optional
from datetime import datetime
import uuid

from ...contracts.pipeline import (
    DecisionPipeline,
    Hypothesis,
    HypothesisStatus,
    EvaluationStep,
    EvaluationOutcome,
    PipelineTemplate
)
from ...core.logging import logger
from ...core.time import TimeAuthority
from ...services.durable_store import JsonFileStore


class PipelineService:
    """
    Service for managing decision pipelines.
    
    Responsibilities:
    - Create pipelines from hypotheses
    - Execute evaluation steps
    - Track pipeline progress
    - Store templates
    
    Persistence: Pipelines are durably stored via JsonFileStore
    (crash-safe atomic writes, auto-flush, signal handlers).
    """
    
    def __init__(self):
        self._pipelines: dict[str, DecisionPipeline] = {}
        self._pipeline_store = JsonFileStore(
            "data/pipelines.json", DecisionPipeline, "pipeline_id"
        )
        self._templates: dict[str, PipelineTemplate] = {}
        self._store_loaded = False
        self._init_default_templates()
    
    def _init_default_templates(self):
        """Initialize default pipeline templates."""
        # T1 Simple Review
        self._templates["t1-simple"] = PipelineTemplate(
            template_id="t1-simple",
            name="T1 Simple Review",
            description="Quick review for low-impact changes",
            step_definitions=[
                {"type": "ai_review", "description": "Child AI quick review"},
                {"type": "auto_test", "description": "Run affected unit tests"}
            ],
            applicable_tiers=["T0", "T1"]
        )
        
        # T2 Full Review
        self._templates["t2-full"] = PipelineTemplate(
            template_id="t2-full",
            name="T2 Full Review",
            description="Complete review with parent escalation",
            step_definitions=[
                {"type": "ai_review", "description": "Child AI initial review"},
                {"type": "parent_review", "description": "Parent AI escalation"},
                {"type": "integration_test", "description": "Run integration tests"},
                {"type": "peer_review", "description": "Human peer review"}
            ],
            applicable_tiers=["T2"]
        )
        
        # T3 War Room
        self._templates["t3-war-room"] = PipelineTemplate(
            template_id="t3-war-room",
            name="T3 War Room",
            description="Full escalation for critical changes",
            step_definitions=[
                {"type": "ai_review", "description": "Full AI council review"},
                {"type": "war_room", "description": "Human war room session"},
                {"type": "security_audit", "description": "Security team review"},
                {"type": "performance_test", "description": "Performance impact analysis"},
                {"type": "final_approval", "description": "Architect final sign-off"}
            ],
            applicable_tiers=["T3"]
        )
    
    async def create_pipeline(
        self,
        title: str,
        hypothesis_statement: str,
        created_by: str,
        workspace_id: str,
        proposal_id: Optional[str] = None,
        session_id: Optional[str] = None,
        template_id: Optional[str] = None
    ) -> DecisionPipeline:
        """Create a new decision pipeline."""
        pipeline_id = f"pipe-{uuid.uuid4().hex[:12]}"
        hypothesis_id = f"hyp-{uuid.uuid4().hex[:12]}"
        
        hypothesis = Hypothesis(
            hypothesis_id=hypothesis_id,
            statement=hypothesis_statement,
            created_by=created_by,
            created_at=TimeAuthority.now(),
            proposal_id=proposal_id,
            session_id=session_id
        )
        
        # Generate steps from template or default
        steps = []
        template = self._templates.get(template_id or "t1-simple")
        for i, step_def in enumerate(template.step_definitions):
            steps.append(EvaluationStep(
                step_id=f"step-{pipeline_id}-{i}",
                step_type=step_def["type"],
                description=step_def["description"]
            ))
        
        pipeline = DecisionPipeline(
            pipeline_id=pipeline_id,
            title=title,
            description=f"Pipeline for: {hypothesis_statement[:100]}",
            hypothesis=hypothesis,
            evaluation_steps=steps,
            started_at=TimeAuthority.now(),
            created_by=created_by,
            workspace_id=workspace_id
        )
        
        self._pipelines[pipeline_id] = pipeline
        await self._pipeline_store.save(pipeline)
        
        logger.audit(
            action="PIPELINE_CREATED",
            actor=created_by,
            target=pipeline_id,
            justification=title,
            metadata={"hypothesis": hypothesis_statement[:200]}
        )
        
        return pipeline
    
    async def execute_step(
        self,
        pipeline_id: str,
        step_index: int,
        outcome: EvaluationOutcome,
        notes: Optional[str] = None,
        executed_by: Optional[str] = None
    ) -> DecisionPipeline:
        """Execute and record the result of a pipeline step."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            raise ValueError(f"Pipeline {pipeline_id} not found")
        
        if step_index >= len(pipeline.evaluation_steps):
            raise ValueError(f"Invalid step index {step_index}")
        
        step = pipeline.evaluation_steps[step_index]
        step.outcome = outcome
        step.notes = notes
        step.executed_at = TimeAuthority.now()
        step.executed_by = executed_by
        
        pipeline.current_step = step_index + 1
        
        # Check if pipeline complete
        if pipeline.current_step >= len(pipeline.evaluation_steps):
            pipeline.completed_at = TimeAuthority.now()
            all_passed = all(
                s.outcome == EvaluationOutcome.PASS 
                for s in pipeline.evaluation_steps
            )
            pipeline.outcome_summary = "All steps passed" if all_passed else "Some steps failed"
        
        await self._pipeline_store.save(pipeline)
        return pipeline
    
    async def get_pipeline(self, pipeline_id: str) -> Optional[DecisionPipeline]:
        """Get a pipeline by ID (checks cache, then durable store)."""
        if pipeline_id in self._pipelines:
            return self._pipelines[pipeline_id]
        stored = await self._pipeline_store.get(pipeline_id)
        if stored:
            self._pipelines[pipeline_id] = stored
        return stored
    
    async def list_pipelines(
        self,
        workspace_id: Optional[str] = None,
        limit: int = 50
    ) -> List[DecisionPipeline]:
        """List pipelines with optional workspace filter (loads from store)."""
        all_stored = await self._pipeline_store.list_all()
        # Merge cache with store
        for p in all_stored:
            self._pipelines[p.pipeline_id] = p
        pipelines = list(self._pipelines.values())
        if workspace_id:
            pipelines = [p for p in pipelines if p.workspace_id == workspace_id]
        return pipelines[:limit]
    
    async def get_templates(self) -> List[PipelineTemplate]:
        """Get all available pipeline templates."""
        return list(self._templates.values())


# Singleton
_pipeline_service: Optional[PipelineService] = None


def get_pipeline_service() -> PipelineService:
    """Get singleton pipeline service."""
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = PipelineService()
    return _pipeline_service
