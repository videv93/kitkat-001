# Story 2.10: Wallet Disconnect & Revocation

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want **to disconnect my wallet and revoke delegation**,
so that **I can stop kitkat-001 from trading on my behalf**.

## Acceptance Criteria

1. **Session Invalidation on Disconnect**: Given a connected user, when they request wallet disconnection, then their session is invalidated immediately and the session record is deleted from the database

2. **No New Orders After Disconnect**: Given a user disconnects, when the disconnection completes, then no new orders can be submitted for that user and any pending operations complete (in-flight orders finish)

3. **Reconnection Flow Required**: Given a disconnected user, when they want to reconnect, then they must go through the full wallet connection flow again and a new session is created

4. **Old Session Token Rejection**: Given a user's session is invalidated, when they try to use the old session token, then the request is rejected with 401

## Tasks / Subtasks

- [ ] Task 1: Add disconnect method to SessionService (AC: #1)
  - [ ] Subtask 1.1: Implement `delete_session(session_id: int)` in SessionService
  - [ ] Subtask 1.2: Implement `delete_all_user_sessions(wallet_address: str)` for full wallet disconnect
  - [ ] Subtask 1.3: Ensure session deletion is atomic and committed
  - [ ] Subtask 1.4: Write unit tests for session deletion

- [ ] Task 2: Create disconnect API endpoint (AC: #1, #3)
  - [ ] Subtask 2.1: Add `POST /api/wallet/disconnect` endpoint to `wallet.py`
  - [ ] Subtask 2.2: Require valid session token (via `get_current_user` dependency)
  - [ ] Subtask 2.3: Delete current session and return confirmation
  - [ ] Subtask 2.4: Write API tests for disconnect endpoint

- [ ] Task 3: Add full revocation endpoint (AC: #1, #2)
  - [ ] Subtask 3.1: Add `POST /api/wallet/revoke` endpoint for full delegation revocation
  - [ ] Subtask 3.2: Delete ALL sessions for the wallet address
  - [ ] Subtask 3.3: Update user config to mark DEX authorizations as revoked
  - [ ] Subtask 3.4: Write tests for revocation flow

- [ ] Task 4: Create response models for disconnect/revoke (AC: #1)
  - [ ] Subtask 4.1: Add `DisconnectResponse` model with wallet_address, message, timestamp
  - [ ] Subtask 4.2: Add `RevokeResponse` model with sessions_deleted, delegation_status
  - [ ] Subtask 4.3: Write model serialization tests

- [ ] Task 5: Verify old token rejection (AC: #4)
  - [ ] Subtask 5.1: Write test confirming 401 response after disconnect
  - [ ] Subtask 5.2: Write test confirming 401 response after revoke
  - [ ] Subtask 5.3: Verify error response format matches project standards

- [ ] Task 6: In-flight order handling documentation (AC: #2)
  - [ ] Subtask 6.1: Add dev notes about in-flight order completion (Story 2.11 handles shutdown)
  - [ ] Subtask 6.2: Disconnect only blocks NEW orders, not existing operations
  - [ ] Subtask 6.3: Document behavior in endpoint response

## Dev Notes

### Architecture Compliance

- **Service Layer** (`src/kitkat/services/session_service.py`): Add `delete_session()`, `delete_all_user_sessions()`
- **API Layer** (`src/kitkat/api/wallet.py`): Add disconnect and revoke endpoints
- **Models** (`src/kitkat/models.py`): Add response models for disconnect/revoke

### Project Structure Notes

**Files to create:**
- None - all changes in existing files

**Files to modify:**
- `src/kitkat/services/session_service.py` - Add deletion methods
- `src/kitkat/api/wallet.py` - Add disconnect/revoke endpoints
- `src/kitkat/models.py` - Add response models
- `tests/services/test_session_service.py` - Add deletion tests
- `tests/api/test_wallet.py` - Add disconnect/revoke API tests

**Alignment with project structure:**
```
src/kitkat/
├── services/
│   ├── session_service.py   # MODIFY - add delete methods
├── api/
│   ├── wallet.py            # MODIFY - add disconnect/revoke endpoints
├── models.py                # MODIFY - add response models
```

### Technical Requirements

**SessionService Additions:**
```python
async def delete_session(self, session_id: int) -> bool:
    """Delete a specific session by ID.

    Args:
        session_id: The session ID to delete.

    Returns:
        bool: True if session was deleted, False if not found.
    """
    stmt = delete(SessionModel).where(SessionModel.id == session_id)
    result = await self.db.execute(stmt)
    await self.db.commit()

    if result.rowcount > 0:
        logger.info("Session deleted", session_id=session_id)
        return True
    return False


async def delete_all_user_sessions(self, wallet_address: str) -> int:
    """Delete all sessions for a wallet address.

    Used for full wallet revocation - ensures no active sessions remain.

    Args:
        wallet_address: The wallet address to revoke all sessions for.

    Returns:
        int: Number of sessions deleted.
    """
    stmt = delete(SessionModel).where(SessionModel.wallet_address == wallet_address)
    result = await self.db.execute(stmt)
    await self.db.commit()

    count = result.rowcount
    logger.info("All sessions deleted for wallet", wallet_address=wallet_address[:10], count=count)
    return count
```

**Response Models (add to models.py):**
```python
class DisconnectResponse(BaseModel):
    """Response for wallet disconnect endpoint."""

    model_config = ConfigDict(str_strip_whitespace=True)

    wallet_address: str = Field(..., description="Wallet address (abbreviated)")
    message: str = Field(..., description="Confirmation message")
    timestamp: datetime = Field(..., description="When disconnect occurred")


class RevokeResponse(BaseModel):
    """Response for wallet revocation endpoint."""

    model_config = ConfigDict(str_strip_whitespace=True)

    wallet_address: str = Field(..., description="Wallet address (abbreviated)")
    sessions_deleted: int = Field(..., description="Number of sessions invalidated")
    delegation_revoked: bool = Field(..., description="Whether DEX delegation was revoked")
    message: str = Field(..., description="Confirmation message")
    timestamp: datetime = Field(..., description="When revocation occurred")
```

**API Endpoints (add to wallet.py):**
```python
@router.post("/disconnect", response_model=DisconnectResponse)
async def disconnect_wallet(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DisconnectResponse:
    """Disconnect current wallet session.

    AC1: Session is invalidated immediately.
    AC3: User must re-authenticate to use system again.
    AC4: Old session token will return 401 after this.

    This only invalidates the current session. Other sessions (if any)
    remain active. Use /revoke for full delegation revocation.

    Args:
        current_user: Authenticated user context (from session token).
        db: Database session (injected).

    Returns:
        DisconnectResponse confirming the disconnect.
    """
    log = logger.bind(wallet_address=current_user.wallet_address[:10] + "...")

    session_service = SessionService(db)
    deleted = await session_service.delete_session(current_user.session_id)

    if not deleted:
        # Session already deleted (shouldn't happen with valid auth)
        log.warning("Session not found during disconnect")

    # Abbreviate address for response
    abbreviated = f"{current_user.wallet_address[:6]}...{current_user.wallet_address[-4:]}"

    log.info("Wallet disconnected")

    return DisconnectResponse(
        wallet_address=abbreviated,
        message="Session disconnected successfully. To trade again, please reconnect your wallet.",
        timestamp=datetime.now(timezone.utc),
    )


@router.post("/revoke", response_model=RevokeResponse)
async def revoke_delegation(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> RevokeResponse:
    """Revoke all wallet delegation and invalidate all sessions.

    AC1: All sessions are invalidated immediately.
    AC2: No new orders can be submitted for this user.
    AC3: User must go through full wallet connection flow again.

    This is a complete revocation - all sessions deleted, DEX authorization
    marked as revoked in user config.

    In-flight orders (orders already submitted to DEX) will complete normally.
    This only blocks NEW order submissions.

    Args:
        current_user: Authenticated user context (from session token).
        db: Database session (injected).

    Returns:
        RevokeResponse confirming the revocation.
    """
    log = logger.bind(wallet_address=current_user.wallet_address[:10] + "...")

    # Delete all sessions for this wallet
    session_service = SessionService(db)
    sessions_deleted = await session_service.delete_all_user_sessions(current_user.wallet_address)

    # Update user config to mark delegation as revoked
    user_service = UserService(db)
    current_config = await user_service.get_config(current_user.wallet_address)
    onboarding = current_config.get("onboarding_steps", {})

    await user_service.update_config(
        current_user.wallet_address,
        {
            "onboarding_steps": {
                **onboarding,
                "dex_authorized": False,
            },
            "dex_authorizations": [],  # Clear DEX authorizations
        },
    )

    # Abbreviate address for response
    abbreviated = f"{current_user.wallet_address[:6]}...{current_user.wallet_address[-4:]}"

    log.info("Wallet delegation revoked", sessions_deleted=sessions_deleted)

    return RevokeResponse(
        wallet_address=abbreviated,
        sessions_deleted=sessions_deleted,
        delegation_revoked=True,
        message="Delegation revoked. All sessions invalidated. To trade again, please reconnect your wallet and authorize DEX access.",
        timestamp=datetime.now(timezone.utc),
    )
```

### Previous Story Intelligence

**From Story 2.3 (Wallet Connection & Signature Verification):**
- `wallet.py` contains `/api/wallet/challenge` and `/api/wallet/verify` endpoints
- `_validate_ethereum_address()` helper for address validation
- `SignatureVerifier` handles challenge creation and signature verification
- After verification, `SessionService.create_session()` is called
- `UserService.create_user()` creates user with default config

**From Story 2.2 (User & Session Management):**
- `SessionService` provides `create_session()`, `validate_session()`, `cleanup_expired_sessions()`
- `SessionModel` has: id, token, wallet_address, created_at, expires_at, last_used
- Sessions use 24-hour TTL via `SESSION_TTL_HOURS`
- `CurrentUser` model returned from `validate_session()`

**From Story 2.4 (Webhook URL Generation):**
- User has `webhook_token` for webhook authentication
- Webhook token is NOT invalidated on disconnect (user keeps same URL)
- Only session tokens are invalidated

**Key Patterns:**
- Use `get_current_user` dependency for authenticated endpoints
- Abbreviate wallet address in responses: `0x1234...5678`
- Log with bound wallet_address context
- Return timestamps in ISO format with timezone

### Integration Points

**Disconnect vs Revoke:**

| Action | `/disconnect` | `/revoke` |
|--------|---------------|-----------|
| Scope | Current session only | All sessions |
| DEX Authorization | Unchanged | Revoked |
| User Config | Unchanged | `dex_authorized: False` |
| Webhook Token | Unchanged | Unchanged |
| Reconnect Required | Yes | Yes (full flow) |

**In-Flight Orders (AC2):**

Story 2.11 (Graceful Shutdown) handles completing in-flight orders. For disconnect:
- Orders already submitted to DEX continue to completion
- SignalProcessor checks session validity BEFORE submitting new orders
- After disconnect, new webhook requests with the session token get 401

**Current Implementation Gap:**
- SignalProcessor (Story 2.9) doesn't yet check session validity
- Webhook endpoint uses webhook_token, not session token
- Disconnect blocks dashboard/config access, not webhook execution
- Webhook execution is tied to `webhook_token`, not `session_token`

**Design Decision:**
- Disconnect invalidates session (dashboard, config access)
- Revoke additionally clears `dex_authorizations` (prevents new trades)
- Webhook token is NOT invalidated (user keeps same URL)
- To fully stop webhooks, user must regenerate webhook token (future feature)

### Testing Strategy

**Unit tests (test_session_service.py):**
1. `test_delete_session_existing` - verify session deleted
2. `test_delete_session_not_found` - verify returns False
3. `test_delete_all_user_sessions` - verify all sessions for wallet deleted
4. `test_delete_all_user_sessions_no_sessions` - verify returns 0
5. `test_delete_all_user_sessions_multiple` - verify count matches

**API tests (test_wallet.py):**
1. `test_disconnect_success` - valid session returns DisconnectResponse
2. `test_disconnect_invalidates_session` - subsequent request with same token gets 401
3. `test_disconnect_without_auth` - no token returns 401
4. `test_revoke_success` - returns RevokeResponse with session count
5. `test_revoke_invalidates_all_sessions` - all sessions for wallet are invalid
6. `test_revoke_updates_config` - dex_authorized is False after revoke
7. `test_disconnect_then_reconnect` - can re-verify signature after disconnect

### Git Intelligence

**Recent commits:**
- `54fbfda` chore: manual commit
- `d8d096d` Mark Story 2.5 as done
- `49e12b5` Story 2.5: Extended Adapter Connection
- `359725e` Story 2.4: Webhook URL Generation
- `8bc42b3` Story 2.3: Wallet Connection & Signature Verification

**Files changed in recent stories:**
- `src/kitkat/api/wallet.py` - challenge/verify endpoints (Story 2.3)
- `src/kitkat/services/session_service.py` - session management (Story 2.2)
- `src/kitkat/services/user_service.py` - user config updates

### Error Handling

| Scenario | Action |
|----------|--------|
| No session token | 401 Unauthorized (via get_current_user) |
| Invalid session token | 401 Unauthorized (via get_current_user) |
| Expired session token | 401 Unauthorized (via get_current_user) |
| Session already deleted | Log warning, return success (idempotent) |
| User not found | Log error, return 404 (shouldn't happen) |
| Database error | Raise exception, let FastAPI handle |

### Logging Standards

**Per project-context.md:**
```python
log = logger.bind(wallet_address=wallet_address[:10] + "...")

# On disconnect
log.info("Wallet disconnected")

# On revoke
log.info("Wallet delegation revoked", sessions_deleted=count)

# On error
log.warning("Session not found during disconnect")
log.error("User not found despite valid session")
```

### Security Considerations

- Disconnect requires valid session token (authenticated)
- Revoke requires valid session token (authenticated)
- Session tokens use 128-bit random generation (via `generate_secure_token`)
- After disconnect/revoke, old token returns 401
- Webhook token is NOT invalidated (different security domain)
- No user data is deleted (only sessions)

### Response Formats

**Disconnect Response:**
```json
{
  "wallet_address": "0x1234...5678",
  "message": "Session disconnected successfully. To trade again, please reconnect your wallet.",
  "timestamp": "2026-01-31T10:00:00Z"
}
```

**Revoke Response:**
```json
{
  "wallet_address": "0x1234...5678",
  "sessions_deleted": 3,
  "delegation_revoked": true,
  "message": "Delegation revoked. All sessions invalidated. To trade again, please reconnect your wallet and authorize DEX access.",
  "timestamp": "2026-01-31T10:00:00Z"
}
```

**401 Error Response (old token):**
```json
{
  "error": "Invalid token",
  "code": "INVALID_TOKEN",
  "timestamp": "2026-01-31T10:00:00Z"
}
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.10-Wallet-Disconnect-Revocation]
- [Source: _bmad-output/planning-artifacts/architecture.md#Authentication-Security]
- [Source: _bmad-output/project-context.md#Security-Rules]
- [Source: src/kitkat/api/wallet.py - wallet connection endpoints]
- [Source: src/kitkat/services/session_service.py - session management]

## Implementation Readiness

**Prerequisites met:**
- Story 2.2 completed (SessionService, SessionModel)
- Story 2.3 completed (wallet.py endpoints, signature verification)
- Story 2.4 completed (webhook token in user config)
- `get_current_user` dependency available in deps.py

**Functional Requirements Covered:**
- FR22: User can disconnect wallet and revoke delegation
- NFR9: Session token expiration 24 hours max, refresh on activity

**Estimated Scope:**
- ~30 lines SessionService additions
- ~60 lines API endpoints
- ~30 lines response models
- ~150 lines test code
- 0 new files, 4 modified files

**Related Stories:**
- Story 2.2 (User & Session Management): SessionService base
- Story 2.3 (Wallet Connection): wallet.py endpoints, reconnect flow
- Story 2.11 (Graceful Shutdown): Completes in-flight orders on system shutdown

---

**Created:** 2026-01-31
**Ultimate context engine analysis completed - comprehensive developer guide created**

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
