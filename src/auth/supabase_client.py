"""
Supabase Client for Authentication.

Uses direct HTTP calls to Supabase Auth REST API for reliable timeout control,
and the Supabase SDK for token verification.
"""

import os
from typing import Optional, Dict, Any
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from dotenv import load_dotenv
import httpx
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Auth timeout for direct HTTP calls to Supabase Auth API
AUTH_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Singleton instance
_supabase_client: Optional[Client] = None


def _get_auth_headers() -> Dict[str, str]:
    """Get headers for direct Supabase Auth API calls."""
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }


def _parse_auth_response(response: httpx.Response) -> Dict[str, Any]:
    """
    Parse a Supabase Auth response as JSON, tolerating non-JSON error pages.

    The Supabase Auth gateway returns HTML (e.g. a Cloudflare 5xx page) when the
    GoTrue service is unreachable. Calling response.json() on that body raises a
    confusing "Expecting value: line 1 column 1 (char 0)" error, so handle it here
    and surface the real HTTP status instead.
    """
    try:
        return response.json()
    except Exception:
        raise RuntimeError(
            f"Auth service unavailable (HTTP {response.status_code}). "
            "The Supabase Auth service may be down or the project paused. "
            "Please try again shortly."
        )


def get_supabase_client() -> Client:
    """
    Get or create Supabase client instance (singleton pattern).
    Used for token verification only.

    Returns:
        Supabase Client instance

    Raises:
        ValueError: If Supabase credentials are not configured
    """
    global _supabase_client

    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise ValueError(
                "Supabase credentials not configured. "
                "Set SUPABASE_URL and SUPABASE_ANON_KEY environment variables."
            )

        _supabase_client = create_client(
            SUPABASE_URL,
            SUPABASE_ANON_KEY,
            options=SyncClientOptions(
                httpx_client=httpx.Client(
                    timeout=AUTH_TIMEOUT,
                    follow_redirects=True,
                    http2=True,
                ),
            ),
        )
        logger.info("Supabase client initialized")

    return _supabase_client


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Supabase JWT token and return user info.

    Args:
        token: JWT token from Authorization header

    Returns:
        User info dict if valid, None if invalid
    """
    try:
        # Use direct API call for token verification too
        response = httpx.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                **_get_auth_headers(),
                "Authorization": f"Bearer {token}",
            },
            timeout=AUTH_TIMEOUT,
        )

        if response.status_code == 200:
            user = response.json()
            return {
                "id": user.get("id"),
                "email": user.get("email"),
                "created_at": user.get("created_at"),
            }

        return None

    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        return None


def get_user_from_token(token: str) -> Optional[str]:
    """
    Extract user ID from JWT token.

    Args:
        token: JWT token from Authorization header

    Returns:
        User ID (UUID) if valid, None if invalid
    """
    user_info = verify_token(token)
    return user_info["id"] if user_info else None


def sign_up(email: str, password: str) -> Dict[str, Any]:
    """
    Register a new user with email and password.
    Uses direct HTTP call to Supabase Auth REST API.

    Args:
        email: User's email address
        password: User's password

    Returns:
        Dict with 'success' boolean and 'user' or 'error' info
    """
    try:
        response = httpx.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            headers=_get_auth_headers(),
            json={"email": email, "password": password},
            timeout=AUTH_TIMEOUT,
        )

        data = _parse_auth_response(response)

        if response.status_code in (200, 201):
            user = data.get("user") or data
            user_id = user.get("id")
            user_email = user.get("email", email)

            if not user_id:
                return {"success": False, "error": "Sign up failed - no user returned"}

            result = {
                "success": True,
                "user": {"id": user_id, "email": user_email},
            }

            access_token = data.get("access_token")
            if access_token:
                result["session"] = {
                    "access_token": access_token,
                    "refresh_token": data.get("refresh_token"),
                }
            else:
                result["message"] = (
                    "Please check your email to confirm your account before signing in."
                )

            return result

        # Error response
        error_msg = data.get("error_description") or data.get("msg") or data.get("error", "Sign up failed")
        return {"success": False, "error": error_msg}

    except httpx.TimeoutException as e:
        logger.error(f"Sign up timeout: {e}")
        return {"success": False, "error": f"Connection to auth service timed out: {e}"}
    except Exception as e:
        logger.error(f"Sign up error: {e}")
        return {"success": False, "error": str(e)}


def sign_in(email: str, password: str) -> Dict[str, Any]:
    """
    Sign in a user with email and password.
    Uses direct HTTP call to Supabase Auth REST API.

    Args:
        email: User's email address
        password: User's password

    Returns:
        Dict with 'success' boolean and 'user'/'session' or 'error' info
    """
    try:
        response = httpx.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers=_get_auth_headers(),
            json={"email": email, "password": password},
            timeout=AUTH_TIMEOUT,
        )

        data = _parse_auth_response(response)

        if response.status_code == 200 and data.get("access_token"):
            user = data.get("user", {})
            return {
                "success": True,
                "user": {
                    "id": user.get("id"),
                    "email": user.get("email", email),
                },
                "session": {
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token"),
                },
            }

        error_msg = data.get("error_description") or data.get("msg") or data.get("error", "Invalid email or password")
        return {"success": False, "error": error_msg}

    except httpx.TimeoutException as e:
        logger.error(f"Sign in timeout: {e}")
        return {"success": False, "error": f"Connection to auth service timed out: {e}"}
    except RuntimeError as e:
        # Auth service unavailable (non-JSON gateway error) — surface the real reason
        logger.error(f"Sign in failed: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Sign in error: {e}")
        return {"success": False, "error": "Invalid email or password"}


def sign_out(access_token: str) -> Dict[str, Any]:
    """
    Sign out a user (invalidate session).

    Args:
        access_token: User's current access token

    Returns:
        Dict with 'success' boolean
    """
    try:
        httpx.post(
            f"{SUPABASE_URL}/auth/v1/logout",
            headers={
                **_get_auth_headers(),
                "Authorization": f"Bearer {access_token}",
            },
            timeout=AUTH_TIMEOUT,
        )
        return {"success": True}

    except Exception as e:
        logger.error(f"Sign out error: {e}")
        return {"success": False, "error": str(e)}
