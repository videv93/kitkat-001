"""Wallet connection API endpoints (Story 2.3).

Provides endpoints for:
- Challenge generation for wallet authentication
- Signature verification and session creation
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from kitkat.database import get_db_session
from kitkat.models import (
    ChallengeRequest,
    ChallengeResponse,
    VerifyRequest,
    VerifyResponse,
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


def _validate_ethereum_address(wallet_address: str) -> str:
    """Validate Ethereum address format.

    Args:
        wallet_address: The address to validate.

    Returns:
        The validated address.

    Raises:
        HTTPException: If address format is invalid.
    """
    if not wallet_address:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Wallet address is required",
                "code": "INVALID_ADDRESS",
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )

    if not wallet_address.startswith("0x"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid Ethereum address: must start with 0x",
                "code": "INVALID_ADDRESS",
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )

    if len(wallet_address) != 42:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid Ethereum address: must be 42 characters",
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

    return wallet_address


@router.get("/challenge", response_model=ChallengeResponse)
async def get_challenge(
    wallet_address: str = Query(..., description="Ethereum wallet address"),
    request: Request = None,
    verifier: SignatureVerifier = Depends(get_signature_verifier),
) -> ChallengeResponse:
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
    """
    log = logger.bind(wallet_address=wallet_address[:10] + "..." if len(wallet_address) >= 10 else wallet_address)

    # Validate address format
    wallet_address = _validate_ethereum_address(wallet_address)

    # Rate limiting: prevent brute force on challenge endpoint (Story 2.3, AC5.5)
    rate_limiter = request.app.state.rate_limiter if request and hasattr(request.app.state, "rate_limiter") else None
    if rate_limiter:
        # Use wallet address as the rate limit key
        if not rate_limiter.is_allowed(wallet_address):
            log.warning("Rate limit exceeded for challenge generation")
            raise HTTPException(
                status_code=429,
                detail={
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

    # Validate address format (additional check beyond Pydantic)
    try:
        _validate_ethereum_address(request.wallet_address)
    except HTTPException as e:
        if e.status_code == 400:
            raise
        raise

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
        raise HTTPException(
            status_code=401,
            detail={
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
