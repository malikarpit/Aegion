"""
Aegion API v1 - Health Check Endpoints.

Production-grade health checks for load balancers and monitoring.
"""

from fastapi import APIRouter, Response
from typing import Dict, Any
from enum import Enum
import asyncio
import time

from ...core.time import TimeAuthority
from ...core.logging import logger


router = APIRouter(tags=["health"])

# Track startup time for uptime calculation
_startup_time = time.monotonic()


class HealthStatus(str, Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


async def check_supabase() -> tuple[bool, str]:
    """Check Supabase connectivity with a lightweight probe."""
    try:
        from ...db.supabase_client import get_supabase_client
        client = get_supabase_client()
        # Lightweight query — select 1 row from sessions (or any table)
        result = client.table("sessions").select("id").limit(1).execute()
        return True, "connected"
    except ValueError as e:
        return True, f"not_configured ({e})"
    except Exception as e:
        return False, f"error: {type(e).__name__}: {e}"


async def check_redis() -> tuple[bool, str]:
    """Check Redis connectivity with PING."""
    try:
        import redis.asyncio as aioredis
        from ...core.config import settings
        redis_url = getattr(settings, "REDIS_URL", None)
        if not redis_url:
            return True, "not_configured (in-memory rate limiter)"
        r = aioredis.from_url(redis_url, socket_timeout=2)
        pong = await asyncio.wait_for(r.ping(), timeout=3.0)
        await r.close()
        return pong, "connected"
    except ImportError:
        return True, "sdk_not_installed (in-memory mode)"
    except asyncio.TimeoutError:
        return False, "timeout (>3s)"
    except Exception as e:
        return False, f"error: {type(e).__name__}: {e}"


async def check_graph() -> tuple[bool, str]:
    """Check graph service availability."""
    try:
        from ...services.graph_provider import get_shared_graph_service
        svc = get_shared_graph_service()
        # Use the formal health check interface
        is_healthy = await svc.graph.health_check()
        return is_healthy, "connected" if is_healthy else "connection failing"
    except Exception as e:
        return False, f"error: {type(e).__name__}: {e}"


async def check_chronos() -> tuple[bool, str]:
    """Check Chronos Timeline Service status."""
    try:
        from ...services.chronos.timeline import get_timeline_service
        svc = get_timeline_service()
        stats = svc.get_stats()
        return True, f"adrs={stats['total_adrs']}, backend={stats['backend_type']}"
    except Exception as e:
        return False, f"error: {type(e).__name__}: {e}"


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check for load balancers.
    Returns 200 if service is running.
    """
    return {
        "status": HealthStatus.HEALTHY,
        "timestamp": TimeAuthority.now(),
        "service": "aegion-backend"
    }


@router.get("/health/live")
async def liveness_probe() -> Response:
    """
    Kubernetes liveness probe.
    Returns 200 if process is alive.
    """
    return Response(status_code=200, content="OK")


@router.get("/health/ready")
async def readiness_probe() -> Dict[str, Any]:
    """
    Kubernetes readiness probe.
    Checks all dependencies before accepting traffic.
    """
    checks = {}
    overall_healthy = True

    # Run dependency checks concurrently
    supabase_result, redis_result, graph_result, chronos_result = await asyncio.gather(
        check_supabase(),
        check_redis(),
        check_graph(),
        check_chronos(),
    )

    supabase_ok, supabase_msg = supabase_result
    checks["supabase"] = {"healthy": supabase_ok, "message": supabase_msg}
    if not supabase_ok:
        overall_healthy = False

    redis_ok, redis_msg = redis_result
    checks["redis"] = {"healthy": redis_ok, "message": redis_msg}
    if not redis_ok:
        overall_healthy = False

    graph_ok, graph_msg = graph_result
    checks["graph"] = {"healthy": graph_ok, "message": graph_msg}
    if not graph_ok:
        overall_healthy = False

    chronos_ok, chronos_msg = chronos_result
    checks["chronos"] = {"healthy": chronos_ok, "message": chronos_msg}
    if not chronos_ok:
        overall_healthy = False

    status = HealthStatus.HEALTHY if overall_healthy else HealthStatus.UNHEALTHY

    response = {
        "status": status,
        "timestamp": TimeAuthority.now(),
        "checks": checks
    }

    if not overall_healthy:
        logger.warning(f"Readiness check failed: {checks}")

    return response


@router.get("/health/detailed")
async def detailed_health() -> Dict[str, Any]:
    """
    Detailed health check for monitoring dashboards.
    Includes version, uptime, and component status from real probes.
    """
    import platform
    import sys

    # Run all probes for real component status
    supabase_result, redis_result, graph_result, chronos_result = await asyncio.gather(
        check_supabase(),
        check_redis(),
        check_graph(),
        check_chronos(),
    )

    def _component(ok: bool, msg: str) -> dict:
        return {
            "status": "healthy" if ok else "unhealthy",
            "message": msg,
        }

    uptime_seconds = time.monotonic() - _startup_time

    return {
        "status": HealthStatus.HEALTHY if all(r[0] for r in [supabase_result, redis_result, graph_result, chronos_result]) else HealthStatus.DEGRADED,
        "timestamp": TimeAuthority.now(),
        "service": "aegion-backend",
        "version": "0.1.0",
        "uptime_seconds": round(uptime_seconds, 1),
        "environment": {
            "python_version": sys.version,
            "platform": platform.platform(),
        },
        "components": {
            "api": {"status": "healthy", "message": "running"},
            "supabase": _component(*supabase_result),
            "redis": _component(*redis_result),
            "graph": _component(*graph_result),
            "chronos": _component(*chronos_result),
        }
    }


@router.get("/health/metrics")
async def health_metrics_endpoint() -> Dict[str, Any]:
    """Exposes internal metrics (requests, latency, errors)."""
    try:
        from ...middleware.metrics import get_health_metrics
        return get_health_metrics()
    except ImportError:
        return {"error": "metrics middleware not installed"}


@router.get("/health/engine")
async def engine_health() -> Response:
    """
    Council engine health check — aggregate provider circuit breaker status.

    Returns:
        200 + {"health": "operational", ...}   — all providers healthy
        200 + {"health": "degraded", ...}      — some providers failing
        503 + {"health": "critical", ...}      — most providers failing
        503 + {"health": "unavailable", ...}   — all providers failing

    Used by:
        - Cognitive Sidebar OS system state strip
        - Web dashboard health indicator
        - Load balancer health checks
    """
    import json
    try:
        from ...services.council_kernel.engine import get_council_engine
        from ...services.council_kernel.types import EngineHealth

        engine = get_council_engine()
        status = engine.get_health()

        http_status = 200
        if status.health in (EngineHealth.CRITICAL, EngineHealth.UNAVAILABLE):
            http_status = 503

        return Response(
            content=json.dumps(status.model_dump(), default=str),
            status_code=http_status,
            media_type="application/json",
        )
    except Exception as exc:
        logger.error(f"Engine health check failed: {exc}")
        return Response(
            content=json.dumps({"health": "unavailable", "error": str(exc)}),
            status_code=503,
            media_type="application/json",
        )

