# Story 5.5: Onboarding Checklist

Status: ready-for-dev

## Story

As a **new user**,
I want **to see an onboarding checklist showing setup progress**,
So that **I know what steps remain before I can start trading**.

## Acceptance Criteria

1. **Given** an authenticated user, **When** they call `GET /api/onboarding`, **Then** the response includes checklist status:
```json
{
  "complete": false,
  "progress": "3/5",
  "steps": [
    {"id": "wallet_connected", "name": "Connect Wallet", "complete": true},
    {"id": "dex_authorized", "name": "Authorize DEX Trading", "complete": true},
    {"id": "webhook_configured", "name": "Configure TradingView Webhook", "complete": true},
    {"id": "test_signal_sent", "name": "Send Test Signal", "complete": false},
    {"id": "first_live_trade", "name": "First Live Trade", "complete": false}
  ]
}
```

2. **Given** onboarding step tracking, **When** a step is completed, **Then** it is persisted in `users.config_data` as `onboarding_steps`

3. **Given** "wallet_connected" step, **When** checked, **Then** it is complete if user has a valid session

4. **Given** "dex_authorized" step, **When** checked, **Then** it is complete if at least one DEX adapter has successful connection

5. **Given** "webhook_configured" step, **When** checked, **Then** it is complete if user has a webhook token generated

6. **Given** "test_signal_sent" step, **When** checked, **Then** it is complete if user has at least one test mode execution

7. **Given** "first_live_trade" step, **When** checked, **Then** it is complete if user has at least one non-test execution

8. **Given** all steps complete, **When** onboarding is queried, **Then** `complete: true` and `progress: "5/5"`

## Tasks / Subtasks

