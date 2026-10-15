import os
import base64
import hmac
import hashlib
import logging
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("auth")

AUTH_USER = os.getenv("APP_USER", os.getenv("AUTH_USERNAME", "judge"))
AUTH_PASS = os.getenv("APP_PASSWORD", os.getenv("AUTH_PASSWORD", "Aegis2026!"))
SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "aegis-hackathon-2026-secret-key-salt")


def verify_credentials(user: str, password: str) -> bool:
    if not user or not password:
        return False
    return hmac.compare_digest(user.strip(), AUTH_USER.strip()) and hmac.compare_digest(password.strip(), AUTH_PASS.strip())


def make_auth_cookie_token(username: Optional[str] = None) -> str:
    user = username or AUTH_USER
    sig = hmac.new(SECRET_KEY.encode(), f"{user}:{AUTH_PASS}".encode(), hashlib.sha256).hexdigest()
    return f"{user}:{sig}"


def verify_auth_token(token: Optional[str]) -> bool:
    if not token or ":" not in token:
        return False
    try:
        user, sig = token.split(":", 1)
        if not hmac.compare_digest(user, AUTH_USER):
            return False
        expected_sig = hmac.new(SECRET_KEY.encode(), f"{user}:{AUTH_PASS}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected_sig)
    except Exception as e:
        logger.debug(f"Auth token verification error: {e}")
        return False


def verify_basic_auth(auth_header: Optional[str]) -> bool:
    if not auth_header or not auth_header.startswith("Basic "):
        return False
    try:
        encoded = auth_header[6:].strip()
        decoded = base64.b64decode(encoded).decode("utf-8")
        if ":" not in decoded:
            return False
        user, password = decoded.split(":", 1)
        return verify_credentials(user, password)
    except Exception as e:
        logger.debug(f"Basic auth parse error: {e}")
        return False


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware ensuring only authenticated judges and team members can access AEGIS.
    Supports HTTP Basic Auth dialog and automatic session cookie.
    Allows unauthenticated access to /health for Cloud Run liveness checks.
    """
    async def dispatch(self, request: Request, call_next):
        # Whitelisted health check, robots, and image assets
        if request.url.path in ("/health", "/robots.txt") or request.url.path.startswith("/img/"):
            return await call_next(request)

        # Allow WebSocket upgrades to be verified at the endpoint level
        if request.scope.get("type") == "websocket" or request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # 1. Check existing auth cookie
        cookie_token = request.cookies.get("aegis_auth")
        if cookie_token and verify_auth_token(cookie_token):
            return await call_next(request)

        # 2. Check HTTP Basic Auth header
        auth_header = request.headers.get("authorization")
        if verify_basic_auth(auth_header):
            response = await call_next(request)
            token = make_auth_cookie_token(AUTH_USER)
            response.set_cookie(
                key="aegis_auth",
                value=token,
                max_age=86400 * 7,
                path="/",
                httponly=True,
                samesite="lax",
            )
            return response

        # 3. Check query param credentials (e.g. ?user=judge&pass=Aegis2026!)
        q_user = request.query_params.get("user")
        q_pass = request.query_params.get("pass")
        if q_user and q_pass and verify_credentials(q_user, q_pass):
            response = await call_next(request)
            token = make_auth_cookie_token(AUTH_USER)
            response.set_cookie(
                key="aegis_auth",
                value=token,
                max_age=86400 * 7,
                path="/",
                httponly=True,
                samesite="lax",
            )
            return response

        # Unauthorized: Prompt browser native Basic Auth modal
        return Response(
            content="AEGIS Live Meeting Co-Pilot - Authentication Required.\nPlease enter the Judge ID and Password.",
            status_code=401,
            headers={
                "WWW-Authenticate": 'Basic realm="AEGIS Meeting Assistant (Judge Access)", charset="UTF-8"',
                "Content-Type": "text/plain; charset=utf-8",
            },
        )
