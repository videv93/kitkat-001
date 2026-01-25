"""Utility functions for token generation and other common tasks."""

import secrets


def generate_secure_token() -> str:
    """Generate a cryptographically secure random token.

    Returns a 128-bit random token as a URL-safe string using the secrets module.
    This is suitable for both webhook tokens and session tokens.

    Returns:
        str: 128-bit random token as URL-safe string (approximately 24 characters)
    """
    return secrets.token_urlsafe(16)
