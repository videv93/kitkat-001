---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
status: complete
validated: 2026-01-19
total_epics: 5
total_stories: 33
fr_coverage: 48/48
inputDocuments:
  - '_bmad-output/planning-artifacts/prd.md'
  - '_bmad-output/planning-artifacts/architecture.md'
---

# kitkat-001 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for kitkat-001, decomposing the requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

**Signal Reception (FR1-9):**
- FR1: System can receive webhook POST requests from TradingView
- FR2: System can parse JSON payload from webhook request
- FR3: System can validate JSON structure against expected schema
- FR4: System can validate business rules (valid side, symbol, size values)
- FR5: System can reject invalid payloads with descriptive error messages
- FR6: System can authenticate webhook requests via secret token in URL
- FR7: System can rate-limit webhook requests per user (10/minute)
- FR8: System can detect and reject duplicate signals within 5-second window
- FR9: System can track processed webhook IDs to prevent duplicate execution beyond 5-second window

**Order Execution (FR10-17):**
- FR10: System can submit long orders to Extended DEX
- FR11: System can submit short orders to Extended DEX
- FR12: System can receive execution confirmation from DEX
- FR13: System can retry failed orders with exponential backoff (3 attempts)
- FR14: System can log partial fill events with fill amount and remaining
- FR15: System can alert user on partial fill scenarios
- FR16: System can log all execution attempts with timestamps and responses
- FR17: System can complete in-flight orders before shutdown

**User Authentication (FR18-25):**
- FR18: User can create account by connecting wallet
- FR19: User can connect wallet (MetaMask) to kitkat-001
- FR20: User can sign delegation authority message for Extended DEX
- FR21: System can verify wallet signature matches expected wallet
- FR22: User can disconnect wallet and revoke delegation
- FR23: System can display clear explanation of what signature grants
- FR24: System can maintain user session after authentication
- FR25: System can generate unique webhook URL per user

**System Monitoring (FR26-30):**
- FR26: System can display health status per DEX (healthy/degraded/offline)
- FR27: System can send error alerts to Telegram on execution failure
- FR28: System can auto-recover DEX connection after outage via periodic health check
- FR29: System can log errors with full context (payload, DEX response, timestamps)
- FR30: User can view error log entries (last 50 entries or last 24 hours)

**Dashboard & Status (FR31-33):**
- FR31: User can view dashboard with system status and stats
- FR32: System can display "everything OK" indicator when all DEXs healthy and no recent errors
- FR33: System can display onboarding checklist with completion status

**Volume & Statistics (FR34-38):**
- FR34: System can track total volume executed per DEX
- FR35: System can display today's volume total
- FR36: System can display this week's volume total
- FR37: System can display execution count (signals processed)
- FR38: System can display success rate percentage

**Test Mode (FR39-43):**
- FR39: User can enable test/dry-run mode
- FR40: System can process webhooks in test mode without submitting to DEX
- FR41: System can display "would have executed" details in test mode
- FR42: Test mode can validate full flow including payload parsing and business rules
- FR43: User can disable test mode to go live

**Configuration (FR44-48):**
- FR44: User can configure position size per trade
- FR45: User can configure maximum position size limit
- FR46: User can view their unique webhook URL
- FR47: User can view expected webhook payload format
- FR48: User can configure Telegram alert destination

### NonFunctional Requirements

**Performance (NFR1-5):**
- NFR1: Webhook-to-DEX-submission latency < 1 second (95th percentile)
- NFR2: Dashboard page load time < 2 seconds
- NFR3: Webhook endpoint response time < 200ms (acknowledgment)
- NFR4: Health check interval every 30 seconds
- NFR5: DEX reconnection time after detected failure < 30 seconds

**Security (NFR6-11):**
- NFR6: All API traffic encrypted (HTTPS/TLS 1.2+ only)
- NFR7: DEX API credentials storage encrypted at rest (secrets manager or encrypted env)
- NFR8: Webhook URL entropy minimum 128-bit secret token
- NFR9: Session token expiration 24 hours max, refresh on activity
- NFR10: Audit log immutability - append-only, no deletion capability
- NFR11: No private key storage - System never stores user private keys

**Reliability (NFR12-16):**
- NFR12: System uptime 99.9% (excluding scheduled maintenance)
- NFR13: DEX connection recovery automatic within 30 seconds of detection
- NFR14: Data durability - No loss of execution logs or volume stats
- NFR15: Graceful degradation - Continue on healthy DEXs if one fails
- NFR16: Error alerting latency < 30 seconds from failure to Telegram notification

**Integration (NFR17-20):**
- NFR17: DEX API compatibility - Support HTTP REST + WebSocket protocols
- NFR18: Webhook payload format - JSON with documented schema
- NFR19: Telegram API integration - Standard Bot API
- NFR20: Rate limit compliance - Respect DEX API rate limits per documentation

**Scalability (NFR21-23):**
- NFR21: Concurrent users supported - 10 users minimum at launch
- NFR22: Concurrent webhook processing - 10 simultaneous requests without degradation
- NFR23: Growth headroom - Architecture supports 100 users without redesign

### Additional Requirements

**From Architecture Document:**

1. **Starter Template (CRITICAL - Epic 1 Story 1)**: Initialize project using bare Python + uv + curated libraries (FastAPI, SQLAlchemy async, Pydantic, httpx, websockets, structlog, tenacity, python-telegram-bot)

2. **Database Architecture**: SQLite + WAL mode with SQLAlchemy async for concurrent write safety

3. **Project Structure**: Layered architecture following defined boundaries:
   - API Layer: webhook.py, health.py, status.py, deps.py
   - Service Layer: signal_processor.py, deduplicator.py, alert.py, health.py, stats.py
   - Adapter Layer: base.py (abstract), extended.py, mock.py
   - Data Layer: database.py, models.py

4. **DEX Adapter Interface Contract**:
   - `connect(wallet_signature) → ConnectionStatus`
   - `disconnect() → void`
   - `execute_order(symbol, side, size, order_type) → OrderResult`
   - `get_position(symbol) → Position | null`
   - `get_order_status(order_id) → OrderStatus`
   - `subscribe_order_updates(callback) → Subscription`
   - `health_check() → HealthStatus`

5. **Test Mode Architecture**: Feature flag with MockAdapter injection for 100% production parity

6. **Signal Deduplication**: In-memory with 60-second TTL using SHA256 hash

7. **Parallel Fan-Out Execution**: asyncio.gather() for simultaneous DEX execution with return_exceptions=True

8. **Webhook Authentication**: X-Webhook-Token header with constant-time comparison

9. **Error Response Format**: JSON with signal_id, dex, timestamp, code fields

10. **WebSocket Reconnection**: Exponential backoff with jitter using tenacity