- [ ] Task 1: Create Pydantic response models (AC: #1)
  - [ ] 1.1 Add `OnboardingStep` model with: id, name, complete
  - [ ] 1.2 Add `OnboardingResponse` model with: complete, progress, steps
  - [ ] 1.3 Add models to `models.py` following existing naming patterns

- [ ] Task 2: Create onboarding endpoint in API (AC: #1)
  - [ ] 2.1 Add `GET /api/onboarding` endpoint to `api/stats.py` (alongside dashboard endpoint)
  - [ ] 2.2 Use `Depends(get_current_user)` for authentication
  - [ ] 2.3 Inject dependencies: StatsService, HealthService, db session
  - [ ] 2.4 Return response matching AC#1 JSON structure

- [ ] Task 3: Implement wallet_connected check (AC: #3)
  - [ ] 3.1 User has valid session → step complete (authentication itself proves wallet connected)
  - [ ] 3.2 If authenticated via `get_current_user` → wallet_connected = True

- [ ] Task 4: Implement dex_authorized check (AC: #4)
  - [ ] 4.1 Query HealthService for DEX connection status
  - [ ] 4.2 If any DEX is "healthy" or "degraded" (connected) → step complete
  - [ ] 4.3 If all DEXs "offline" → step incomplete

- [ ] Task 5: Implement webhook_configured check (AC: #5)
  - [ ] 5.1 Check if user has `webhook_token` in `users.config_data`
  - [ ] 5.2 Token presence → step complete
  - [ ] 5.3 Fallback: if user exists in system, assume webhook token exists (MVP simplification)

- [ ] Task 6: Implement test_signal_sent check (AC: #6)
  - [ ] 6.1 Query executions table for user with `is_test_mode: true` in result_data
  - [ ] 6.2 At least one test mode execution → step complete
  - [ ] 6.3 Reuse StatsService pattern for database queries

- [ ] Task 7: Implement first_live_trade check (AC: #7)
  - [ ] 7.1 Query executions table for user with `is_test_mode: false` or not present
  - [ ] 7.2 At least one non-test execution with status "filled" or "partial" → step complete
  - [ ] 7.3 Reuse existing execution query patterns from StatsService

- [ ] Task 8: Implement onboarding persistence (AC: #2)
  - [ ] 8.1 Define `onboarding_steps` structure in `users.config_data` JSON
  - [ ] 8.2 Update step completion status when detected (optional - can be computed on-demand)
  - [ ] 8.3 NOTE: For MVP, compute status dynamically rather than persisting (simpler, always accurate)

- [ ] Task 9: Calculate progress and complete status (AC: #8)
  - [ ] 9.1 Count completed steps, format as "X/5"
  - [ ] 9.2 Set `complete: true` only when all 5 steps are complete
  - [ ] 9.3 Ensure progress math is correct: completed_count / total_steps

- [ ] Task 10: Update Dashboard endpoint to use real onboarding status
  - [ ] 10.1 Replace hardcoded `onboarding_complete = True` in `/api/dashboard`
  - [ ] 10.2 Call onboarding logic to determine actual completion status
  - [ ] 10.3 Ensure backward compatibility (dashboard still works)

- [ ] Task 11: Write comprehensive tests
  - [ ] 11.1 Test endpoint returns correct JSON structure (AC#1)
  - [ ] 11.2 Test wallet_connected logic (AC#3)
  - [ ] 11.3 Test dex_authorized with healthy DEX (AC#4)
  - [ ] 11.4 Test dex_authorized with offline DEXs (AC#4)
  - [ ] 11.5 Test webhook_configured (AC#5)
  - [ ] 11.6 Test test_signal_sent with mock test execution (AC#6)
  - [ ] 11.7 Test first_live_trade with real execution (AC#7)
  - [ ] 11.8 Test progress calculation "3/5", "5/5" etc. (AC#8)
  - [ ] 11.9 Test complete=true when all steps done (AC#8)
  - [ ] 11.10 Test authentication required (401 without valid session)

## Dev Notes

### Architecture Patterns (MUST FOLLOW)

**From Project Context:**
- **File Location**: Add endpoint to existing `src/kitkat/api/stats.py`
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Imports**: Use absolute imports from `kitkat.*` package
- **Async**: ALL database operations must be async
- **Logging**: Use `structlog.get_logger()` with bound context

**CRITICAL: Extend existing files, do NOT create new ones:**
- `api/stats.py` - Add onboarding endpoint to existing router (alongside dashboard)
- `models.py` - Add OnboardingStep, OnboardingResponse models

### Existing Services to Reuse (MUST USE)

**HealthService (services/health_monitor.py):**
```python
# From Story 4.1 - get DEX connection status
async def get_system_health() -> SystemHealth
# Returns SystemHealth with components dict[str, HealthStatus]
# Each HealthStatus has .status: "healthy" | "degraded" | "offline"
```

**StatsService (services/stats.py):**
```python
# From Story 5.1 - execution queries
# Reuse pattern for querying executions table
async def get_execution_stats(period) -> ExecutionPeriodStats

# Database session pattern:
async with self._session_factory() as session:
    query = select(ExecutionModel).where(...)
    result = await session.execute(query)
```

**Dependencies (api/deps.py):**
```python
# Already implemented
get_current_user() -> CurrentUser  # Auth dependency
get_stats_service() -> StatsService  # Stats singleton
get_health_service() -> HealthService  # Health singleton
get_db_session() -> AsyncSession  # Database session
```

### Pydantic Response Models

**Add to models.py:**
```python
class OnboardingStep(BaseModel):
    """Individual onboarding step status (Story 5.5: AC#1)."""
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(..., description="Step identifier (e.g., 'wallet_connected')")
    name: str = Field(..., description="Human-readable step name")
    complete: bool = Field(..., description="Whether step is complete")


class OnboardingResponse(BaseModel):
    """Response for GET /api/onboarding endpoint (Story 5.5: AC#1).

    Shows user's progress through the onboarding checklist.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    complete: bool = Field(..., description="True if ALL steps complete")
    progress: str = Field(..., description="Progress as 'X/5' format")
    steps: list[OnboardingStep] = Field(..., description="All onboarding steps with status")
```

### Onboarding Step Definitions

**5 Required Steps (in order):**
1. `wallet_connected` - "Connect Wallet" - User has authenticated
2. `dex_authorized` - "Authorize DEX Trading" - At least one DEX connected
3. `webhook_configured` - "Configure TradingView Webhook" - Webhook token exists
4. `test_signal_sent` - "Send Test Signal" - Has test mode execution
5. `first_live_trade` - "First Live Trade" - Has non-test execution

### Implementation Approach

**Option A (Recommended for MVP): Compute on-demand**
- Query each condition dynamically when endpoint called
- No persistence needed - always accurate
- Simpler implementation, fewer moving parts

**Option B (Deferred): Persist in users.config_data**
- Store `onboarding_steps` dict in user config JSON
- Update when events happen (webhook registered, signal sent, etc.)
- More complex but potentially faster queries

**Choose Option A for this story** - simpler, meets all ACs, can optimize later if needed.

### API Endpoint Implementation

**Add to api/stats.py:**
```python
# Onboarding step definitions
ONBOARDING_STEPS = [
    ("wallet_connected", "Connect Wallet"),
    ("dex_authorized", "Authorize DEX Trading"),
    ("webhook_configured", "Configure TradingView Webhook"),
    ("test_signal_sent", "Send Test Signal"),
    ("first_live_trade", "First Live Trade"),
]


async def _check_test_signal_sent(session, user_id: int | None) -> bool:
    """Check if user has sent at least one test signal (AC#6)."""
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


async def _check_first_live_trade(session, user_id: int | None) -> bool:
    """Check if user has at least one live trade (AC#7)."""
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
```

### Dashboard Integration

**Update `/api/dashboard` in stats.py to use real onboarding status:**
```python
@router.get("/api/dashboard")
async def get_dashboard(
    current_user: CurrentUser = Depends(get_current_user),
    stats_service: StatsService = Depends(get_stats_service),
    health_service: HealthService = Depends(get_health_service),
    session: AsyncSession = Depends(get_db_session),  # ADD THIS
) -> DashboardResponse:
    # ... existing code ...

    # Replace hardcoded onboarding status with real check
    # OLD: onboarding_complete = True
    # NEW: Call the actual onboarding logic
    system_health = await health_service.get_system_health()
    dex_authorized = any(
        dex.status in ("healthy", "degraded")
        for dex in system_health.components.values()
    )
    test_signal_sent = await _check_test_signal_sent(session, current_user.id)
    first_live_trade = await _check_first_live_trade(session, current_user.id)

    # All 5 steps must be complete (wallet, dex, webhook always true for MVP)
    onboarding_complete = dex_authorized and test_signal_sent and first_live_trade

    # ... rest of existing code ...
```

### Testing Patterns

**Test File Location:** `tests/api/test_stats.py` (extend existing)

**Key Test Cases:**
```python
@pytest.mark.asyncio
async def test_onboarding_returns_correct_structure(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    """Test AC#1: Onboarding returns all required fields."""
    response = await async_client.get(
        "/api/onboarding",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Verify all required fields
    assert "complete" in data
    assert "progress" in data
    assert "steps" in data

    # Verify steps structure
    assert len(data["steps"]) == 5
    for step in data["steps"]:
        assert "id" in step
        assert "name" in step
        assert "complete" in step


@pytest.mark.asyncio
async def test_onboarding_wallet_connected_when_authenticated(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    """Test AC#3: wallet_connected is true when authenticated."""
    response = await async_client.get(
        "/api/onboarding",
        headers=authenticated_headers,
    )
    assert response.status_code == 200

    steps = {s["id"]: s for s in response.json()["steps"]}
    assert steps["wallet_connected"]["complete"] is True


@pytest.mark.asyncio
async def test_onboarding_dex_authorized_when_healthy(
    async_client: AsyncClient,
    authenticated_headers: dict,
    mock_healthy_dex,  # Fixture sets DEX to healthy
):
    """Test AC#4: dex_authorized is true when DEX is healthy."""
    response = await async_client.get(
        "/api/onboarding",
        headers=authenticated_headers,
    )
    assert response.status_code == 200

    steps = {s["id"]: s for s in response.json()["steps"]}
    assert steps["dex_authorized"]["complete"] is True


@pytest.mark.asyncio
async def test_onboarding_test_signal_with_execution(
    async_client: AsyncClient,
    authenticated_headers: dict,
    mock_test_mode_execution,  # Fixture creates test execution in DB
):
    """Test AC#6: test_signal_sent is true when test execution exists."""
    response = await async_client.get(
        "/api/onboarding",
        headers=authenticated_headers,
    )
    assert response.status_code == 200

    steps = {s["id"]: s for s in response.json()["steps"]}
    assert steps["test_signal_sent"]["complete"] is True


@pytest.mark.asyncio
async def test_onboarding_progress_format(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    """Test AC#8: Progress shows correct format."""
    response = await async_client.get(
        "/api/onboarding",
        headers=authenticated_headers,
    )
    assert response.status_code == 200

    # Progress should be "X/5" format
    progress = response.json()["progress"]
    assert "/" in progress
    parts = progress.split("/")
    assert len(parts) == 2
    assert parts[1] == "5"
    assert 0 <= int(parts[0]) <= 5


@pytest.mark.asyncio
async def test_onboarding_complete_when_all_steps_done(
    async_client: AsyncClient,
    authenticated_headers: dict,
    mock_healthy_dex,
    mock_test_mode_execution,
    mock_live_execution,
):
    """Test AC#8: complete is true when all 5 steps complete."""
    response = await async_client.get(
        "/api/onboarding",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["complete"] is True
    assert data["progress"] == "5/5"


@pytest.mark.asyncio
async def test_onboarding_requires_authentication(
    async_client: AsyncClient,
):
    """Test authentication is required."""
    response = await async_client.get("/api/onboarding")
    assert response.status_code == 401
```

### Database Query Patterns

**Execution table query for test_signal_sent (reuse from StatsService):**
```python
# Pattern from services/stats.py
from kitkat.database import ExecutionModel

async with session_factory() as session:
    query = (
        select(ExecutionModel)
        .where(ExecutionModel.status.in_(["filled", "partial"]))
        .limit(100)
    )
    result = await session.execute(query)
    executions = result.scalars().all()

    for execution in executions:
        # Parse result_data JSON
        try:
            if isinstance(execution.result_data, str):
                result_data = json.loads(execution.result_data)
            else:
                result_data = execution.result_data or {}
        except (json.JSONDecodeError, TypeError):
            result_data = {}

        is_test_mode = result_data.get("is_test_mode", False)
        # Check condition based on step being verified
```

### Previous Story Intelligence

**From Story 5.4 (Dashboard Endpoint):**
- `onboarding_complete` is currently hardcoded to `True` in lines 203-205
- Dashboard uses same `get_health_service()` dependency pattern
- Response models live in `models.py` (DashboardResponse at lines 772-845)
- Test patterns established in `tests/api/test_stats.py`

**From Story 5.1 (Stats Service):**
- JSON parsing pattern for `result_data` field (lines 218-226 in stats.py)
- `is_test_mode` check pattern (lines 227-230)
- Database session pattern with `async with self._session_factory()` (line 193)

**From Story 4.1 (Health Service):**
- `get_system_health()` returns `SystemHealth` with `components` dict
- Each component has `.status`: "healthy" | "degraded" | "offline"
- HealthService available via `Depends(get_health_service)`

### Git Commit Patterns

Recent commits show story naming convention:
- `Story 4.5: Error Log Viewer - Implementation Complete`
- `Story 5.1: Stats Service & Volume Tracking - Implementation Complete`

**Follow same pattern for this story's commits.**

### Error Handling

- Return 401 if not authenticated (handled by `get_current_user` dependency)
- Database query failures → let exceptions propagate (FastAPI returns 500)
- JSON parse failures in result_data → skip that execution, log warning
- Empty execution history → test_signal_sent=False, first_live_trade=False (not errors)

### Performance Considerations

- Query only necessary executions (limit 100 for step checks)
- DEX health check is fast (in-memory adapter status)
- No caching needed for onboarding (rarely called, must be accurate)
- Consider combining test_signal and live_trade queries if performance is issue

### Project Structure Notes

**Files to Modify:**
- `src/kitkat/api/stats.py` - Add `/api/onboarding` endpoint, helper functions
- `src/kitkat/models.py` - Add OnboardingStep, OnboardingResponse models

**Files to Update:**
- `src/kitkat/api/stats.py` - Update dashboard endpoint to use real onboarding status

**Test Files to Modify:**
- `tests/api/test_stats.py` - Add onboarding endpoint tests

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.5]
- [Source: _bmad-output/planning-artifacts/prd.md#FR33] - Onboarding checklist requirement
- [Source: _bmad-output/planning-artifacts/architecture.md] - Component patterns
- [Source: _bmad-output/implementation-artifacts/5-4-dashboard-endpoint.md] - Dashboard patterns
- [Source: src/kitkat/api/stats.py] - Existing stats router to extend (lines 1-252)
- [Source: src/kitkat/services/stats.py] - StatsService patterns (lines 1-471)
- [Source: src/kitkat/models.py] - Model definitions (lines 1-200+)
- [Source: _bmad-output/project-context.md] - Naming conventions, async patterns

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

