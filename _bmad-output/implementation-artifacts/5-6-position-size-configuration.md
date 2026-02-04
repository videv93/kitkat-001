# Story 5.6: Position Size Configuration

Status: done

## Story

As a **user**,
I want **to configure my position size per trade and maximum limit**,
So that **I can control my risk exposure**.

## Acceptance Criteria

1. **Given** an authenticated user, **When** they call `GET /api/config`, **Then** the response includes position size settings:
```json
{
  "position_size": "0.5",
  "max_position_size": "10.0",
  "position_size_unit": "ETH"
}
```

2. **Given** an authenticated user, **When** they call `PUT /api/config` with:
```json
{
  "position_size": "1.0",
  "max_position_size": "5.0"
}
```
**Then** the settings are updated in `users.config_data` **And** the response confirms the new values

3. **Given** position size validation, **When** `position_size` is set, **Then** it must be > 0 **And** it must be <= `max_position_size`

4. **Given** max position size validation, **When** `max_position_size` is set, **Then** it must be > 0 **And** a system-wide absolute maximum is enforced (e.g., 100 ETH)

5. **Given** an order execution, **When** size exceeds `max_position_size`, **Then** the order is rejected with error: "Position size exceeds configured maximum" **And** the signal is logged but not executed

6. **Given** default values, **When** a new user is created, **Then** `position_size` defaults to "0.1" **And** `max_position_size` defaults to "10.0"

## Tasks / Subtasks

