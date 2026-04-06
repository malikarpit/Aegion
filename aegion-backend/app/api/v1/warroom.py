"""
Aegion API v1 - War Room Endpoints.

Operational cockpit providing high-level overview and incident management.
Aggregates data from presence, checkpoints, and health services.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List, Dict
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid
from ...middleware.observability import get_metrics, MetricNames

from ...core.security import AuthorityContext, get_current_user
from ...core.logging import logger
from ...models.incident import Incident, IncidentSeverity, IncidentStatus
from ...services.durable_store import JsonFileStore
# Import other services/stores if needed for aggregation (mocking for now or using their public interfaces if available)
# In a real microservices architecture, this might call other services.
# Here we can access the in-memory stores directly if they are exposed, or duplicate some logic.
# For simplicity and speed, we'll keep incidents self-contained and mock the aggregation part 
# or implement simple counters if we can access the other modules.

from .presence import _presence_store
from .checkpoints import _checkpoints as _checkpoints_store


router = APIRouter(prefix="/warroom", tags=["warroom"])


# ========== Durable Store ==========
_incidents_store = JsonFileStore(".aegion_data/incidents.json", Incident, "incident_id")


# ========== Request/Response Models ==========


class CreateIncidentRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    severity: Optional[str] = "medium"
    service: str
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, str]] = None


class IncidentResponse(BaseModel):
    incident_id: str
    title: str
    description: str
    severity: str
    status: str
    service: str
    created_by: str
    created_at: str
    resolved_at: Optional[str] = None
    tags: List[str]


class WarRoomOverview(BaseModel):
    # Status
    system_status: str = "operational"  # computed from active critical incidents
    active_incidents: int
    critical_incidents: int
    
    # Metrics
    online_users: int
    active_checkpoints: int
    
    # Recent Activity
    recent_incidents: List[IncidentResponse]


class SystemMetrics(BaseModel):
    cpu_usage_percent: float
    memory_usage_mb: float
    active_requests: int
    error_rate_1h: float
    average_response_time_ms: float


class Alert(BaseModel):
    alert_id: str
    severity: str
    message: str
    source: str
    timestamp: str
    incident_id: Optional[str] = None


# ========== Helpers ==========


def _incident_to_response(i: Incident) -> IncidentResponse:
    return IncidentResponse(
        incident_id=i.incident_id,
        title=i.title,
        description=i.description,
        severity=i.severity.value,
        status=i.status.value,
        service=i.service,
        created_by=i.created_by,
        created_at=i.created_at.isoformat(),
        resolved_at=i.resolved_at.isoformat() if i.resolved_at else None,
        tags=i.tags,
    )


# ========== Endpoints ==========


@router.get("/overview", response_model=WarRoomOverview)
async def get_warroom_overview(
    user: AuthorityContext = Depends(get_current_user),
):
    """Get high-level operational overview."""
    all_incidents = await _incidents_store.list_all()
    active_incidents = [i for i in all_incidents if i.status != IncidentStatus.RESOLVED]
    critical_incidents = [i for i in active_incidents if i.severity == IncidentSeverity.CRITICAL]
    
    # Compute system status
    if len(critical_incidents) > 0:
        sys_status = "critical"
    elif len(active_incidents) > 0:
        sys_status = "degraded"
    else:
        sys_status = "operational"

    # Sort recent incidents
    recent = sorted(active_incidents, key=lambda x: x.created_at, reverse=True)[:5]

    return WarRoomOverview(
        system_status=sys_status,
        active_incidents=len(active_incidents),
        critical_incidents=len(critical_incidents),
        online_users=len(await _presence_store.list_all()),
        active_checkpoints=len(await _checkpoints_store.list_all()),
        recent_incidents=[_incident_to_response(i) for i in recent],
    )


@router.post("/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    request: CreateIncidentRequest,
    user: AuthorityContext = Depends(get_current_user),
):
    """Report a new incident."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    now = datetime.now(timezone.utc)
    incident_id = str(uuid.uuid4())

    incident = Incident(
        incident_id=incident_id,
        title=request.title,
        description=request.description or "",
        severity=IncidentSeverity(request.severity) if request.severity else IncidentSeverity.MEDIUM,
        service=request.service,
        created_by=user.user_id,
        created_at=now,
        tags=request.tags or [],
        metadata=request.metadata or {},
    )

    await _incidents_store.save(incident)
    logger.info(f"Incident created: {incident_id} title={request.title}")
    return _incident_to_response(incident)


