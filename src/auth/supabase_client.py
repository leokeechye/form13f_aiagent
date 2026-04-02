"""
Supabase Client for Authentication.

Provides Supabase client initialization and helper functions for auth.
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

# Singleton instance
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get or create Supabase client instance (singleton pattern).

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
                httpx_client=httpx.Client(timeout=httpx.Timeout(30.0)),
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
        client = get_supabase_client()

        # Verify token by getting user info
        response = client.auth.get_user(token)

        if response and response.user:
            return {
                "id": response.user.id,
                "email": response.user.email,
                "created_at": response.user.created_at,
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

    Args:
        email: User's email address
        password: User's password

    Returns:
        Dict with 'success' boolean and 'user' or 'error' info
    """
    try:
        client = get_supabase_client()

        response = client.auth.sign_up({
            "email": email,
            "password": password
        })

        if response.user:
            result = {
                "success": True,
                "user": {
                    "id": response.user.id,
                    "email": response.user.email
                }
            }

            # Include session if available (email confirmation might be required)
            if response.session and response.session.access_token:
                result["session"] = {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token if hasattr(response.session, 'refresh_token') else None
                }
            else:
                result["message"] = "Please check your email to confirm your account before signing in."

            return result
        else:
            return {
                "success": False,
                "error": "Sign up failed"
            }

    except Exception as e:
        logger.error(f"Sign up error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def sign_in(email: str, password: str) -> Dict[str, Any]:
    """
    Sign in a user with email and password.

    Args:
        email: User's email address
        password: User's password

    Returns:
        Dict with 'success' boolean and 'user'/'session' or 'error' info
    """
    try:
        client = get_supabase_client()

        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if response.user and response.session:
            return {
                "success": True,
                "user": {
                    "id": response.user.id,
                    "email": response.user.email
                },
                "session": {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token
                }
            }
        else:
            return {
                "success": False,
                "error": "Invalid email or password"
            }

    except Exception as e:
        logger.error(f"Sign in error: {e}")
        return {
            "success": False,
            "error": "Invalid email or password"
        }


def sign_out(access_token: str) -> Dict[str, Any]:
    """
    Sign out a user (invalidate session).

    Args:
        access_token: User's current access token

    Returns:
        Dict with 'success' boolean
    """
    try:
        client = get_supabase_client()
        client.auth.sign_out()

        return {"success": True}

    except Exception as e:
        logger.error(f"Sign out error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