- [x] Task 1: Create Pydantic request/response models (AC: #1, #2)
  - [x] 1.1 Add `PositionSizeConfig` response model with: position_size, max_position_size, position_size_unit
  - [x] 1.2 Add `PositionSizeUpdate` request model with: position_size (optional), max_position_size (optional)
  - [x] 1.3 Add validation constraints to models (gt=0, le=100)
  - [x] 1.4 Add models to `models.py` following existing naming patterns

- [x] Task 2: Create configuration API router (AC: #1, #2)
  - [x] 2.1 Create new `api/config.py` file for configuration endpoints
  - [x] 2.2 Add `GET /api/config` endpoint with `Depends(get_current_user)`
  - [x] 2.3 Add `PUT /api/config` endpoint with request body validation
  - [x] 2.4 Register router in `main.py` alongside existing routers

- [x] Task 3: Implement GET /api/config endpoint (AC: #1)
  - [x] 3.1 Query user's `config_data` JSON field from database
  - [x] 3.2 Extract position_size and max_position_size from config_data
  - [x] 3.3 Apply defaults if values not present (0.1 and 10.0)
  - [x] 3.4 Return `PositionSizeConfig` response with position_size_unit = "ETH"

- [x] Task 4: Implement PUT /api/config endpoint (AC: #2, #3, #4)
  - [x] 4.1 Validate incoming position_size > 0 (if provided)
  - [x] 4.2 Validate incoming max_position_size > 0 and <= 100 ETH (if provided)
  - [x] 4.3 Cross-validate: position_size <= max_position_size (consider updated values)
  - [x] 4.4 Update user's config_data JSON in database
  - [x] 4.5 Return updated `PositionSizeConfig` response

- [x] Task 5: Add position_size validation to Signal Processor (AC: #5)
  - [x] 5.1 Load user's max_position_size from config before execution
  - [x] 5.2 Compare incoming signal size against max_position_size
  - [x] 5.3 If exceeds limit: reject with error code "POSITION_SIZE_EXCEEDED"
  - [x] 5.4 Log rejected signal with full context (payload, user config, reason)
  - [x] 5.5 Do NOT send to DEX adapters if limit exceeded

- [x] Task 6: Set default values for new users (AC: #6)
  - [x] 6.1 Update user creation flow (Story 2.2/2.3 code) to set defaults
  - [x] 6.2 Default config_data structure: `{"position_size": "0.1", "max_position_size": "10.0"}`
  - [x] 6.3 Ensure existing users without config work (apply defaults on read)

- [x] Task 7: Write comprehensive tests
  - [x] 7.1 Test GET /api/config returns correct structure (AC#1)
  - [x] 7.2 Test GET /api/config returns defaults when not configured
  - [x] 7.3 Test PUT /api/config updates values correctly (AC#2)
  - [x] 7.4 Test PUT /api/config validates position_size > 0 (AC#3)
  - [x] 7.5 Test PUT /api/config validates max_position_size <= 100 (AC#4)
  - [x] 7.6 Test cross-validation: position_size <= max_position_size (AC#3)
  - [x] 7.7 Test signal rejection when size exceeds limit (AC#5)
  - [x] 7.8 Test rejected signal is logged but not executed (AC#5)
  - [x] 7.9 Test new user gets default values (AC#6)
  - [x] 7.10 Test authentication required for both endpoints (401 without session)

## Dev Notes

### Architecture Patterns (MUST FOLLOW)

**From Project Context:**
- **File Location**: Create NEW `src/kitkat/api/config.py` for configuration endpoints
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Imports**: Use absolute imports from `kitkat.*` package
- **Async**: ALL database operations must be async
- **Logging**: Use `structlog.get_logger()` with bound context
- **Decimal**: Use `Decimal` for position size values (NOT float)

**CRITICAL: Follow existing patterns:**
- Pattern from `api/stats.py` for router structure and dependencies
- Pattern from `services/stats.py` for database JSON field access
- Error response format from project-context.md

### Existing Components to Reuse (MUST USE)

**User Model (database.py / models.py):**
```python
# User table structure from Story 2.2
class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_address: Mapped[str] = mapped_column(String, unique=True, index=True)
    config_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

**Dependencies (api/deps.py):**
```python
# Already implemented
get_current_user() -> CurrentUser  # Auth dependency
get_db_session() -> AsyncSession   # Database session
```

**Signal Processor (services/signal_processor.py):**
```python
# Location to add size validation (Story 2.9)
# Add check before calling adapters
async def process_signal(self, signal: Signal) -> ProcessingResult:
    # ... existing validation ...
    # ADD: Check if signal.size > user.max_position_size
    # ... fan-out to adapters ...
```

### Pydantic Models

**Add to models.py:**
```python
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class PositionSizeConfig(BaseModel):
    """Response for GET /api/config endpoint (Story 5.6: AC#1).

    Shows user's current position size configuration.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    position_size: str = Field(
        ...,
        description="Position size per trade (e.g., '0.5')"
    )
    max_position_size: str = Field(
        ...,
        description="Maximum allowed position size (e.g., '10.0')"
    )
    position_size_unit: str = Field(
        default="ETH",
        description="Unit for position sizes"
    )


class PositionSizeUpdate(BaseModel):
    """Request body for PUT /api/config endpoint (Story 5.6: AC#2).

    Allows updating position size settings. Both fields are optional -
    only provided fields are updated.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    position_size: Decimal | None = Field(
        default=None,
        gt=0,
        description="New position size per trade (must be > 0)"
    )
    max_position_size: Decimal | None = Field(
        default=None,
        gt=0,
        le=100,
        description="New maximum position size (must be > 0 and <= 100)"
    )
```

### API Endpoint Implementation

**Create api/config.py:**
```python
"""Configuration API endpoints (Story 5.6).

Provides endpoints for reading and updating user configuration,
specifically position size settings.
"""

import json
from decimal import Decimal

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.api.deps import get_current_user, get_db_session
from kitkat.database import UserModel
from kitkat.models import CurrentUser, PositionSizeConfig, PositionSizeUpdate

logger = structlog.get_logger()

router = APIRouter(prefix="/api", tags=["config"])

# Default values (AC#6)
DEFAULT_POSITION_SIZE = Decimal("0.1")
DEFAULT_MAX_POSITION_SIZE = Decimal("10.0")
SYSTEM_MAX_POSITION_SIZE = Decimal("100.0")


def _get_config_value(
    config_data: dict | None,
    key: str,
    default: Decimal
) -> Decimal:
    """Extract config value with default fallback."""
    if not config_data:
        return default
    value = config_data.get(key)
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return default


@router.get("/config")
async def get_config(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PositionSizeConfig:
    """Get user's position size configuration (Story 5.6: AC#1).

    Returns current position size settings with defaults applied
    if not explicitly configured.

    Args:
        current_user: Authenticated user (injected)
        session: Database session (injected)

    Returns:
        PositionSizeConfig with current settings
    """
    log = logger.bind(user_id=current_user.id)
    log.debug("Fetching user config")

    # Query user's config_data
    query = select(UserModel).where(UserModel.id == current_user.id)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        # User authenticated but not in DB - shouldn't happen
        log.error("Authenticated user not found in database")
        raise HTTPException(status_code=404, detail="User not found")

    # Extract values with defaults
    config_data = user.config_data or {}
    position_size = _get_config_value(
        config_data, "position_size", DEFAULT_POSITION_SIZE
    )
    max_position_size = _get_config_value(
        config_data, "max_position_size", DEFAULT_MAX_POSITION_SIZE
    )

    log.info(
        "Config retrieved",
        position_size=str(position_size),
        max_position_size=str(max_position_size)
    )

    return PositionSizeConfig(
        position_size=str(position_size),
        max_position_size=str(max_position_size),
        position_size_unit="ETH",
    )


@router.put("/config")
async def update_config(
    config_update: PositionSizeUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PositionSizeConfig:
    """Update user's position size configuration (Story 5.6: AC#2, #3, #4).

    Validates and updates position size settings. Both fields are optional -
    only provided fields are updated.

    Validation rules:
    - position_size must be > 0 (AC#3)
    - max_position_size must be > 0 and <= 100 (AC#4)
    - position_size must be <= max_position_size (AC#3)

    Args:
        config_update: New configuration values
        current_user: Authenticated user (injected)
        session: Database session (injected)

    Returns:
        PositionSizeConfig with updated settings

    Raises:
        HTTPException 400: If validation fails
    """
    log = logger.bind(user_id=current_user.id)
    log.debug("Updating user config", update=config_update.model_dump())

    # Get current user and config
    query = select(UserModel).where(UserModel.id == current_user.id)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        log.error("Authenticated user not found in database")
        raise HTTPException(status_code=404, detail="User not found")

    # Get current values with defaults
    config_data = dict(user.config_data) if user.config_data else {}
    current_position_size = _get_config_value(
        config_data, "position_size", DEFAULT_POSITION_SIZE
    )
    current_max_size = _get_config_value(
        config_data, "max_position_size", DEFAULT_MAX_POSITION_SIZE
    )

    # Determine new values (use current if not provided)
    new_position_size = config_update.position_size or current_position_size
    new_max_size = config_update.max_position_size or current_max_size

    # Cross-validation: position_size <= max_position_size (AC#3)
    if new_position_size > new_max_size:
        log.warning(
            "Position size exceeds max",
            position_size=str(new_position_size),
            max_position_size=str(new_max_size)
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "position_size cannot exceed max_position_size",
                "code": "INVALID_CONFIG",
                "position_size": str(new_position_size),
                "max_position_size": str(new_max_size),
            }
        )

    # Update config_data
    config_data["position_size"] = str(new_position_size)
    config_data["max_position_size"] = str(new_max_size)

    # Save to database
    update_stmt = (
        update(UserModel)
        .where(UserModel.id == current_user.id)
        .values(config_data=config_data)
    )
    await session.execute(update_stmt)
    await session.commit()

    log.info(
        "Config updated",
        position_size=str(new_position_size),
        max_position_size=str(new_max_size)
    )

    return PositionSizeConfig(
        position_size=str(new_position_size),
        max_position_size=str(new_max_size),
        position_size_unit="ETH",
    )
```

### Signal Processor Size Validation

**Add to services/signal_processor.py:**
```python
# In process_signal method, BEFORE fan-out to adapters:

async def process_signal(self, signal: Signal, user: User) -> ProcessingResult:
    """Process validated signal and route to DEX adapters."""
    log = logger.bind(signal_id=signal.id, user_id=user.id)

    # ... existing validation (deduplication, etc.) ...

    # Position size validation (Story 5.6: AC#5)
    user_max_size = _get_user_max_position_size(user.config_data)
    if signal.size > user_max_size:
        log.warning(
            "Signal size exceeds configured maximum",
            signal_size=str(signal.size),
            max_allowed=str(user_max_size)
        )
        # Log the rejection but don't execute
        await self._log_rejected_signal(
            signal=signal,
            reason="POSITION_SIZE_EXCEEDED",
            details={
                "signal_size": str(signal.size),
                "max_allowed": str(user_max_size),
            }
        )
        return ProcessingResult(
            status="rejected",
            error="Position size exceeds configured maximum",
            code="POSITION_SIZE_EXCEEDED",
            signal_id=signal.id,
        )

    # ... continue with adapter fan-out ...


def _get_user_max_position_size(config_data: dict | None) -> Decimal:
    """Get user's max position size with default fallback."""
    if not config_data:
        return DEFAULT_MAX_POSITION_SIZE
    value = config_data.get("max_position_size")
    if value is None:
        return DEFAULT_MAX_POSITION_SIZE
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return DEFAULT_MAX_POSITION_SIZE
```

### Router Registration

**Update main.py:**
```python
from kitkat.api import webhook, health, stats, config  # ADD config

# In create_app():
app.include_router(config.router)  # ADD this line
```

### Testing Patterns

**Create tests/api/test_config.py:**
```python
"""Tests for configuration API endpoints (Story 5.6)."""

import pytest
from httpx import AsyncClient
from decimal import Decimal


@pytest.mark.asyncio
async def test_get_config_returns_correct_structure(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    """Test AC#1: GET /api/config returns all required fields."""
    response = await async_client.get(
        "/api/config",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Verify all required fields
    assert "position_size" in data
    assert "max_position_size" in data
    assert "position_size_unit" in data

    # Verify types
    assert isinstance(data["position_size"], str)
    assert isinstance(data["max_position_size"], str)
    assert data["position_size_unit"] == "ETH"


@pytest.mark.asyncio
async def test_get_config_returns_defaults_when_not_configured(
    async_client: AsyncClient,
    authenticated_headers: dict,
    user_without_config,  # Fixture: user with no config_data
):
    """Test AC#6: Defaults applied when not configured."""
    response = await async_client.get(
        "/api/config",
        headers=authenticated_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["position_size"] == "0.1"
    assert data["max_position_size"] == "10.0"


@pytest.mark.asyncio
async def test_put_config_updates_values(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    """Test AC#2: PUT /api/config updates and returns new values."""
    response = await async_client.put(
        "/api/config",
        headers=authenticated_headers,
        json={
            "position_size": "1.0",
            "max_position_size": "5.0"
        }
    )
    assert response.status_code == 200
    data = response.json()

    assert data["position_size"] == "1.0"
    assert data["max_position_size"] == "5.0"


@pytest.mark.asyncio
async def test_put_config_validates_position_size_positive(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    """Test AC#3: position_size must be > 0."""
    response = await async_client.put(
        "/api/config",
        headers=authenticated_headers,
        json={"position_size": "-1.0"}
    )
    assert response.status_code == 422  # Pydantic validation


@pytest.mark.asyncio
async def test_put_config_validates_max_not_exceed_system_limit(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    """Test AC#4: max_position_size must be <= 100."""
    response = await async_client.put(
        "/api/config",
        headers=authenticated_headers,
        json={"max_position_size": "150.0"}
    )
    assert response.status_code == 422  # Pydantic validation


@pytest.mark.asyncio
async def test_put_config_cross_validates_size_vs_max(
    async_client: AsyncClient,
    authenticated_headers: dict,
):
    """Test AC#3: position_size cannot exceed max_position_size."""
    response = await async_client.put(
        "/api/config",
        headers=authenticated_headers,
        json={
            "position_size": "20.0",
            "max_position_size": "5.0"
        }
    )
    assert response.status_code == 400
    data = response.json()
    assert "INVALID_CONFIG" in str(data)


@pytest.mark.asyncio
async def test_config_endpoints_require_authentication(
    async_client: AsyncClient,
):
    """Test both endpoints require authentication."""
    get_response = await async_client.get("/api/config")
    assert get_response.status_code == 401

    put_response = await async_client.put(
        "/api/config",
        json={"position_size": "1.0"}
    )
    assert put_response.status_code == 401
```

**Add signal rejection test to tests/services/test_signal_processor.py:**
```python
@pytest.mark.asyncio
async def test_signal_rejected_when_size_exceeds_max(
    signal_processor: SignalProcessor,
    mock_user_with_config,  # Fixture: user with max_position_size="5.0"
):
    """Test AC#5: Signal rejected if size > max_position_size."""
    signal = Signal(
        id="test-123",
        symbol="ETH-PERP",
        side="buy",
        size=Decimal("10.0"),  # Exceeds limit of 5.0
    )

    result = await signal_processor.process_signal(
        signal=signal,
        user=mock_user_with_config,
    )

    assert result.status == "rejected"
    assert result.code == "POSITION_SIZE_EXCEEDED"
    assert "exceeds configured maximum" in result.error


@pytest.mark.asyncio
async def test_rejected_signal_is_logged_not_executed(
    signal_processor: SignalProcessor,
    mock_user_with_config,
    mock_dex_adapter,  # Should NOT be called
):
    """Test AC#5: Rejected signals are logged but not sent to DEX."""
    signal = Signal(
        id="test-456",
        symbol="ETH-PERP",
        side="sell",
        size=Decimal("100.0"),  # Way over any limit
    )

    result = await signal_processor.process_signal(
        signal=signal,
        user=mock_user_with_config,
    )

    # Verify rejection
    assert result.status == "rejected"

    # Verify DEX adapter was NOT called
    mock_dex_adapter.execute_order.assert_not_called()
```

### Database JSON Field Patterns

**Pattern for updating JSON fields (from existing code):**
```python
# SQLAlchemy async pattern for JSON field update
from sqlalchemy import update

# 1. Read current config
query = select(UserModel).where(UserModel.id == user_id)
result = await session.execute(query)
user = result.scalar_one()

# 2. Update config dict
config = dict(user.config_data) if user.config_data else {}
config["position_size"] = str(new_value)

# 3. Write back
stmt = update(UserModel).where(UserModel.id == user_id).values(config_data=config)
await session.execute(stmt)
await session.commit()
```

### Previous Story Intelligence

**From Story 5.5 (Onboarding Checklist):**
- Uses same auth dependency pattern: `Depends(get_current_user)`
- Same database session pattern: `Depends(get_db_session)`
- JSON parsing pattern for `config_data` field
- Test patterns with authenticated_headers fixture

**From Story 5.4 (Dashboard Endpoint):**
- Router structure pattern in `api/stats.py`
- Response model patterns in `models.py`
- Integration with main.py router registration

**From Story 2.2 (User Session Management):**
- User model with `config_data` JSON field structure
- Session creation and user lookup patterns

### Git Commit Patterns

Recent commits follow naming convention:
- `Story 5.1: Stats Service & Volume Tracking - Implementation Complete`
- `Story 4.5: Error Log Viewer - Implementation Complete`

**Follow same pattern for this story's commits.**

### Error Handling

- Return 401 if not authenticated (handled by `get_current_user` dependency)
- Return 404 if user not found in database (shouldn't happen but handle gracefully)
- Return 400 for cross-validation failures with detailed error info
- Return 422 for Pydantic validation failures (automatic)
- Signal processor returns rejection result (doesn't raise exception)

### Performance Considerations

- Config reads are fast (single user query)
- Position size check in signal processor is lightweight
- No caching needed (infrequent updates, must be accurate)
- Consider caching user config in signal processor if processing many signals

### Security Considerations

- Users can only access/modify their own config (auth dependency)
- System maximum prevents configuration of dangerously large positions
- Position size values stored as strings to preserve precision
- No sensitive data in config (just trading preferences)

### Project Structure Notes

**Files to Create:**
- `src/kitkat/api/config.py` - New configuration API router

**Files to Modify:**
- `src/kitkat/models.py` - Add PositionSizeConfig, PositionSizeUpdate models
- `src/kitkat/main.py` - Register config router
- `src/kitkat/services/signal_processor.py` - Add size validation check

**Test Files to Create:**
- `tests/api/test_config.py` - Configuration endpoint tests

**Test Files to Modify:**
- `tests/services/test_signal_processor.py` - Add size rejection tests

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.6]
- [Source: _bmad-output/planning-artifacts/prd.md#FR44] - Configure position size per trade
- [Source: _bmad-output/planning-artifacts/prd.md#FR45] - Configure maximum position size limit
- [Source: _bmad-output/planning-artifacts/architecture.md] - Component patterns
- [Source: _bmad-output/project-context.md] - Naming conventions, async patterns, error codes
- [Source: src/kitkat/api/stats.py] - Router patterns to follow
- [Source: src/kitkat/models.py] - Model definitions to extend
- [Source: src/kitkat/database.py] - UserModel with config_data field
- [Source: src/kitkat/services/signal_processor.py] - Signal processing flow

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No significant debugging issues encountered.

### Completion Notes List

- Tasks 1-4, 6 were already implemented prior to this session
- Task 5 (position size validation in SignalProcessor) implemented with:
  - Added `max_position_size` parameter to `SignalProcessor.process_signal()`
  - Added "rejected" status to `SignalProcessorResponse.overall_status` and `DEXExecutionResult.status`
  - Webhook handler extracts user's max_position_size from config and passes to signal processor
  - Signals exceeding limit are rejected without executing on any DEX adapter
- Task 7 (comprehensive tests) implemented with 17 new tests in:
  - `tests/api/test_config.py` (12 tests for config API)
  - `tests/services/test_signal_processor.py` (5 tests for position size validation)
- All 38 tests in config and signal_processor test files pass

### File List

**New Files:**
- `tests/api/test_config.py` - Configuration API endpoint tests

**Modified Files:**
- `src/kitkat/api/config.py` - Position size configuration endpoints (GET/PUT /api/config)
- `src/kitkat/models.py` - Added "rejected" status to DEXExecutionResult and SignalProcessorResponse
- `src/kitkat/services/signal_processor.py` - Added max_position_size validation
- `src/kitkat/api/webhook.py` - Extract user max_position_size and pass to signal processor
- `tests/conftest.py` - Added async_client and authenticated_user fixtures
- `tests/services/test_signal_processor.py` - Added position size validation tests

### Change Log

- 2026-02-04: **Code Review PASSED** - Minor issues fixed:
  - M1: Added boundary test for position_size == max_position_size
  - L1: Updated File List to include src/kitkat/api/config.py
- 2026-02-02: Story 5.6 implementation completed - Position size configuration with validation

