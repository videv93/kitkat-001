---
project_name: 'kitkat-001'
user_name: 'vitr'
date: '2026-01-18'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'code_quality', 'workflow_rules', 'critical_rules']
status: 'complete'
rule_count: 47
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

**Runtime:** Python 3.11+ (native asyncio required)

**Package Manager:** uv (NOT pip)

**Core Stack:**
- FastAPI + uvicorn[standard] - ASGI server
- Pydantic V2 - use `ConfigDict`, NOT `class Config`
- SQLAlchemy async + aiosqlite - SQLite with WAL mode
- httpx - async HTTP (NOT requests)
- websockets - WebSocket client
- structlog - structured logging
- tenacity - retry with backoff

**Dev Tools:**
- ruff - linting AND formatting (single tool)
- pytest + pytest-asyncio - async tests
- pytest-httpx - HTTP mocking

**Critical Version Notes:**
- Pydantic V2 syntax required (model_config = ConfigDict(...))
- SQLite MUST use WAL mode for concurrent writes
- NEVER use blocking `requests` library - always `httpx`

## Language-Specific Rules (Python)

### Async Patterns (CRITICAL)
- ALL I/O must be async - no blocking calls
- Parallel execution: `await asyncio.gather(*tasks, return_exceptions=True)`
- Fire-and-forget: `asyncio.create_task(alert_service.send(...))`
- Handle gather results: check `isinstance(result, Exception)` for each

### Import Rules
- ONLY absolute imports: `from kitkat.services.signal_processor import SignalProcessor`
- NEVER relative imports across packages: `from ..adapters` is FORBIDDEN
- Relative imports OK within same package: `from .base import DEXAdapter`

### Type Hints
- Required on all functions and methods
- Use `Literal["buy", "sell"]` for constrained string values
- Use `Decimal` for money/size values (NOT float)
- Use Pydantic models for all external data

### Error Handling
- Network/timeout errors → retry with backoff (max 3)
- Business errors (4xx, validation) → fail immediately, no retry
- Always bind context before logging: `log = logger.bind(signal_id=x)`

## Framework-Specific Rules (FastAPI + Adapters)

### FastAPI Patterns
- ALL request/response data uses Pydantic models (no raw dicts)
- Dependencies live in `api/deps.py` (auth, db session)
- Use `Depends()` for injection, not manual instantiation
- Return appropriate HTTP codes per error type (see Error Codes)

### API Naming Convention
- Endpoints: `snake_case`, plural → `/api/executions`, `/api/signals`
- Path params: `snake_case` → `/api/executions/{execution_id}`
- Query params: `snake_case` → `?dex_id=extended`
- JSON fields: `snake_case` → `{"signal_id": "abc", "dex_id": "extended"}`
- Custom headers: `X-Custom-Name` → `X-Webhook-Token`

### DEX Adapter Pattern (CRITICAL)
- ALL adapters MUST extend `DEXAdapter` ABC from `adapters/base.py`
- Required methods: `dex_id`, `execute_order`, `get_status`, `connect`, `disconnect`
- MockAdapter must have 100% behavior parity with real adapters
- Test mode routes to MockAdapter via feature flag in SignalProcessor

### Error Response Format
```json
{
  "error": "DEX timeout",
  "code": "DEX_TIMEOUT",
  "signal_id": "abc123",
  "dex": "extended",
  "timestamp": "2026-01-18T10:30:00Z"
}
```

## Testing Rules

### Test Organization
- Mirror source structure: `tests/adapters/`, `tests/services/`, `tests/api/`
- Integration tests: `tests/integration/`
- Shared fixtures: `tests/conftest.py` + `tests/fixtures/`

### Async Test Patterns
- ALL async tests use `pytest-asyncio`
- Mark async tests: `@pytest.mark.asyncio`
- Use `pytest-httpx` for HTTP mocking (NOT `responses` or `aioresponses`)

### Mock Strategy
- Mock at boundaries: DEX APIs, Telegram API, external HTTP
- DO NOT mock internal services in unit tests
- Fixtures for sample data: `tests/fixtures/signals.py`, `tests/fixtures/dex_responses.py`

### Test Boundaries
| Test Type | Scope | Mocks |
|-----------|-------|-------|
| Unit | Single class/function | External APIs |
| Integration | Webhook → Execution | None (uses MockAdapter) |

### Coverage Expectations
- Adapter interface compliance: test ALL methods
- Error paths: test retry behavior, failure modes
- No DEX testnet dependency - use MockAdapter for integration tests

## Code Quality & Style Rules

