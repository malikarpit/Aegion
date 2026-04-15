# Aegion API v1
from fastapi import APIRouter

from .sessions import router as sessions_router
from .proposals import router as proposals_router
from .council import router as council_router
from .workspaces import router as workspaces_router
from .stream import router as stream_router
from .drafts import router as drafts_router
from .recovery import router as recovery_router
from .decisions import router as decisions_router
from .evidence import router as evidence_router, edg_router
from .analytics import sentinel_router as sentinel_analytics_router, noesis_router
from .sentinel import router as sentinel_domain_router
from .ghost_text import router as ghost_text_router
from .websocket import router as websocket_router
from .rejections import router as rejections_router
from .pipelines import router as pipelines_router
from .praxis import router as praxis_router
from .audit import router as audit_router
from .architecture import router as architecture_router
from .health import router as health_router
from .chronos import router as chronos_router
from .tasks import router as tasks_router
from .checkpoints import router as checkpoints_router
from .memory import router as memory_router
from .rules import router as rules_router
from .skills import router as skills_router
from .presence import router as presence_router
from .warroom import router as warroom_router
from .delegation import router as delegation_router
from .governance import router as governance_router
from .reasoning import router as reasoning_router
from .diff_review import router as diff_review_router
from .modes import router as modes_router
from .mcp import router as mcp_router
from .terminal import router as terminal_router
from .browser import router as browser_router
from .chatops import router as chatops_router
from .ai_commands import router as ai_commands_router
from .models import router as models_router
from .council_analytics import router as council_analytics_router
from .admin import router as admin_router
from .secrets import router as secrets_router
from .skill_invoke import router as skill_invoke_router
from .agents import router as agents_router
from .repo import router as repo_router
from .thoughts import router as thoughts_router
from .collaboration import router as collaboration_router
from .auth import router as auth_router
from .gateway import router as gateway_router
from .batch import router as batch_router
from .model_settings import router as model_settings_router
from .graph_data import router as graph_data_router

# Main v1 router
router = APIRouter()
router.include_router(gateway_router)
router.include_router(recovery_router)
router.include_router(decisions_router)
router.include_router(evidence_router)
router.include_router(proposals_router)
router.include_router(council_router)
router.include_router(workspaces_router)
router.include_router(stream_router)
router.include_router(drafts_router)
router.include_router(sessions_router)
router.include_router(edg_router)
router.include_router(sentinel_analytics_router)
router.include_router(sentinel_domain_router)
router.include_router(noesis_router)
router.include_router(ghost_text_router)
router.include_router(websocket_router)
router.include_router(rejections_router)
router.include_router(pipelines_router)
router.include_router(praxis_router)
router.include_router(audit_router)
router.include_router(architecture_router)
router.include_router(health_router)
router.include_router(chronos_router)
router.include_router(tasks_router)
router.include_router(checkpoints_router)
router.include_router(memory_router)
router.include_router(rules_router)
router.include_router(skills_router)
router.include_router(presence_router)
router.include_router(warroom_router)
router.include_router(delegation_router, prefix="/delegation", tags=["delegation"])
router.include_router(governance_router)
router.include_router(reasoning_router)
router.include_router(diff_review_router)
router.include_router(modes_router)
router.include_router(mcp_router)
router.include_router(terminal_router)
router.include_router(browser_router)
router.include_router(chatops_router)
router.include_router(ai_commands_router)
router.include_router(models_router)
router.include_router(council_analytics_router)
router.include_router(admin_router)
router.include_router(secrets_router)
router.include_router(skill_invoke_router)
router.include_router(agents_router)
router.include_router(repo_router, prefix="/repo", tags=["repo-intelligence"])
router.include_router(thoughts_router)
router.include_router(collaboration_router, prefix="/collaboration", tags=["collaboration"])
router.include_router(auth_router)
router.include_router(batch_router)
router.include_router(model_settings_router)
router.include_router(graph_data_router)

__all__ = ["router"]
