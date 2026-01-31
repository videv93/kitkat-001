"""Wallet connection API endpoints (Story 2.3).

Provides endpoints for:
- Challenge generation for wallet authentication
- Signature verification and session creation
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.api.deps import get_current_user
from kitkat.database import get_db_session
from kitkat.models import (
    ChallengeRequest,
    ChallengeResponse,
    DisconnectResponse,
    RevokeResponse,
    VerifyRequest,
    VerifyResponse,
    CurrentUser,
)
from kitkat.services.session_service import SessionService
from kitkat.services.signature_verifier import get_signature_verifier, SignatureVerifier
from kitkat.services.user_service import UserService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

# Explanation text for AC1
DELEGATION_EXPLANATION = (
    "This grants kitkat-001 delegated trading authority on Extended DEX. "
    "Your private keys are never stored."
)




@router.get("/challenge", response_model=ChallengeResponse)
async def get_challenge(
    wallet_address: str = Query(..., description="Ethereum wallet address"),
    request: Request = None,
    verifier: SignatureVerifier = Depends(get_signature_verifier),
) -> ChallengeResponse | JSONResponse:
    """Generate a challenge message for wallet authentication.

    AC1: Clear explanation displayed about delegation authority.
    AC2: Challenge message generated for user to sign.

    AC5.5: Rate limiting to prevent brute force attacks.

    The challenge includes:
    - A message explaining the delegation
    - A unique nonce for replay prevention
    - A timestamp for challenge expiration

    Args:
        wallet_address: The Ethereum wallet address (0x + 40 hex chars).
        request: FastAPI Request for rate limiting.
        verifier: Signature verifier service (injected).

    Returns:
        ChallengeResponse with message, nonce, expires_at, and explanation.

    Raises:
        HTTPException: 400 for invalid address format, 429 for rate limit.
    """
    log = logger.bind(wallet_address=wallet_address[:10] + "..." if len(wallet_address) >= 10 else wallet_address)

    # Validate address format (Query parameter, not Pydantic validated)
    if not wallet_address or not wallet_address.startswith("0x") or len(wallet_address) != 42:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid Ethereum address format",
                "code": "INVALID_ADDRESS",
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )

    try:
        int(wallet_address[2:], 16)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid Ethereum address: invalid hex characters",
                "code": "INVALID_ADDRESS",
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )

    # Rate limiting: prevent brute force on challenge endpoint (Story 2.3, AC5.5)
    rate_limiter = request.app.state.rate_limiter if request and hasattr(request.app.state, "rate_limiter") else None
    if rate_limiter:
        # Use wallet address as the rate limit key
        if not rate_limiter.is_allowed(wallet_address):
            log.warning("Rate limit exceeded for challenge generation")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too many challenge requests. Please try again later.",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                },
            )

    # Generate challenge
    nonce, expires_at, message = verifier.create_challenge(wallet_address)

    log.info("Challenge generated", nonce=nonce[:8] + "...")

    return ChallengeResponse(
        message=message,
        nonce=nonce,
        expires_at=expires_at,
        explanation=DELEGATION_EXPLANATION,
    )


@router.post("/verify", response_model=VerifyResponse)
async def verify_signature(
    request: VerifyRequest,
    db: AsyncSession = Depends(get_db_session),
    verifier: SignatureVerifier = Depends(get_signature_verifier),
) -> VerifyResponse:
    """Verify wallet signature and create session.

    AC3: Valid signature creates user and session, returns token.
    AC4: Invalid signature rejected with 401.

    Args:
        request: Verification request with wallet_address, signature, nonce.
        db: Database session (injected).
        verifier: Signature verifier service (injected).

    Returns:
        VerifyResponse with session token and expiration.

    Raises:
        HTTPException: 400 for invalid address format.
        HTTPException: 401 for invalid/expired signature.
    """
    log = logger.bind(
        wallet_address=request.wallet_address[:10] + "...",
        nonce=request.nonce[:8] + "..." if len(request.nonce) >= 8 else request.nonce,
    )

    # Verify signature
    try:
        verifier.verify_signature(
            wallet_address=request.wallet_address,
            signature=request.signature,
            nonce=request.nonce,
        )
    except ValueError as e:
        error_msg = str(e)
        log.warning("Signature verification failed", error=error_msg)
        return JSONResponse(
            status_code=401,
            content={
                "error": error_msg,
                "code": "INVALID_SIGNATURE",
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )

    # Get or create user
    user_service = UserService(db)
    user = await user_service.get_user(request.wallet_address)

    if not user:
        log.info("Creating new user for wallet")
        user = await user_service.create_user(request.wallet_address)

        # Update onboarding step
        await user_service.update_config(
            request.wallet_address,
            {"onboarding_steps": {**user.config_data.get("onboarding_steps", {}), "wallet_connected": True}},
        )

    # Create session
    session_service = SessionService(db)
    session = await session_service.create_session(request.wallet_address)

    log.info("Session created after signature verification", session_id=session.id)

    return VerifyResponse(
        token=session.token,
        expires_at=session.expires_at,
        wallet_address=request.wallet_address,
    )


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
    abbreviated = f"{current_user.wallet_address[:6]}...{current_user.wallet_address[-4:]}"
    log = logger.bind(wallet_address=abbreviated)

    session_service = SessionService(db)
    deleted = await session_service.delete_session(current_user.session_id)

    if not deleted:
        # Session already deleted (shouldn't happen with valid auth)
        log.warning("Session not found during disconnect")

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

    NOTE: Webhook tokens are NOT invalidated on revocation. Users must
    separately regenerate webhook tokens if they want to fully stop webhooks.

    Args:
        current_user: Authenticated user context (from session token).
        db: Database session (injected).

    Returns:
        RevokeResponse confirming the revocation.
    """
    abbreviated = f"{current_user.wallet_address[:6]}...{current_user.wallet_address[-4:]}"
    log = logger.bind(wallet_address=abbreviated)

    # Delete all sessions for this wallet
    session_service = SessionService(db)
    sessions_deleted = await session_service.delete_all_user_sessions(current_user.wallet_address)

    # Update user config to mark delegation as revoked
    user_service = UserService(db)
    try:
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
    except Exception as e:
        log.error("Failed to update user config during revocation", error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to revoke delegation",
                "code": "REVOCATION_CONFIG_ERROR",
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )

    log.info("Wallet delegation revoked", sessions_deleted=sessions_deleted)

    return RevokeResponse(
        wallet_address=abbreviated,
        sessions_deleted=sessions_deleted,
        delegation_revoked=True,
        message="Delegation revoked. All sessions invalidated. To trade again, please reconnect your wallet and authorize DEX access.",
        timestamp=datetime.now(timezone.utc),
    )