11. **Logging Pattern**: structlog with signal_id binding for request correlation

12. **Naming Conventions**: snake_case everywhere except PascalCase for classes, UPPER_SNAKE for constants

13. **Async Patterns**: Use asyncio.gather() for parallel, asyncio.create_task() for fire-and-forget

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 1 | Receive webhook POST from TradingView |
| FR2 | Epic 1 | Parse JSON payload |
| FR3 | Epic 1 | Validate JSON structure |
| FR4 | Epic 1 | Validate business rules |
| FR5 | Epic 1 | Reject invalid payloads |
| FR6 | Epic 1 | Authenticate via secret token |
| FR7 | Epic 1 | Rate-limit requests |
| FR8 | Epic 1 | Detect duplicate signals |
| FR9 | Epic 1 | Track processed webhook IDs |
| FR10 | Epic 2 | Submit long orders to Extended |
| FR11 | Epic 2 | Submit short orders to Extended |
| FR12 | Epic 2 | Receive execution confirmation |
| FR13 | Epic 2 | Retry with exponential backoff |
| FR14 | Epic 2 | Log partial fills |
| FR15 | Epic 2 | Alert on partial fills |
| FR16 | Epic 2 | Log all execution attempts |
| FR17 | Epic 2 | Complete in-flight orders on shutdown |
| FR18 | Epic 2 | Create account by connecting wallet |
| FR19 | Epic 2 | Connect MetaMask wallet |
| FR20 | Epic 2 | Sign delegation authority |
| FR21 | Epic 2 | Verify wallet signature |
| FR22 | Epic 2 | Disconnect and revoke delegation |
| FR23 | Epic 2 | Display signature explanation |
| FR24 | Epic 2 | Maintain user session |
| FR25 | Epic 2 | Generate unique webhook URL |
| FR26 | Epic 4 | Display DEX health status |
| FR27 | Epic 4 | Send Telegram error alerts |
| FR28 | Epic 4 | Auto-recover after outage |
| FR29 | Epic 4 | Log errors with full context |
| FR30 | Epic 4 | View error log entries |
| FR31 | Epic 5 | View dashboard |
| FR32 | Epic 5 | Display "everything OK" indicator |
| FR33 | Epic 5 | Display onboarding checklist |
| FR34 | Epic 5 | Track volume per DEX |
| FR35 | Epic 5 | Display today's volume |
| FR36 | Epic 5 | Display week's volume |
| FR37 | Epic 5 | Display execution count |
| FR38 | Epic 5 | Display success rate |
| FR39 | Epic 3 | Enable test mode |
| FR40 | Epic 3 | Process webhooks without DEX submission |
| FR41 | Epic 3 | Display "would have executed" |
| FR42 | Epic 3 | Validate full flow in test mode |
| FR43 | Epic 3 | Disable test mode |
| FR44 | Epic 5 | Configure position size |
| FR45 | Epic 5 | Configure max position limit |
| FR46 | Epic 5 | View webhook URL |
| FR47 | Epic 5 | View payload format |
| FR48 | Epic 5 | Configure Telegram destination |

**Coverage:** 48/48 FRs mapped (100%)

## Epic List

### Epic 1: Project Foundation & Webhook Handler
**User Outcome:** Users can receive and validate TradingView webhook signals with proper authentication and deduplication.

**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8, FR9

**What gets built:**
- Project initialization (uv, FastAPI, SQLAlchemy, structlog)
- Database setup with WAL mode
- Configuration system (Pydantic Settings, .env)
- Webhook endpoint with X-Webhook-Token auth
- JSON payload parsing and business rule validation
- Signal deduplication (in-memory, 60s TTL)
- Rate limiting (10 signals/minute/user)

**Standalone Value:** TradingView can send webhooks, system validates and acknowledges them. Foundation for all future epics.

---

### Epic 2: Extended DEX Integration & Order Execution
**User Outcome:** Users can connect their wallet and execute trades on Extended DEX with proper error handling and retries.

**FRs covered:** FR10, FR11, FR12, FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR20, FR21, FR22, FR23, FR24, FR25

**What gets built:**
- DEX adapter interface (abstract base)
- Extended adapter implementation (HTTP + WebSocket)
- Wallet connection and signature flow
- Order execution (long/short)
- Exponential backoff retry logic
- Partial fill handling and logging
- Graceful shutdown (complete in-flight orders)

**Standalone Value:** Full signal-to-execution flow works. Webhooks trigger real trades on Extended DEX.

---

### Epic 3: Test Mode & Safe Onboarding
**User Outcome:** Users can safely validate the entire system without risking real funds, building confidence before going live.

**FRs covered:** FR39, FR40, FR41, FR42, FR43

**What gets built:**
- Test mode feature flag
- MockAdapter (100% production parity)
- "Would have executed" output
- Full validation flow in test mode
- Toggle to enable/disable test mode

