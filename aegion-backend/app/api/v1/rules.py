"""
Aegion API v1 - Rules Endpoints.

Governance rule management with org/repo scoping and evaluation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List, Any
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger
from ...models.rule import Rule, RulePriority, RuleScope
from ...services.durable_store import JsonFileStore


router = APIRouter(prefix="/rules", tags=["rules"])


# ========== Durable Store ==========
_rules_store = JsonFileStore(".aegion_data/rules.json", Rule, "rule_id")


# ========== Request/Response Models ==========


class CreateRuleRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    condition: str
    action: str
    scope: Optional[str] = "repository"
    scope_id: Optional[str] = ""
    priority: Optional[str] = "medium"
    tags: Optional[List[str]] = None
    config: Optional[dict] = None


class UpdateRuleRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    condition: Optional[str] = None
    action: Optional[str] = None
    priority: Optional[str] = None
    enabled: Optional[bool] = None
    tags: Optional[List[str]] = None
    config: Optional[dict] = None


class RuleResponse(BaseModel):
    rule_id: str
    name: str
    description: str
    condition: str
    action: str
    scope: str
    scope_id: str
    priority: str
    enabled: bool
    tags: List[str]
    created_by: str
    created_at: str
    updated_at: Optional[str] = None


class EvaluateRequest(BaseModel):
    context: dict
    scope: Optional[str] = None


class EvaluationResult(BaseModel):
    matched_rules: List[RuleResponse]
    actions: List[str]
    total_evaluated: int


# ========== Helpers ==========

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _rule_to_response(rule: Rule) -> RuleResponse:
    return RuleResponse(
        rule_id=rule.rule_id,
        name=rule.name,
        description=rule.description,
        condition=rule.condition,
        action=rule.action,
        scope=rule.scope.value,
        scope_id=rule.scope_id,
        priority=rule.priority.value,
        enabled=rule.enabled,
        tags=rule.tags,
        created_by=rule.created_by,
        created_at=rule.created_at.isoformat(),
        updated_at=rule.updated_at.isoformat() if rule.updated_at else None,
    )


# ========== Endpoints ==========


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    request: CreateRuleRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Create a governance rule."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    now = datetime.now(timezone.utc)
    rule_id = str(uuid.uuid4())

    rule = Rule(
        rule_id=rule_id,
        name=request.name,
        description=request.description or "",
        condition=request.condition,
        action=request.action,
        scope=RuleScope(request.scope) if request.scope else RuleScope.REPOSITORY,
        scope_id=request.scope_id or "",
        priority=RulePriority(request.priority) if request.priority else RulePriority.MEDIUM,
        enabled=True,
        tags=request.tags or [],
        created_by=user.user_id,
        created_at=now,
        config=request.config or {},
    )

    await _rules_store.save(rule)
    logger.info(f"Rule created: {rule_id} name={request.name}")
    return _rule_to_response(rule)


@router.get("", response_model=List[RuleResponse])
async def list_rules(
    scope: Optional[str] = None,
    enabled_only: Optional[bool] = None,
    user: AuthorityContext = Depends(get_current_user),
):
    """List rules with optional filtering."""
    rules = await _rules_store.list_all()

    if scope:
        rules = [r for r in rules if r.scope.value == scope]

    if enabled_only:
        rules = [r for r in rules if r.enabled]

    # Sort by priority (critical first)
    rules.sort(key=lambda r: PRIORITY_ORDER.get(r.priority.value, 99))
    return [_rule_to_response(r) for r in rules]


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get a specific rule."""
    rule = await _rules_store.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return _rule_to_response(rule)


@router.patch("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    request: UpdateRuleRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Update a rule."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    rule = await _rules_store.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    now = datetime.now(timezone.utc)

    if request.name is not None:
        rule.name = request.name
    if request.description is not None:
        rule.description = request.description
    if request.condition is not None:
        rule.condition = request.condition
    if request.action is not None:
        rule.action = request.action
    if request.priority is not None:
        rule.priority = RulePriority(request.priority)
    if request.enabled is not None:
        rule.enabled = request.enabled
    if request.tags is not None:
        rule.tags = request.tags
    if request.config is not None:
        rule.config = request.config

    rule.updated_at = now
    await _rules_store.save(rule)
    return _rule_to_response(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Delete a rule."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    deleted = await _rules_store.delete(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    logger.info(f"Rule deleted: {rule_id}")


@router.post("/evaluate", response_model=EvaluationResult)
async def evaluate_rules(
    request: EvaluateRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Evaluate enabled rules against a context."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    rules = await _rules_store.list_all()

    if request.scope:
        rules = [r for r in rules if r.scope.value == request.scope]

    # Only evaluate enabled rules
    enabled_rules = [r for r in rules if r.enabled]

    # Simple keyword matching on condition
    matched = []
    for rule in enabled_rules:
        # Check if any context key/value matches the condition keywords
        condition_lower = rule.condition.lower()
        for key, val in request.context.items():
            if key.lower() in condition_lower or str(val).lower() in condition_lower:
                matched.append(rule)
                break

    # Sort matched by priority
    matched.sort(key=lambda r: PRIORITY_ORDER.get(r.priority.value, 99))

    return EvaluationResult(
        matched_rules=[_rule_to_response(r) for r in matched],
        actions=[r.action for r in matched],
        total_evaluated=len(enabled_rules),
    )