### Naming Conventions
| Element | Convention | Example |
|---------|------------|---------|
| Files | `snake_case.py` | `signal_processor.py` |
| Classes | `PascalCase` | `SignalProcessor` |
| Functions/Variables | `snake_case` | `process_signal`, `dex_adapter` |
| Constants | `UPPER_SNAKE` | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Private | `_prefix` | `_cleanup()`, `_seen` |

### Database Naming
| Element | Convention | Example |
|---------|------------|---------|
| Tables | `snake_case`, plural | `executions`, `signals` |
| Columns | `snake_case` | `wallet_address`, `created_at` |
| Primary keys | `id` | `id: int` |
| Foreign keys | `{table}_id` | `signal_id`, `user_id` |
| JSON columns | `_data` suffix | `config_data`, `result_data` |
| Indexes | `ix_{table}_{column}` | `ix_executions_signal_id` |

### Linting & Formatting
- Use `ruff` for BOTH linting AND formatting
- Run: `ruff check src/ tests/` and `ruff format src/ tests/`
- NO other tools (Black, isort, flake8) - ruff handles all

### Logging Standards
- Use `structlog.get_logger()` everywhere
- Bind context once at request start: `log = logger.bind(signal_id=signal.id)`
- All subsequent logs in that request auto-include signal_id

## Development Workflow Rules

### Project Structure
```
src/kitkat/           # All source code
├── adapters/         # DEX adapter implementations
├── api/              # FastAPI routes (webhook, health, status)
├── services/         # Business logic (SignalProcessor, AlertService)
├── models.py         # SQLAlchemy models + Pydantic schemas
├── config.py         # Pydantic Settings class
├── database.py       # Engine, session, WAL setup
└── main.py           # FastAPI app entry point
tests/                # Mirrors src/ structure
```

### Development Commands
```bash
# Start dev server
uvicorn kitkat.main:app --reload

# Run tests
pytest
pytest --cov=kitkat        # with coverage
pytest tests/adapters/     # specific directory

# Lint and format
ruff check src/ tests/
ruff format src/ tests/
```

### Configuration Management
- Use Pydantic `BaseSettings` in `config.py`
- Load from `.env` file via `python-dotenv`
- Provide `.env.example` with all required vars (no real values)
- NEVER commit `.env` - must be in `.gitignore`

### Files to Gitignore
```
.env
*.db
__pycache__/
.ruff_cache/
.pytest_cache/
*.pyc
```

## Critical Don't-Miss Rules

### Anti-Patterns (NEVER DO THIS)

| Anti-Pattern | Correct Pattern |
|--------------|-----------------|
| `userId`, `signalID` | `user_id`, `signal_id` |
| `class signalProcessor` | `class SignalProcessor` |
| `await asyncio.gather(*tasks)` | `await asyncio.gather(*tasks, return_exceptions=True)` |
| Blocking `requests.post()` | Async `httpx.AsyncClient()` |
| `logger.info("x", signal_id=y)` repeated | `log = logger.bind(signal_id=y)` once |
| Raw dict responses | Pydantic response models |
| `from ..adapters import` | `from kitkat.adapters import` |
| Pydantic `class Config:` | `model_config = ConfigDict(...)` |

### Security Rules (CRITICAL)
- NEVER store private keys - users sign via their wallets
- NEVER log secrets, API keys, or tokens
- Use `secrets.compare_digest()` for token comparison (timing-safe)
- Return generic 401 on auth failure - no error details

### Error Code Reference
| Code | HTTP | Retry? | When |
|------|------|--------|------|
| `INVALID_SIGNAL` | 400 | No | Malformed payload |
| `INVALID_TOKEN` | 401 | No | Auth failed |
| `DUPLICATE_SIGNAL` | 200 | N/A | Already processed (idempotent) |
| `DEX_TIMEOUT` | 504 | Yes | DEX didn't respond |
| `DEX_ERROR` | 502 | Yes | DEX returned 5xx |
| `DEX_REJECTED` | 400 | No | DEX rejected order |
| `INSUFFICIENT_FUNDS` | 400 | No | Balance too low |

### Edge Case Handling
- **Duplicate signals:** Return 200 OK, log as duplicate, do NOT re-execute
- **DEX timeout:** Retry 3x with backoff, then alert via Telegram and fail
- **Partial fills:** Log fill amount and remaining, alert user, continue tracking
- **WebSocket disconnect:** Auto-reconnect with exponential backoff + jitter
- **Shutdown during execution:** Complete in-flight orders before exit

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code
- Follow ALL rules exactly as documented
- When in doubt, prefer the more restrictive option
- Update this file if new patterns emerge

**For Humans:**
- Keep this file lean and focused on agent needs
- Update when technology stack changes
- Review quarterly for outdated rules
- Remove rules that become obvious over time

_Last Updated: 2026-01-18_
