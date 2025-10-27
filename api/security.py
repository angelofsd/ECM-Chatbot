"""
Security and authentication module for ECM RAG Chatbot API.

Current: Demo token-based auth for local development
Future: Azure AD JWT validation

Middleware extracts user from token and attaches to request.
"""

import logging
from typing import Optional
from functools import lru_cache

from fastapi import HTTPException, Request, status

from config import DEMO_USER_TOKEN, AUTH_ENABLED, LOG_LEVEL
from db import db, get_or_create_user

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)


# ========================
# Token Validation
# ========================

def validate_token(token: str) -> dict:
    """
    Validate authentication token.
    
    Args:
        token: Bearer token from Authorization header
    
    Returns:
        dict with user info: {"user_id": int, "username": str, "department": str}
    
    Raises:
        HTTPException if token is invalid
    """
    if not AUTH_ENABLED:
        # Demo mode: all requests authenticated as "demo_user"
        logger.debug("Auth disabled - using demo user")
        return {
            "user_id": -1,
            "username": "demo_user",
            "department": "Claims",  # Default dept
        }

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )

    # Demo token validation (upgrade to real JWT in production)
    if token == DEMO_USER_TOKEN:
        logger.debug(f"Demo token validated")
        return {
            "user_id": -1,
            "username": "demo_user",
            "department": "Claims",
        }

    # TODO: Validate real JWT from Azure AD
    # import jwt
    # try:
    #     payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    #     return payload
    # except jwt.InvalidTokenError:
    #     raise HTTPException(...)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
    )


def extract_token_from_header(request: Request) -> Optional[str]:
    """Extract bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


# ========================
# User Retrieval
# ========================

@lru_cache(maxsize=128)
def get_or_create_cached_user(username: str, department: str):
    """Get or create user with caching."""
    return get_or_create_user(
        username=username,
        email=f"{username}@newmexicomutual.com",
        department=department,
    )


def get_user_from_request(request: Request):
    """
    Extract and validate user from request.
    
    Args:
        request: FastAPI request
    
    Returns:
        db.User object
    
    Raises:
        HTTPException if user invalid/missing
    """
    token = extract_token_from_header(request)
    if not token and AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization",
        )

    # Validate token
    payload = validate_token(token) if AUTH_ENABLED else {
        "user_id": -1,
        "username": "demo_user",
        "department": "Claims",
    }

    # Get or create user
    user = get_or_create_cached_user(
        username=payload.get("username", "demo_user"),
        department=payload.get("department", ""),
    )

    logger.debug(f"User authenticated: {user.username}")
    return user


# ========================
# Middleware
# ========================

class AuthMiddleware:
    """FastAPI middleware for authentication."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next):
        """Attach user to request scope."""
        try:
            user = get_user_from_request(request)
            request.scope["user"] = user
        except HTTPException as e:
            if AUTH_ENABLED:
                raise
            # In demo mode, create default user
            request.scope["user"] = get_or_create_cached_user("demo_user", "Claims")

        response = await call_next(request)
        return response


# ========================
# Helper Functions
# ========================

def require_auth(request: Request):
    """
    Dependency for FastAPI routes that require authentication.
    
    Usage in route:
        @app.get("/protected")
        def protected_route(request: Request, user = Depends(require_auth)):
            ...
    """
    if "user" not in request.scope:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
        )
    return request.scope["user"]


def require_admin(request: Request):
    """Dependency requiring admin role."""
    user = require_auth(request)
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


if __name__ == "__main__":
    # Test token validation
    print("Testing security module...")
    
    # Demo mode
    payload = validate_token("")
    print(f"Demo user: {payload}")