@router.get("/incidents", response_model=List[IncidentResponse])
async def list_incidents(
    status_filter: Optional[str] = None,
    severity: Optional[str] = None,
    user: AuthorityContext = Depends(get_current_user),
):
    """List incidents with filtering."""
    incidents = await _incidents_store.list_all()

    if status_filter:
        if status_filter == "active":
            incidents = [i for i in incidents if i.status != IncidentStatus.RESOLVED]
        else:
            incidents = [i for i in incidents if i.status.value == status_filter]

    if severity:
        incidents = [i for i in incidents if i.severity.value == severity]

    # Sort by creation time desc
    incidents.sort(key=lambda x: x.created_at, reverse=True)
    return [_incident_to_response(i) for i in incidents]


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: str,
    user: AuthorityContext = Depends(get_current_user),
):
    """Get specific incident details."""
    incident = await _incidents_store.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return _incident_to_response(incident)


@router.patch("/incidents/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: str,
    status_update: Optional[str] = None,
    user: AuthorityContext = Depends(get_current_user),
):
    """Update incident status (e.g. resolve)."""
    from ...services.archon import get_archon, GovernanceError
    archon = get_archon()
    try:
        archon.guard_writable()
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))

    incident = await _incidents_store.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    if status_update:
        new_status = IncidentStatus(status_update)
        incident.status = new_status
        incident.updated_at = datetime.now(timezone.utc)
        
        if new_status == IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.now(timezone.utc)
            
    await _incidents_store.save(incident)
    logger.info(f"Incident updated: {incident_id} status={status_update}")
    return _incident_to_response(incident)


@router.get("/telemetry", response_model=SystemMetrics)
async def get_system_metrics(
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Get real-time system telemetry.
    """
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    
    return SystemMetrics(
        cpu_usage_percent=psutil.cpu_percent(),
        memory_usage_mb=process.memory_info().rss / 1024 / 1024,
        active_requests=int(get_metrics()._gauges.get(MetricNames.ACTIVE_SESSIONS, 0)),
        error_rate_1h=round(
            get_metrics()._counters.get(MetricNames.REQUEST_ERRORS, 0)
            / max(get_metrics()._counters.get(MetricNames.REQUEST_TOTAL, 0), 1),
            4,
        ),
        average_response_time_ms=round(
            sum(get_metrics()._histograms.get(MetricNames.REQUEST_LATENCY, [0]))
            / max(len(get_metrics()._histograms.get(MetricNames.REQUEST_LATENCY, [0])), 1)
            * 1000,
            1,
        ),
    )


@router.get("/alerts", response_model=List[Alert])
async def get_active_alerts(
    user: AuthorityContext = Depends(get_current_user),
):
    """
    Get active system alerts.
    """
    alerts = []
    
    # Generate alerts based on real state
    # 1. High incident count
    all_incidents = await _incidents_store.list_all()
    active_incidents = [i for i in all_incidents if i.status != IncidentStatus.RESOLVED]
    if len(active_incidents) > 3:
        alerts.append(Alert(
            alert_id=str(uuid.uuid4()),
            severity="high",
            message=f"High incident volume: {len(active_incidents)} active",
            source="incident_monitor",
            timestamp=datetime.now(timezone.utc).isoformat()
        ))
        
    # 2. Checkpoint drift (mocked logic)
    all_checkpoints = await _checkpoints_store.list_all()
    if len(all_checkpoints) > 100:
         alerts.append(Alert(
            alert_id=str(uuid.uuid4()),
            severity="medium",
            message="High checkpoint accumulation (perform cleanup)",
            source="checkpoint_monitor",
            timestamp=datetime.now(timezone.utc).isoformat()
        ))

    return alerts
