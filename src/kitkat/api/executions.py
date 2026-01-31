"""Execution history endpoint for viewing and filtering test/production executions (Story 3.3)."""

from datetime import datetime, timezone
from typing import Literal, Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.api.deps import get_db_session
from kitkat.models import Execution

logger = structlog.get_logger()

router = APIRouter(prefix="/api", tags=["executions"])


@router.get("/executions")
async def get_execution_history(
    db: AsyncSession = Depends(get_db_session),
    test_mode: Optional[Literal["true", "false", "all"]] = Query(
        "all",
        description="Filter by test mode: 'true' for test only, 'false' for production only, 'all' for both"
    ),
    limit: int = Query(50, ge=1, le=100, description="Number of executions to return (max 100)"),
) -> dict:
    """Get execution history with optional test mode filtering (Story 3.3: AC#5).

    Story 3.3: Supports filtering executions by is_test_mode flag in result_data JSON.
    Test mode executions are marked as "DRY RUN" in the response.

    Args:
        db: AsyncSession for database operations
        test_mode: Filter by test mode status
            - "true": Only test mode executions
            - "false": Only production executions
            - "all": Both test and production
        limit: Number of executions to return (default: 50, max: 100)

    Returns:
        dict with executions list and count, ordered by most recent first
    """
    log = logger.bind(endpoint="execution_history")

    try:
        # Build query
        query = select(Execution).order_by(Execution.created_at.desc()).limit(limit)

        # Apply test_mode filter (Story 3.3: AC#5)
        if test_mode == "true":
            # Filter to only test mode executions
            # result_data is JSON, check is_test_mode flag
            query = query.where(
                Execution.result_data["is_test_mode"].astext == "true"
            )
            log = log.bind(filter="test_mode_only")
        elif test_mode == "false":
            # Filter to only production executions
            query = query.where(
                Execution.result_data["is_test_mode"].astext != "true"
            )
            log = log.bind(filter="production_only")
        else:
            log = log.bind(filter="all")

        # Execute query
        result = await db.execute(query)
        executions = result.scalars().all()

        # Format response (Story 3.3: AC#5 - mark test executions as DRY RUN)
        execution_list = []
        for exec_record in executions:
            exec_dict = {
                "id": exec_record.id,
                "signal_id": exec_record.signal_id,
                "dex_id": exec_record.dex_id,
                "order_id": exec_record.order_id,
                "status": exec_record.status,
                "result_data": exec_record.result_data,
                "latency_ms": exec_record.latency_ms,
                "created_at": exec_record.created_at.isoformat(),
                # AC#5: Mark test executions as DRY RUN
                "mode": "DRY RUN" if exec_record.result_data.get("is_test_mode") else "LIVE",
            }
            execution_list.append(exec_dict)

        log.info("Execution history retrieved", count=len(execution_list))

        return {
            "executions": execution_list,
            "count": len(execution_list),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        log.error("Failed to retrieve execution history", error=str(e))
        raise