**Standalone Value:** New users can onboard safely. Supports Journey 3 (Marco's first-time experience).

---

### Epic 4: System Monitoring & Alerting
**User Outcome:** Users get real-time notifications when things fail and can see DEX health status at a glance.

**FRs covered:** FR26, FR27, FR28, FR29, FR30

**What gets built:**
- Health service (component status aggregation)
- Per-DEX health status (healthy/degraded/offline)
- Telegram alert service (fire-and-forget async)
- Auto-recovery after DEX outage
- Error logging with full context
- Error log viewer (last 50 entries)

**Standalone Value:** Users trust the system because failures are visible. Supports Journey 2 (troubleshooting).

---

### Epic 5: Dashboard, Volume Stats & Configuration
**User Outcome:** Users can view their execution stats, configure position sizes, and get a "glance-and-go" status check.

**FRs covered:** FR31, FR32, FR33, FR34, FR35, FR36, FR37, FR38, FR44, FR45, FR46, FR47, FR48

**What gets built:**
- Dashboard endpoint with system status
- "Everything OK" indicator
- Onboarding checklist
- Volume tracking per DEX (today/week totals)
- Execution count and success rate
- Position size configuration
- Webhook URL and payload format display
- Telegram destination configuration

**Standalone Value:** Users can check status in 30 seconds. Supports Journey 1 (daily operation) and Journey 5 (health check).

---

## Epic Summary

| Epic | Title | FRs | User Value |
|------|-------|-----|------------|
| 1 | Project Foundation & Webhook Handler | 9 | Receive & validate TradingView signals |
| 2 | Extended DEX Integration & Order Execution | 16 | Execute real trades on Extended DEX |
| 3 | Test Mode & Safe Onboarding | 5 | Validate system without risking funds |
| 4 | System Monitoring & Alerting | 5 | Get notified of failures, see health |
| 5 | Dashboard, Volume Stats & Configuration | 13 | Glance-and-go status, configure settings |

**Dependencies:**
- Epic 2 builds on Epic 1 (needs webhook handler)
- Epic 3 builds on Epic 1 & 2 (needs adapters to mock)
- Epic 4 builds on Epic 2 (monitors DEX connections)
- Epic 5 builds on all (aggregates data from all components)

---

## Epic 1: Project Foundation & Webhook Handler

**Goal:** Users can receive and validate TradingView webhook signals with proper authentication and deduplication.

---

### Story 1.1: Project Initialization

As a **developer**,
I want **the project initialized with the correct structure, dependencies, and configuration system**,
So that **I have a solid foundation to build all features upon**.

**Acceptance Criteria:**

**Given** an empty project directory
**When** the initialization script is run
**Then** the following directory structure is created:
- `src/kitkat/` with `adapters/`, `api/`, `services/` subdirectories
- `tests/` with `adapters/`, `services/`, `api/`, `integration/`, `fixtures/` subdirectories
- `__init__.py` files in all Python packages

**Given** the project is initialized
**When** I check the dependencies
**Then** all required packages are installed:
- fastapi, uvicorn[standard], httpx, websockets
- sqlalchemy[asyncio], pydantic, aiosqlite
- python-telegram-bot, structlog, tenacity, python-dotenv, rich
- Dev: pytest, pytest-asyncio, pytest-httpx, pytest-mock, ruff

**Given** the project is initialized
**When** I check for configuration files
**Then** the following exist:
- `pyproject.toml` with project metadata and ruff config
- `.env.example` with all required environment variable placeholders
- `.gitignore` excluding `.env`, `*.db`, `__pycache__/`, `.ruff_cache/`
- `src/kitkat/config.py` with Pydantic Settings class

**Given** a `.env` file with valid configuration
**When** I import `settings` from `kitkat.config`
**Then** all environment variables are loaded and accessible as typed attributes

---

### Story 1.2: Database Foundation

As a **developer**,
I want **a database layer with SQLite, WAL mode, and async session management**,
So that **I can persist data with concurrent write safety**.

**Acceptance Criteria:**

**Given** the application starts
**When** the database engine is initialized
**Then** SQLite is configured with WAL mode enabled via `PRAGMA journal_mode=WAL`

**Given** the database module
**When** I request a database session
**Then** an async SQLAlchemy session is provided via dependency injection

**Given** the `Signal` model is defined
**When** the application starts
**Then** the `signals` table is created with columns:
- `id` (primary key)
- `signal_id` (unique hash, indexed)
- `payload` (JSON)
- `received_at` (datetime)
- `processed` (boolean)

**Given** the database is running
**When** multiple concurrent writes occur
**Then** all writes succeed without "database is locked" errors (WAL mode working)

---

### Story 1.3: Webhook Endpoint with Authentication

As a **TradingView user**,
I want **to send webhook signals to a secure endpoint**,
So that **only authorized requests are processed**.

**Acceptance Criteria:**

**Given** the FastAPI application is running
**When** I send a POST request to `/api/webhook`
**Then** the endpoint accepts the request and returns a response

**Given** a valid `X-Webhook-Token` header matching the configured token
**When** I send a POST request to `/api/webhook`
**Then** the request is accepted with status 200

**Given** an invalid or missing `X-Webhook-Token` header
**When** I send a POST request to `/api/webhook`
**Then** the request is rejected with status 401
**And** the response contains `{"error": "Invalid token", "code": "INVALID_TOKEN"}`

**Given** authentication is performed
**When** comparing tokens
**Then** constant-time comparison is used to prevent timing attacks

**Given** the webhook endpoint
**When** I check the API documentation
**Then** the endpoint is documented at `/docs` with request/response schemas

---

### Story 1.4: Signal Payload Parsing & Validation

As a **TradingView user**,
I want **my webhook payloads validated for correct structure and business rules**,
So that **only valid signals are processed and I get clear error messages for invalid ones**.

**Acceptance Criteria:**

**Given** a valid JSON payload with required fields: `symbol`, `side`, `size`
**When** I send it to `/api/webhook`
**Then** the payload is parsed successfully
**And** the response includes `{"status": "received", "signal_id": "<hash>"}`

**Given** a malformed JSON payload (invalid JSON syntax)
**When** I send it to `/api/webhook`
**Then** the request is rejected with status 400
**And** the response contains `{"error": "Invalid JSON", "code": "INVALID_SIGNAL"}`

**Given** a JSON payload missing required fields
**When** I send it to `/api/webhook`
**Then** the request is rejected with status 400
**And** the response contains `{"error": "Missing required field: <field>", "code": "INVALID_SIGNAL"}`

**Given** a JSON payload with invalid `side` value (not "buy" or "sell")
**When** I send it to `/api/webhook`
**Then** the request is rejected with status 400
**And** the response contains `{"error": "Invalid side value", "code": "INVALID_SIGNAL"}`

**Given** a JSON payload with invalid `size` value (zero or negative)
**When** I send it to `/api/webhook`
**Then** the request is rejected with status 400
**And** the response contains `{"error": "Size must be positive", "code": "INVALID_SIGNAL"}`

**Given** any validation error
**When** the error response is generated
**Then** the raw payload is logged for debugging with structlog

---

### Story 1.5: Signal Deduplication

As a **TradingView user**,
I want **duplicate signals detected and rejected**,
So that **the same trade is not executed multiple times**.

**Acceptance Criteria:**

**Given** a valid signal payload
**When** it is received for the first time
**Then** a unique `signal_id` hash is generated using SHA256(payload + timestamp_minute)
**And** the signal is marked as seen in the deduplicator
**And** the request returns status 200 with `{"status": "received"}`

**Given** an identical signal payload within 60 seconds
**When** it is received again
**Then** the signal is identified as a duplicate
**And** the request returns status 200 with `{"status": "duplicate", "code": "DUPLICATE_SIGNAL"}`
**And** no further processing occurs

**Given** the deduplicator has stored signal hashes
**When** 60 seconds have passed since a signal was seen
**Then** that signal hash is cleaned up from memory
**And** the same payload can be processed again

**Given** the deduplicator
**When** I check memory usage
**Then** old entries are automatically cleaned up to prevent memory leaks

---

### Story 1.6: Rate Limiting

As a **system operator**,
I want **webhook requests rate-limited per user**,
So that **the system is protected from abuse and overload**.

**Acceptance Criteria:**

**Given** a user with a valid webhook token
**When** they send up to 10 signals within 1 minute
**Then** all signals are accepted and processed normally

**Given** a user with a valid webhook token
**When** they send more than 10 signals within 1 minute
**Then** the 11th+ signals are rejected with status 429
**And** the response contains `{"error": "Rate limit exceeded", "code": "RATE_LIMITED"}`
**And** a `Retry-After` header indicates when they can retry

**Given** a rate-limited user
**When** the rate limit window resets (after 1 minute)
**Then** the user can send signals again normally

**Given** the rate limiter
**When** tracking request counts
**Then** counts are tracked per webhook token (user isolation)

---

## Epic 2: Extended DEX Integration & Order Execution

**Goal:** Users can connect their wallet and execute trades on Extended DEX with proper error handling and retries.

---

### Story 2.1: DEX Adapter Interface

As a **developer**,
I want **an abstract base class defining the DEX adapter contract**,
So that **all DEX implementations follow a consistent interface and can be swapped easily**.

**Acceptance Criteria:**

**Given** the adapter module
**When** I check `adapters/base.py`
**Then** an abstract `DEXAdapter` class exists with the following methods:
- `dex_id` property returning unique identifier
- `async connect() -> None`
- `async disconnect() -> None`
- `async execute_order(symbol, side, size) -> OrderResult`
- `async get_position(symbol) -> Position | None`
- `async get_order_status(order_id) -> OrderStatus`
- `async health_check() -> HealthStatus`

**Given** the `DEXAdapter` abstract class
**When** I try to instantiate it directly
**Then** a `TypeError` is raised (abstract class cannot be instantiated)

**Given** a class that inherits from `DEXAdapter`
**When** it doesn't implement all abstract methods
**Then** a `TypeError` is raised at instantiation

**Given** the adapter interface
**When** I check the type definitions
**Then** `OrderResult`, `Position`, `OrderStatus`, and `HealthStatus` are defined as Pydantic models in `models.py`

---

### Story 2.2: User & Session Management

As a **system operator**,
I want **user accounts and session management**,
So that **users can authenticate and maintain persistent sessions**.

**Acceptance Criteria:**

**Given** the database models
**When** I check for user-related tables
**Then** a `users` table exists with columns:
- `id` (primary key)
- `wallet_address` (unique, indexed)
- `config_data` (JSON for user preferences)
- `created_at` (datetime)

**Given** the database models
**When** I check for session-related tables
**Then** a `sessions` table exists with columns:
- `id` (primary key)
- `token` (unique, 128-bit random)
- `wallet_address` (foreign key to users)
- `created_at` (datetime)
- `expires_at` (datetime, 24h from creation)
- `last_used` (datetime)

**Given** a valid session token
**When** I make an authenticated request
**Then** the `last_used` timestamp is updated

**Given** a session token past its `expires_at`
**When** I try to authenticate
**Then** the request is rejected with 401
**And** the expired session is cleaned up

---

### Story 2.3: Wallet Connection & Signature

As a **user**,
I want **to connect my MetaMask wallet and sign delegation authority**,
So that **kitkat-001 can execute trades on my behalf without holding my private keys**.

**Acceptance Criteria:**

**Given** a user wants to connect their wallet
**When** they access the connection endpoint
**Then** a clear explanation is displayed: "This grants kitkat-001 delegated trading authority on Extended DEX. Your private keys are never stored."

**Given** a user initiates wallet connection
**When** the connection flow starts
**Then** a challenge message is generated for the user to sign

**Given** a user signs the delegation message with MetaMask
**When** the signature is submitted
**Then** the system verifies the signature matches the expected wallet address
**And** the wallet address is stored in the `users` table
**And** a new session token is generated and returned

**Given** an invalid signature is submitted
**When** verification is attempted
**Then** the request is rejected with 401
**And** an error message explains the signature mismatch

**Given** a connected wallet
**When** I query the user's status
**Then** the wallet address is shown (abbreviated: `0x1234...5678`)
**And** the connection status shows "Connected"

---

### Story 2.4: Webhook URL Generation

As a **user**,
I want **a unique webhook URL generated for my account**,
So that **my TradingView alerts are routed to my specific configuration**.

**Acceptance Criteria:**

**Given** a newly registered user
**When** their account is created
**Then** a unique webhook token (128-bit random) is generated
**And** stored in `users.config_data` as `webhook_token`

**Given** a user's webhook token
**When** they request their webhook URL
**Then** the URL is returned in format: `https://{host}/api/webhook?token={webhook_token}`

**Given** a webhook request with `?token=` parameter
**When** the token matches a user's `webhook_token`
**Then** the request is associated with that user
**And** processed using their configuration

**Given** a webhook request with invalid or missing token parameter
**When** validation occurs
**Then** the request is rejected with 401

---

### Story 2.5: Extended Adapter - Connection

As a **system**,
I want **to establish and maintain connections to Extended DEX**,
So that **orders can be submitted and status updates received**.

**Acceptance Criteria:**

**Given** the Extended adapter is initialized
**When** `connect()` is called with valid credentials
**Then** an HTTP session is established for REST API calls
**And** a WebSocket connection is established for real-time updates
**And** the adapter status becomes "connected"

**Given** the Extended adapter
**When** connection fails (network error, invalid credentials)
**Then** a `ConnectionError` is raised with descriptive message
**And** the error is logged with full context

**Given** an active WebSocket connection
**When** a heartbeat ping is missed
**Then** reconnection is attempted automatically
**And** exponential backoff with jitter is applied (1s → 2s → 4s → max 30s)

**Given** the adapter's `health_check()` method
**When** called
**Then** it returns `HealthStatus` with:
- `status`: "healthy" | "degraded" | "offline"
- `latency_ms`: last response time
- `last_checked`: timestamp

---

### Story 2.6: Extended Adapter - Order Execution

As a **user**,
I want **to execute long and short orders on Extended DEX**,
So that **my TradingView signals result in actual trades**.

**Acceptance Criteria:**

**Given** a valid signal with `side: "buy"` (long)
**When** `execute_order(symbol, "buy", size)` is called
**Then** a long order is submitted to Extended DEX API
**And** the order ID is returned in `OrderResult`

**Given** a valid signal with `side: "sell"` (short)
**When** `execute_order(symbol, "sell", size)` is called
**Then** a short order is submitted to Extended DEX API
**And** the order ID is returned in `OrderResult`

**Given** an order is submitted successfully
**When** the DEX confirms execution
**Then** `OrderResult` contains:
- `order_id`: DEX-assigned identifier
- `status`: "filled" | "partial" | "pending"
- `filled_size`: amount executed
- `fill_price`: execution price
- `timestamp`: execution time

**Given** the DEX rejects an order (insufficient funds, invalid symbol)
**When** the rejection is received
**Then** `OrderResult.status` is "rejected"
**And** `OrderResult.error` contains the rejection reason
**And** no retry is attempted (business error)

---

### Story 2.7: Retry Logic with Exponential Backoff

As a **system**,
I want **transient failures retried with exponential backoff**,
So that **temporary network issues don't cause permanent failures**.

**Acceptance Criteria:**

**Given** an order submission fails with a timeout
**When** the retry logic activates
**Then** up to 3 retry attempts are made
**And** delays follow exponential backoff: 1s, 2s, 4s

**Given** an order submission fails with HTTP 5xx
**When** the retry logic activates
**Then** retries are attempted with backoff
**And** each attempt is logged with attempt number

**Given** an order submission fails with HTTP 4xx (client error)
**When** the error is received
**Then** no retry is attempted (business error, not transient)
**And** the error is returned immediately

**Given** all 3 retry attempts fail
**When** retries are exhausted
**Then** the final error is returned
**And** an alert is triggered (will be handled in Epic 4)

**Given** the retry mechanism
**When** I check the implementation
**Then** tenacity library is used with `@retry` decorator
**And** jitter is applied to prevent thundering herd

---

### Story 2.8: Execution Logging & Partial Fills

As a **user**,
I want **all execution attempts logged and partial fills handled**,
So that **I have full visibility into what happened with my orders**.

**Acceptance Criteria:**

**Given** any order execution attempt
**When** it occurs
**Then** an `executions` table record is created with:
- `id` (primary key)
- `signal_id` (foreign key)
- `dex_id` ("extended")
- `status` ("pending" | "filled" | "partial" | "failed")
- `result_data` (JSON with full DEX response)
- `created_at` (timestamp)

**Given** a partial fill occurs
**When** the DEX reports partial execution
**Then** `status` is set to "partial"
**And** `result_data` includes `filled_size` and `remaining_size`
**And** the partial fill is logged with structlog

**Given** a partial fill occurs
**When** it is detected
**Then** an alert is queued for the user (FR15)
**And** the alert includes: symbol, filled amount, remaining amount

**Given** any execution (success or failure)
**When** logging occurs
**Then** the log includes: `signal_id`, `dex_id`, `order_id`, `status`, `latency_ms`, `timestamp`

---

### Story 2.9: Signal Processor & Fan-Out

As a **system**,
I want **validated signals routed to all configured DEX adapters in parallel**,
So that **trades execute simultaneously across exchanges**.

**Acceptance Criteria:**

**Given** a validated signal from the webhook handler
**When** it is passed to the Signal Processor
**Then** the processor identifies all active DEX adapters for the user

**Given** multiple DEX adapters are configured (future: Extended + Paradex)
**When** a signal is processed
**Then** `asyncio.gather(*tasks, return_exceptions=True)` executes orders in parallel
**And** each DEX operates independently (one slow DEX doesn't block others)

**Given** parallel execution completes
**When** results are collected
**Then** each result is processed individually
**And** successes are recorded to the database
**And** failures are logged and trigger alerts

**Given** one DEX fails while others succeed
**When** results are aggregated
**Then** the response indicates partial success per DEX
**And** the system continues operating (graceful degradation)

**Given** a signal is processed
**When** the response is returned
**Then** it includes per-DEX status:
```json
{
  "signal_id": "abc123",
  "results": [
    {"dex": "extended", "status": "filled", "order_id": "..."}
  ]
}
```

---

### Story 2.10: Wallet Disconnect & Revocation

As a **user**,
I want **to disconnect my wallet and revoke delegation**,
So that **I can stop kitkat-001 from trading on my behalf**.

**Acceptance Criteria:**

**Given** a connected user
**When** they request wallet disconnection
**Then** their session is invalidated immediately
**And** the session record is deleted from the database

**Given** a user disconnects
**When** the disconnection completes
**Then** no new orders can be submitted for that user
**And** any pending operations complete (in-flight orders finish)

**Given** a disconnected user
**When** they want to reconnect
**Then** they must go through the full wallet connection flow again
**And** a new session is created

**Given** a user's session is invalidated
**When** they try to use the old session token
**Then** the request is rejected with 401

---

### Story 2.11: Graceful Shutdown

As a **system operator**,
I want **in-flight orders completed before shutdown**,
So that **no orders are left in an inconsistent state**.

**Acceptance Criteria:**

**Given** the application receives a shutdown signal (SIGTERM/SIGINT)
**When** shutdown begins
**Then** new webhook requests are rejected with 503 "Service Unavailable"
**And** a shutdown grace period starts (default: 30 seconds)

**Given** there are in-flight orders being processed
**When** shutdown is initiated
**Then** the system waits for all in-flight orders to complete
**And** each completion is logged

**Given** the grace period expires
**When** in-flight orders are still pending
**Then** a warning is logged with details of pending orders
**And** the application shuts down anyway (to not hang indefinitely)

**Given** all in-flight orders complete
**When** before the grace period expires
**Then** the application shuts down immediately
**And** a clean shutdown is logged

**Given** active WebSocket connections
**When** shutdown occurs
**Then** connections are closed gracefully with proper close frames

---

## Epic 3: Test Mode & Safe Onboarding

**Goal:** Users can safely validate the entire system without risking real funds, building confidence before going live.

---

### Story 3.1: Test Mode Feature Flag

As a **user**,
I want **to enable or disable test mode**,
So that **I can safely validate my setup without risking real funds**.

**Acceptance Criteria:**

**Given** the application configuration
**When** I check `config.py`
**Then** a `test_mode` setting exists (boolean, default: `False`)
**And** it can be set via environment variable `TEST_MODE=true`

**Given** test mode is enabled (`TEST_MODE=true`)
**When** the application starts
**Then** a log message indicates "Test mode ENABLED - no real trades will be executed"
**And** the MockAdapter is injected instead of real DEX adapters

**Given** test mode is disabled (`TEST_MODE=false` or not set)
**When** the application starts
**Then** real DEX adapters are used
**And** no test mode warning is logged

**Given** a user wants to toggle test mode
**When** they update the `TEST_MODE` environment variable
**Then** the application must be restarted for the change to take effect
**And** this behavior is documented in `.env.example`

**Given** test mode status
**When** I query the `/api/health` endpoint
**Then** the response includes `"test_mode": true|false`

---

### Story 3.2: Mock DEX Adapter

As a **developer**,
I want **a MockAdapter that simulates DEX behavior with 100% production parity**,
So that **test mode validates the exact same code paths as production**.

**Acceptance Criteria:**

**Given** the MockAdapter class
**When** I check `adapters/mock.py`
**Then** it implements the full `DEXAdapter` interface:
- `dex_id` returns "mock"
- `connect()` simulates successful connection
- `disconnect()` simulates clean disconnect
- `execute_order()` returns simulated `OrderResult`
- `get_position()` returns simulated position
- `health_check()` returns healthy status

**Given** `execute_order()` is called on MockAdapter
**When** with valid parameters
**Then** it returns a successful `OrderResult` with:
- `order_id`: generated mock ID (e.g., "mock-12345")
- `status`: "filled"
- `filled_size`: the requested size
- `fill_price`: simulated price (can be configurable or random within range)
- `timestamp`: current time

**Given** the MockAdapter
**When** processing a signal
**Then** it goes through the exact same code path as real adapters:
- Signal validation
- Deduplication check
- Rate limit check
- Signal processor fan-out
- Execution logging to database

**Given** MockAdapter execution
**When** the result is logged
**Then** the `executions` table record has `dex_id: "mock"`
**And** the execution is indistinguishable from real execution in structure

**Given** the MockAdapter
**When** simulating failures (for testing error paths)
**Then** it can be configured to return specific error types:
- `MOCK_FAIL_RATE` env var (0-100) for random failure percentage
- Default: 0 (always succeed)

---

### Story 3.3: Dry-Run Execution Output

As a **user**,
I want **clear "would have executed" output in test mode**,
So that **I can verify my setup is correct before going live**.

**Acceptance Criteria:**

**Given** test mode is enabled
**When** a valid webhook signal is received
**Then** the response clearly indicates dry-run mode:
```json
{
  "status": "dry_run",
  "signal_id": "abc123",
  "message": "Test mode - no real trade executed",
  "would_have_executed": {
    "dex": "mock",
    "symbol": "ETH-PERP",
    "side": "buy",
    "size": "0.5",
    "simulated_result": {
      "order_id": "mock-12345",
      "status": "filled",
      "fill_price": "2150.00"
    }
  }
}
```

**Given** test mode is enabled
**When** a signal fails validation (bad payload, rate limit, duplicate)
**Then** the error response is identical to production
**And** no special "test mode" indication is added to errors
**And** this validates that error handling works correctly

**Given** test mode execution
**When** logged to the database
**Then** the `executions` record includes `is_test_mode: true` in `result_data`
**And** this allows filtering test executions from real ones

**Given** a user in test mode
**When** they view their execution history
**Then** test executions are clearly marked as "DRY RUN"
**And** they are excluded from volume statistics

**Given** the dashboard (Epic 5)
**When** test mode is active
**Then** a visible banner indicates "TEST MODE ACTIVE - No real trades"

---

## Epic 4: System Monitoring & Alerting

**Goal:** Users get real-time notifications when things fail and can see DEX health status at a glance.

---

### Story 4.1: Health Service & DEX Status

As a **user**,
I want **to see the health status of each DEX at a glance**,
So that **I know if my trades are being executed or if there's an issue**.

**Acceptance Criteria:**

**Given** the health service
**When** I check `services/health.py`
**Then** a `HealthService` class exists that aggregates status from all components

**Given** the health service
**When** `get_system_health()` is called
**Then** it returns a `SystemHealth` object with:
- `status`: "healthy" | "degraded" | "offline"
- `components`: dict of component statuses
- `timestamp`: current time

**Given** each DEX adapter
**When** the health service queries status
**Then** it calls `adapter.health_check()` for each configured adapter
**And** aggregates results into per-DEX status

**Given** a DEX health status
**When** returned
**Then** it includes:
- `dex_id`: "extended" | "mock"
- `status`: "healthy" | "degraded" | "offline"
- `latency_ms`: last measured response time
- `last_successful`: timestamp of last successful operation
- `error_count`: recent errors (last 5 minutes)

**Given** the `/api/health` endpoint
**When** called
**Then** it returns the full system health:
```json
{
  "status": "healthy",
  "test_mode": false,
  "uptime_seconds": 3600,
  "dex_status": {
    "extended": {"status": "healthy", "latency_ms": 45}
  },
  "timestamp": "2026-01-19T10:00:00Z"
}
```

**Given** one DEX is unhealthy but others are healthy
**When** system health is calculated
**Then** overall status is "degraded" (not "offline")

---

### Story 4.2: Telegram Alert Service

As a **user**,
I want **to receive Telegram alerts when executions fail**,
So that **I'm immediately aware of issues even when not watching the dashboard**.

**Acceptance Criteria:**

**Given** the alert service
**When** I check `services/alert.py`
**Then** a `TelegramAlertService` class exists using `python-telegram-bot` library

**Given** Telegram configuration
**When** set in environment
**Then** the following are required:
- `TELEGRAM_BOT_TOKEN`: Bot API token
- `TELEGRAM_CHAT_ID`: Target chat/channel ID

**Given** an execution failure occurs
**When** the alert service is triggered
**Then** a Telegram message is sent with:
- Alert type (e.g., "🚨 Execution Failed")
- Signal ID
- DEX name
- Error message
- Timestamp

**Given** alert sending
**When** implemented
**Then** it uses `asyncio.create_task()` for fire-and-forget
**And** alert failures don't block order processing
**And** alert failures are logged but don't raise exceptions

**Given** a partial fill occurs
**When** detected
**Then** an alert is sent with:
- "⚠️ Partial Fill"
- Symbol, filled amount, remaining amount
- DEX name

**Given** alert rate limiting
**When** many alerts would be sent rapidly
**Then** alerts are throttled to max 1 per minute per error type
**And** a summary is sent: "X additional errors suppressed"

**Given** Telegram credentials are not configured
**When** the application starts
**Then** a warning is logged: "Telegram alerts disabled - credentials not configured"
**And** the application continues without alerting capability

---

### Story 4.3: Auto-Recovery After Outage

As a **system**,
I want **to automatically recover DEX connections after outages**,
So that **trading resumes without manual intervention**.

**Acceptance Criteria:**

**Given** a healthy DEX connection
**When** a health check runs every 30 seconds
**Then** the connection status is verified
**And** latency is measured and recorded

**Given** a DEX health check fails
**When** the failure is detected
**Then** the DEX status is set to "degraded"
**And** an alert is sent: "⚠️ Extended DEX degraded - health check failed"
**And** reconnection attempts begin

**Given** reconnection attempts
**When** initiated
**Then** exponential backoff is used: 1s → 2s → 4s → 8s → max 30s
**And** each attempt is logged with attempt number

**Given** 3 consecutive health check failures
**When** the threshold is reached
**Then** DEX status is set to "offline"
**And** an alert is sent: "🚨 Extended DEX offline - 3 consecutive failures"

**Given** a DEX marked as "offline" or "degraded"
**When** a health check succeeds
**Then** the status is set back to "healthy"
**And** an alert is sent: "✅ Extended DEX recovered"
**And** normal operation resumes

**Given** auto-recovery
**When** a DEX recovers
**Then** no manual intervention is required
**And** the next webhook signal will execute normally

**Given** the health check interval
**When** configurable
**Then** `HEALTH_CHECK_INTERVAL_SECONDS` env var controls it (default: 30)

---

### Story 4.4: Error Logging with Full Context

As a **developer/operator**,
I want **all errors logged with full context**,
So that **I can debug issues quickly**.

**Acceptance Criteria:**

**Given** any error in the system
**When** it is logged
**Then** structlog is used with bound context:
- `signal_id` (if applicable)
- `dex_id` (if applicable)
- `user_id` (if applicable)
- `error_type`: categorized error code
- `error_message`: human-readable description
- `timestamp`: ISO format

**Given** a DEX API error
**When** logged
**Then** the log includes:
- Full request details (method, URL, headers without secrets)
- Response status code
- Response body (truncated if > 1KB)
- Latency

**Given** a webhook validation error
**When** logged
**Then** the log includes:
- Raw payload (for debugging malformed JSON)
- Validation error details
- Client IP (for abuse detection)

**Given** structlog configuration
**When** the application starts
**Then** JSON format is used for structured log output
**And** logs are written to stdout (container-friendly)

**Given** sensitive data
**When** logging occurs
**Then** secrets are redacted:
- API keys show as "***"
- Tokens show as first 4 chars + "..."
- Wallet addresses are NOT redacted (needed for debugging)

**Given** log levels
**When** used consistently
**Then**:
- `DEBUG`: Development details, raw payloads
- `INFO`: Normal operations, successful executions
- `WARNING`: Recoverable issues, degraded states
- `ERROR`: Failures requiring attention

---

### Story 4.5: Error Log Viewer

As a **user**,
I want **to view recent error log entries**,
So that **I can understand what went wrong without accessing server logs**.

**Acceptance Criteria:**

**Given** an authenticated user
**When** they call `GET /api/errors`
**Then** the last 50 error entries are returned (default)

**Given** the error log endpoint
**When** called with `?limit=N` parameter
**Then** up to N entries are returned (max 100)

**Given** the error log endpoint
**When** called with `?hours=24` parameter
**Then** only errors from the last 24 hours are returned

**Given** an error log entry
**When** returned via API
**Then** it includes:
```json
{
  "id": "err-123",
  "timestamp": "2026-01-19T10:00:00Z",
  "level": "error",
  "error_type": "DEX_TIMEOUT",
  "message": "Extended DEX timeout after 10s",
  "context": {
    "signal_id": "abc123",
    "dex_id": "extended",
    "latency_ms": 10000
  }
}
```

**Given** error storage
**When** errors are logged
**Then** they are also written to an `error_logs` table:
- `id` (primary key)
- `level` (error/warning)
- `error_type` (categorized code)
- `message` (text)
- `context_data` (JSON)
- `created_at` (timestamp, indexed)

**Given** error log retention
**When** cleanup runs (daily)
**Then** entries older than 90 days are deleted
**And** cleanup is logged

**Given** no errors in the requested timeframe
**When** the endpoint is called
**Then** an empty array is returned: `{"errors": [], "count": 0}`

---

## Epic 5: Dashboard, Volume Stats & Configuration

**Goal:** Users can view their execution stats, configure position sizes, and get a "glance-and-go" status check.

---

### Story 5.1: Stats Service & Volume Tracking

As a **system**,
I want **to track and aggregate execution volume per DEX**,
So that **users can see their trading activity and progress toward airdrop goals**.

**Acceptance Criteria:**

**Given** the stats service
**When** I check `services/stats.py`
**Then** a `StatsService` class exists for volume and execution tracking

**Given** any successful execution
**When** it is recorded
**Then** the volume is added to the user's total for that DEX
**And** volume is stored in USD equivalent (or base asset value)

**Given** volume tracking
**When** queried
**Then** volume can be aggregated by:
- Per DEX (`extended`, `paradex`, etc.)
- Per time period (today, this week, this month, all-time)
- Per user

**Given** the `executions` table
**When** volume is calculated
**Then** it sums `filled_size * fill_price` for all successful executions
**And** excludes test mode executions (`is_test_mode: true`)

**Given** volume calculation performance
**When** queried frequently
**Then** aggregated totals are cached and updated incrementally
**And** cache invalidation occurs on new executions

**Given** the stats service
**When** `get_volume_stats(user_id, dex_id, period)` is called
**Then** it returns:
```python
VolumeStats(
    dex_id="extended",
    period="today",
    volume_usd=Decimal("47250.00"),
    execution_count=14,
    last_updated=datetime
)
```

---

### Story 5.2: Volume Display (Today/Week)

As a **user**,
I want **to see today's and this week's volume totals**,
So that **I can track my progress toward airdrop qualification thresholds**.

**Acceptance Criteria:**

**Given** an authenticated user
**When** they call `GET /api/stats/volume`
**Then** the response includes today's volume per DEX:
```json
{
  "today": {
    "extended": {"volume_usd": "47250.00", "executions": 14},
    "total": {"volume_usd": "47250.00", "executions": 14}
  },
  "this_week": {
    "extended": {"volume_usd": "284000.00", "executions": 89},
    "total": {"volume_usd": "284000.00", "executions": 89}
  },
  "updated_at": "2026-01-19T10:00:00Z"
}
```

**Given** "today" calculation
**When** determining the time range
**Then** it uses UTC midnight to current time

**Given** "this week" calculation
**When** determining the time range
**Then** it uses Monday 00:00 UTC to current time

**Given** no executions in a period
**When** volume is queried
**Then** the values are `"0.00"` (not null or missing)

**Given** the volume endpoint
**When** called with `?dex=extended` parameter
**Then** only that DEX's volume is returned

---

### Story 5.3: Execution Count & Success Rate

As a **user**,
I want **to see my execution count and success rate**,
So that **I can monitor system reliability**.

**Acceptance Criteria:**

**Given** an authenticated user
**When** they call `GET /api/stats/executions`
**Then** the response includes:
```json
{
  "today": {
    "total": 14,
    "successful": 14,
    "failed": 0,
    "partial": 0,
    "success_rate": "100.00%"
  },
  "this_week": {
    "total": 89,
    "successful": 87,
    "failed": 1,
    "partial": 1,
    "success_rate": "97.75%"
  },
  "all_time": {
    "total": 523,
    "successful": 515,
    "failed": 5,
    "partial": 3,
    "success_rate": "98.47%"
  }
}
```

**Given** success rate calculation
**When** computed
**Then** `success_rate = (successful / total) * 100`
**And** partial fills count as successful for rate calculation

**Given** zero executions
**When** success rate is calculated
**Then** it returns `"N/A"` (not divide by zero error)

**Given** execution counts
**When** queried
**Then** test mode executions are excluded from counts

---

### Story 5.4: Dashboard Endpoint

As a **user**,
I want **a single dashboard endpoint with all key status information**,
So that **I can do a "glance and go" health check in 30 seconds**.

**Acceptance Criteria:**

**Given** an authenticated user
**When** they call `GET /api/dashboard`
**Then** the response includes all key information:
```json
{
  "status": "all_ok",
  "test_mode": false,
  "dex_status": {
    "extended": {"status": "healthy", "latency_ms": 45}
  },
  "volume_today": {
    "total_usd": "47250.00",
    "by_dex": {"extended": "47250.00"}
  },
  "executions_today": {
    "total": 14,
    "success_rate": "100.00%"
  },
  "recent_errors": 0,
  "onboarding_complete": true,
  "updated_at": "2026-01-19T10:00:00Z"
}
```

**Given** the "everything OK" indicator
**When** all conditions are met:
- All DEXs healthy
- No errors in last hour
- Onboarding complete
**Then** `status` is `"all_ok"`

**Given** any DEX is degraded or offline
**When** status is calculated
**Then** `status` is `"degraded"` or `"offline"`

**Given** errors occurred in the last hour
**When** status is calculated
**Then** `recent_errors` shows the count
**And** `status` may still be `"all_ok"` if DEXs are healthy (errors are informational)

**Given** test mode is active
**When** dashboard is displayed
**Then** `test_mode: true` is prominently included
**And** a `test_mode_warning` field contains: "No real trades - test mode active"

**Given** dashboard performance
**When** called
**Then** response time is < 200ms (NFR2 requires < 2s, we target much faster)

---

### Story 5.5: Onboarding Checklist

As a **new user**,
I want **to see an onboarding checklist showing setup progress**,
So that **I know what steps remain before I can start trading**.

**Acceptance Criteria:**

**Given** an authenticated user
**When** they call `GET /api/onboarding`
**Then** the response includes checklist status:
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

**Given** onboarding step tracking
**When** a step is completed
**Then** it is persisted in `users.config_data` as `onboarding_steps`

**Given** "wallet_connected" step
**When** checked
**Then** it is complete if user has a valid session

**Given** "dex_authorized" step
**When** checked
**Then** it is complete if at least one DEX adapter has successful connection

**Given** "webhook_configured" step
**When** checked
**Then** it is complete if user has a webhook token generated

**Given** "test_signal_sent" step
**When** checked
**Then** it is complete if user has at least one test mode execution

**Given** "first_live_trade" step
**When** checked
**Then** it is complete if user has at least one non-test execution

**Given** all steps complete
**When** onboarding is queried
**Then** `complete: true` and `progress: "5/5"`

---

### Story 5.6: Position Size Configuration

As a **user**,
I want **to configure my position size per trade and maximum limit**,
So that **I can control my risk exposure**.

**Acceptance Criteria:**

**Given** an authenticated user
**When** they call `GET /api/config`
**Then** the response includes position size settings:
```json
{
  "position_size": "0.5",
  "max_position_size": "10.0",
  "position_size_unit": "ETH"
}
```

**Given** an authenticated user
**When** they call `PUT /api/config` with:
```json
{
  "position_size": "1.0",
  "max_position_size": "5.0"
}
```
**Then** the settings are updated in `users.config_data`
**And** the response confirms the new values

**Given** position size validation
**When** `position_size` is set
**Then** it must be > 0
**And** it must be <= `max_position_size`

**Given** max position size validation
**When** `max_position_size` is set
**Then** it must be > 0
**And** a system-wide absolute maximum is enforced (e.g., 100 ETH)

**Given** an order execution
**When** size exceeds `max_position_size`
**Then** the order is rejected with error: "Position size exceeds configured maximum"
**And** the signal is logged but not executed

**Given** default values
**When** a new user is created
**Then** `position_size` defaults to "0.1"
**And** `max_position_size` defaults to "10.0"

---

### Story 5.7: Webhook URL & Payload Display

As a **user**,
I want **to view my webhook URL and expected payload format**,
So that **I can configure TradingView alerts correctly**.

**Acceptance Criteria:**

**Given** an authenticated user
**When** they call `GET /api/config/webhook`
**Then** the response includes:
```json
{
  "webhook_url": "https://kitkat.example.com/api/webhook?token=abc123...",
  "payload_format": {
    "required_fields": ["symbol", "side", "size"],
    "optional_fields": ["price", "order_type"],
    "example": {
      "symbol": "ETH-PERP",
      "side": "buy",
      "size": "{{strategy.position_size}}"
    }
  },
  "tradingview_setup": {
    "alert_name": "kitkat-001 Signal",
    "webhook_url": "https://kitkat.example.com/api/webhook?token=abc123...",
    "message_template": "{\"symbol\": \"{{ticker}}\", \"side\": \"{{strategy.order.action}}\", \"size\": \"{{strategy.position_size}}\"}"
  }
}
```

**Given** the webhook URL display
**When** shown to user
**Then** it includes the full URL with their unique token
**And** a "Copy" indicator suggests it can be copied

**Given** the payload format
**When** displayed
**Then** it shows required vs optional fields
**And** includes a working example

**Given** TradingView setup instructions
**When** displayed
**Then** it provides ready-to-paste values for TradingView alert configuration

**Given** the webhook token
**When** displayed in the URL
**Then** only the first 8 characters are shown, rest replaced with "..."
**And** a "Reveal" option shows the full token

---

### Story 5.8: Telegram Configuration

As a **user**,
I want **to configure my Telegram alert destination**,
So that **I receive alerts in my preferred chat**.

**Acceptance Criteria:**

**Given** an authenticated user
**When** they call `GET /api/config/telegram`
**Then** the response includes:
```json
{
  "configured": true,
  "chat_id": "123456789",
  "bot_status": "connected",
  "test_available": true
}
```

**Given** an authenticated user
**When** they call `PUT /api/config/telegram` with:
```json
{
  "chat_id": "123456789"
}
```
**Then** the chat ID is saved to `users.config_data`
**And** a test message is sent to verify the configuration

**Given** Telegram configuration
**When** the test message is sent
**Then** it contains: "✅ kitkat-001 alerts configured successfully!"
**And** the response indicates success or failure

**Given** an invalid chat ID
**When** configuration is attempted
**Then** the test message fails
**And** the response includes: `{"error": "Failed to send test message - check chat ID"}`
**And** the configuration is NOT saved

**Given** Telegram not configured
**When** the config endpoint is called
**Then** `configured: false` is returned
**And** setup instructions are included

**Given** the system bot token
**When** Telegram is configured per-user
**Then** the bot token is system-wide (from env)
**And** only the chat_id is user-configurable
**And** users cannot see or modify the bot token
