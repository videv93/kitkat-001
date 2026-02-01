"""Health check endpoint for system status (Story 4.1).

This module provides the /api/health endpoint that returns aggregated health
status from all DEX adapters, test mode status, uptime, and timestamp.

Story 4.1: Health Service & DEX Status
- AC#4: GET /api/health returns system health with all required fields
- AC#4: Unauthenticated endpoint (standard health check pattern)
"""

from fastapi import APIRouter, Depends

from kitkat.api.deps import get_health_service
from kitkat.config import get_settings
from kitkat.services.health import HealthService

router = APIRouter()


@router.get("/api/health")
async def get_health(
    health_service: HealthService = Depends(get_health_service),
) -> dict:
    """Get system health status (AC#4).

    Returns aggregated health from all DEX adapters including:
    - Overall system status (healthy/degraded/offline)
    - Per-DEX status with latency
    - Uptime since service start
    - Test mode flag
    - Current timestamp

    No authentication required (standard health check pattern).

    Returns:
        dict: System health with status, dex_status, uptime_seconds,
              test_mode flag, and timestamp
    """
    system_health = await health_service.get_system_health()
    settings = get_settings()

    return {
        "status": system_health.status,
        "test_mode": settings.test_mode,
        "uptime_seconds": health_service.uptime_seconds,
        "dex_status": {
            dex_id: {
                "status": dex.status,
                "latency_ms": dex.latency_ms,
                "error_count": dex.error_count,
                "error_message": dex.error_message,
                "last_successful": (
                    dex.last_successful.isoformat() if dex.last_successful else None
                ),
            }
            for dex_id, dex in system_health.components.items()
        },
        "timestamp": system_health.timestamp.isoformat(),
    }
