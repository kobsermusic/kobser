import logging
import time
from collections import deque
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import get_current_session
from db import create_session, delete_session
from services.navidrome_client import (
    get_user_libraries,
    make_credentials,
    ping,
)
from services.navidrome_client import (
    is_admin as get_is_admin,
)

router = APIRouter()
log = logging.getLogger(__name__)

# Throttle login attempts per client to slow down credential brute-forcing.
# Only rejected credentials count (Navidrome-unreachable errors don't), so a
# flaky backend can't lock legitimate users out.
_LOGIN_WINDOW_S = 300
_LOGIN_MAX_FAILURES = 8
_login_failures: dict[str, deque] = {}
_login_lock = Lock()


def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_rate_limited(key: str) -> bool:
    now = time.time()
    with _login_lock:
        dq = _login_failures.get(key)
        if not dq:
            return False
        while dq and dq[0] <= now - _LOGIN_WINDOW_S:
            dq.popleft()
        if not dq:
            _login_failures.pop(key, None)
            return False
        return len(dq) >= _LOGIN_MAX_FAILURES


def _record_failure(key: str) -> None:
    with _login_lock:
        _login_failures.setdefault(key, deque()).append(time.time())


def _clear_failures(key: str) -> None:
    with _login_lock:
        _login_failures.pop(key, None)


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/api/login")
async def login(body: LoginRequest, request: Request):
    key = _client_key(request)
    if _is_rate_limited(key):
        raise HTTPException(status_code=429, detail="too many login attempts, please try again later")

    # Derive a reusable Subsonic (salt, token) from the password and verify it
    # with a ping. The cleartext password is used only here and never stored.
    salt, token = make_credentials(body.password)
    try:
        r = await ping(body.username, salt, token)
        authed = r.get("status") == "ok"
    except Exception as exc:
        # Navidrome is unreachable or returned an error. That isn't a bad-credential
        # attempt, so don't count it against the rate limit or report it as a 401.
        # Log the real cause and tell the client the music server is down.
        log.warning("login ping to Navidrome failed: %s", exc)
        raise HTTPException(
            status_code=502, detail="music server unreachable"
        ) from exc

    if not authed:
        _record_failure(key)
        raise HTTPException(status_code=401, detail="invalid credentials")
    _clear_failures(key)

    # Resolve the user's library path once (it needs the native password login)
    # and store the path, never the password, so later downloads can go there.
    libs = await get_user_libraries(body.username, body.password)
    library_path = libs[0]["path"] if libs else None
    library_id = libs[0].get("id") if libs else None

    # Store the admin role too, because admins can see all users' downloads.
    admin = await get_is_admin(body.username, salt, token)

    sid = create_session(body.username, salt, token, library_path, is_admin=admin, library_id=library_id)
    return {"sessionId": sid, "username": body.username}


@router.post("/api/logout")
async def logout(sess: dict = Depends(get_current_session)):
    delete_session(sess["id"])
    return {"ok": True}


@router.get("/api/me")
async def me(sess: dict = Depends(get_current_session)):
    return {"username": sess["username"]}
