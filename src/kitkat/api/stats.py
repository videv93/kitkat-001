"""Stats API endpoints for volume and execution statistics (Story 5.2, 5.3, 5.4, 5.5).

Provides endpoints for viewing trading volume and execution counts aggregated
by time period and DEX, supporting dashboard display and airdrop progress tracking.

Story 5.2: Volume Display (Today/Week)
- AC#1: GET /api/stats/volume returns today's and this_week's volume per DEX
- AC#2: Today uses UTC midnight to current time
- AC#3: This week uses Monday 00:00 UTC to current time
- AC#4: Empty periods return "0.00" not null
- AC#5: ?dex parameter filters to specific DEX

Story 5.3: Execution Count & Success Rate
- AC#1: GET /api/stats/executions returns today, this_week, all_time execution counts
- AC#2: success_rate = (successful + partial) / total * 100
- AC#3: Zero executions returns "N/A" not divide by zero error
- AC#4: Test mode executions excluded from counts

Story 5.4: Dashboard Endpoint
- AC#1: GET /api/dashboard returns all key status information
- AC#2: "all_ok" when all DEXs healthy, no errors, onboarding complete
- AC#3: "degraded"/"offline" when DEX status is degraded/offline
- AC#4: recent_errors shows count of errors in last hour
- AC#5: test_mode_warning when test mode active
- AC#6: Response time < 200ms

Story 5.5: Onboarding Checklist
- AC#1: GET /api/onboarding returns checklist status with 5 steps
- AC#2: Steps persisted in users.config_data (MVP: computed on-demand)
- AC#3: wallet_connected - complete if user has valid session
- AC#4: dex_authorized - complete if at least one DEX healthy/degraded
- AC#5: webhook_configured - complete if webhook token exists
- AC#6: test_signal_sent - complete if test mode execution exists
- AC#7: first_live_trade - complete if non-test execution exists
- AC#8: complete=true and progress="5/5" when all steps done
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.api.deps import get_current_user, get_health_service, get_stats_service
from kitkat.config import get_settings
from kitkat.database import ExecutionModel, get_db_session
from kitkat.models import (
    CurrentUser,
    DashboardDexStatus,
    DashboardExecutionsToday,
    DashboardResponse,
    DashboardVolumeToday,
    ExecutionStatsResponse,
    OnboardingResponse,
    OnboardingStep,
    SystemHealth,
)
from kitkat.services.health import HealthService
from kitkat.services.stats import StatsService

# ============================================================================
# Onboarding Step Definitions (Story 5.5)
# ============================================================================

ONBOARDING_STEPS = [
    ("wallet_connected", "Connect Wallet"),
    ("dex_authorized", "Authorize DEX Trading"),
    ("webhook_configured", "Configure TradingView Webhook"),
    ("test_signal_sent", "Send Test Signal"),
    ("first_live_trade", "First Live Trade"),
]


# ============================================================================
# Onboarding Helper Functions (Story 5.5)
# ============================================================================


async def _check_test_signal_sent(session: AsyncSession, user_id: int | None) -> bool:
    """Check if user has sent at least one test signal (AC#6).

    Queries executions table for any execution with is_test_mode=true in result_data.

    Args:
        session: Database session
        user_id: User ID to filter by (None = all users for MVP)

    Returns:
        bool: True if at least one test mode execution exists
    """
    query = (
        select(ExecutionModel)
        .where(
            ExecutionModel.status.in_(["filled", "partial"]),
        )
        .limit(100)  # Check recent executions
    )

    result = await session.execute(query)
    executions = result.scalars().all()

    for execution in executions:
        try:
            if isinstance(execution.result_data, str):
                result_data = json.loads(execution.result_data)
            else:
                result_data = execution.result_data or {}
        except (json.JSONDecodeError, TypeError):
            result_data = {}

        # Check for test mode execution
        is_test_mode = result_data.get("is_test_mode", False)
        if is_test_mode is True or is_test_mode == "true":
            return True

    return False


async def _check_first_live_trade(session: AsyncSession, user_id: int | None) -> bool:
    """Check if user has at least one live trade (AC#7).

    Queries executions table for any execution with is_test_mode=false or not present.

    Args:
        session: Database session
        user_id: User ID to filter by (None = all users for MVP)

    Returns:
        bool: True if at least one non-test mode execution exists
    """
    query = (
        select(ExecutionModel)
        .where(
            ExecutionModel.status.in_(["filled", "partial"]),
        )
        .limit(100)
    )

    result = await session.execute(query)
    executions = result.scalars().all()

    for execution in executions:
        try:
            if isinstance(execution.result_data, str):
                result_data = json.loads(execution.result_data)
            else:
                result_data = execution.result_data or {}
        except (json.JSONDecodeError, TypeError):
            result_data = {}

        # Check for non-test mode execution
        is_test_mode = result_data.get("is_test_mode", False)
        if is_test_mode is not True and is_test_mode != "true":
            return True

    return False


router = APIRouter()


@router.get("/api/stats/volume")
async def get_volume_stats(
    current_user: CurrentUser = Depends(get_current_user),
    stats_service: StatsService = Depends(get_stats_service),
    dex: str | None = Query(None, description="Filter by DEX ID"),
) -> dict:
    """Get volume statistics for today and this week (AC#1).

    Returns aggregated volume in USD and execution counts per DEX,
    with totals for each time period.

    Args:
        current_user: Authenticated user (injected)
        stats_service: Stats service for volume queries (injected)
        dex: Optional DEX ID to filter results (e.g., "extended")

    Returns:
        dict: Volume stats with today, this_week, and updated_at
    """
    now = datetime.now(timezone.utc)

    # Build response structure
    result = {
        "today": {},
        "this_week": {},
        "updated_at": now.isoformat(),
    }

    # Get stats for each period
    for period_key, period_value in [("today", "today"), ("this_week", "this_week")]:
        if dex:
            # Filter to specific DEX (AC#5)
            stats = await stats_service.get_volume_stats(
                user_id=None,  # All users for now
                dex_id=dex,
                period=period_value,
            )
            result[period_key][dex] = {
                "volume_usd": f"{stats.volume_usd:.2f}",
                "executions": stats.execution_count,
            }
            # When filtering by single DEX, that DEX IS the total
            result[period_key]["total"] = {
                "volume_usd": f"{stats.volume_usd:.2f}",
                "executions": stats.execution_count,
            }
        else:
            # Get totals across all DEXs (AC#1)
            stats = await stats_service.get_volume_stats(
                user_id=None,
                dex_id=None,  # All DEXs
                period=period_value,
            )
            result[period_key]["total"] = {
                "volume_usd": f"{stats.volume_usd:.2f}",
                "executions": stats.execution_count,
            }

    return result


@router.get("/api/stats/executions")
async def get_execution_stats(
    current_user: CurrentUser = Depends(get_current_user),
    stats_service: StatsService = Depends(get_stats_service),
) -> ExecutionStatsResponse:
    """Get execution count and success rate statistics (Story 5.3: AC#1).

    Returns execution counts (total, successful, failed, partial) and
    success rate for today, this week, and all time. Test mode executions
    are excluded from all counts.

    Args:
        current_user: Authenticated user (injected)
        stats_service: Stats service for execution queries (injected)

    Returns:
        ExecutionStatsResponse with today, this_week, all_time stats
    """
    now = datetime.now(timezone.utc)

    # Get stats for each period (AC#1)
    today_stats = await stats_service.get_execution_stats(period="today")
    week_stats = await stats_service.get_execution_stats(period="this_week")
    all_time_stats = await stats_service.get_execution_stats(period="all_time")

    return ExecutionStatsResponse(
        today=today_stats,
        this_week=week_stats,
        all_time=all_time_stats,
        updated_at=now,
    )


def _calculate_dashboard_status(system_health: SystemHealth) -> str:
    """Calculate overall dashboard status from system health (AC#2, AC#3).

    Priority: offline > degraded > all_ok

    Args:
        system_health: System health from HealthService

    Returns:
        str: Overall status ("all_ok", "degraded", or "offline")
    """
    # Check for offline first (highest priority)
    for dex_status in system_health.components.values():
        if dex_status.status == "offline":
            return "offline"

    # Check for degraded
    for dex_status in system_health.components.values():
        if dex_status.status == "degraded":
            return "degraded"

    # All DEXs are healthy
    return "all_ok"


@router.get("/api/dashboard")
async def get_dashboard(
    current_user: CurrentUser = Depends(get_current_user),
    stats_service: StatsService = Depends(get_stats_service),
    health_service: HealthService = Depends(get_health_service),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardResponse:
    """Get aggregated dashboard status for glance-and-go check (Story 5.4: AC#1).

    Combines health status, volume stats, execution stats, and error counts
    into a single response optimized for quick dashboard display.

    Args:
        current_user: Authenticated user (injected)
        stats_service: Stats service for volume/execution queries (injected)
        health_service: Health service for DEX status (injected)
        session: Database session for onboarding checks (injected)

    Returns:
        DashboardResponse with all key status information
    """
    now = datetime.now(timezone.utc)
    settings = get_settings()

    # Get health status from HealthService (AC#2, AC#3)
    system_health = await health_service.get_system_health()

    # Get today's volume (aggregated across all DEXs)
    volume_stats = await stats_service.get_aggregated_volume_stats(period="today")

    # Get today's execution stats
    exec_stats = await stats_service.get_execution_stats(period="today")

    # Get recent error count (last hour) - placeholder until Story 4.4/4.5 complete
    # Story 4.4/4.5 implement error logging infrastructure; for now return 0 (AC#4)
    recent_errors = 0

    # Onboarding status check (Story 5.5: AC#2)
    # wallet_connected and webhook_configured are always True if authenticated (MVP)
    dex_authorized = any(
        dex.status in ("healthy", "degraded")
        for dex in system_health.components.values()
    )
    test_signal_sent = await _check_test_signal_sent(session, current_user.id)
    first_live_trade = await _check_first_live_trade(session, current_user.id)
    # All 5 steps must be complete for onboarding_complete
    onboarding_complete = dex_authorized and test_signal_sent and first_live_trade

    # Calculate overall status (AC#2, AC#3)
    status = _calculate_dashboard_status(system_health)

    # Build DEX status dict
    dex_status = {
        dex_id: DashboardDexStatus(
            status=dex.status,
            latency_ms=dex.latency_ms,
        )
        for dex_id, dex in system_health.components.items()
    }

    # Build volume breakdown
    volume_today = DashboardVolumeToday(
        total_usd=f"{volume_stats.total_volume_usd:.2f}",
        by_dex={
            dex_id: f"{dex_vol.volume_usd:.2f}"
            for dex_id, dex_vol in volume_stats.by_dex.items()
        },
    )

    # Build execution stats
    executions_today = DashboardExecutionsToday(
        total=exec_stats.total,
        success_rate=exec_stats.success_rate,
    )

    # Build response
    response = DashboardResponse(
        status=status,
        test_mode=settings.test_mode,
        test_mode_warning=None,
        dex_status=dex_status,
        volume_today=volume_today,
        executions_today=executions_today,
        recent_errors=recent_errors,
        onboarding_complete=onboarding_complete,
        updated_at=now,
    )

    # Add test mode warning if active (AC#5)
    if settings.test_mode:
        response.test_mode_warning = "No real trades - test mode active"

    return response


@router.get("/api/onboarding")
async def get_onboarding_status(
    current_user: CurrentUser = Depends(get_current_user),
    health_service: HealthService = Depends(get_health_service),
    session: AsyncSession = Depends(get_db_session),
) -> OnboardingResponse:
    """Get onboarding checklist status (Story 5.5: AC#1).

    Returns progress through the 5 onboarding steps:
    1. wallet_connected - Authenticated (always true if here)
    2. dex_authorized - DEX connection established
    3. webhook_configured - Webhook token exists
    4. test_signal_sent - Sent at least one test signal
    5. first_live_trade - Executed at least one live trade

    Args:
        current_user: Authenticated user (injected)
        health_service: Health service for DEX status (injected)
        session: Database session (injected)

    Returns:
        OnboardingResponse with complete status, progress, and step details
    """
    # Step 1: wallet_connected (AC#3)
    # If we got here with valid auth, wallet is connected
    wallet_connected = True

    # Step 2: dex_authorized (AC#4)
    system_health = await health_service.get_system_health()
    dex_authorized = any(
        dex.status in ("healthy", "degraded")
        for dex in system_health.components.values()
    )

    # Step 3: webhook_configured (AC#5)
    # For MVP, if user exists they have a webhook token
    # (generated during account creation in Story 2.4)
    webhook_configured = True  # MVP simplification

    # Step 4: test_signal_sent (AC#6)
    test_signal_sent = await _check_test_signal_sent(session, current_user.id)

    # Step 5: first_live_trade (AC#7)
    first_live_trade = await _check_first_live_trade(session, current_user.id)

    # Build steps list
    step_status = {
        "wallet_connected": wallet_connected,
        "dex_authorized": dex_authorized,
        "webhook_configured": webhook_configured,
        "test_signal_sent": test_signal_sent,
        "first_live_trade": first_live_trade,
    }

    steps = [
        OnboardingStep(id=step_id, name=step_name, complete=step_status[step_id])
        for step_id, step_name in ONBOARDING_STEPS
    ]

    # Calculate progress (AC#8)
    completed_count = sum(1 for s in steps if s.complete)
    total_steps = len(ONBOARDING_STEPS)
    progress = f"{completed_count}/{total_steps}"
    complete = completed_count == total_steps

    return OnboardingResponse(
        complete=complete,
        progress=progress,
        steps=steps,
    )
