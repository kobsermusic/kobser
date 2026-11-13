import asyncio
import hashlib
import logging
import re
import secrets
import time
import unicodedata
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from config import NAVIDROME_URL

log = logging.getLogger(__name__)


def normalize(s: str) -> str:
    """Loose comparison key for titles and artists (case, accents, punctuation)."""
    return _norm(s)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())

CLIENT_ID = "kobser-middleware"
API_VERSION = "1.16.1"


def make_credentials(password: str) -> tuple[str, str]:
    """Derive a reusable Subsonic (salt, token) pair from a password.

    Subsonic auth uses token = md5(password + salt), with a salt the client picks
    and may reuse across requests. We compute the pair once at login and store it
    in place of the password. Anyone with the token can replay it against the
    Subsonic API, but unlike the password it can't be used for Navidrome's web
    login or on other services.
    """
    salt = secrets.token_hex(16)
    token = hashlib.md5((password + salt).encode()).hexdigest()
    return salt, token


def auth_params(username: str, salt: str, token: str) -> dict[str, str]:
    """Subsonic auth params from a stored (salt, token) pair."""
    return {
        "u": username,
        "t": token,
        "s": salt,
        "v": API_VERSION,
        "c": CLIENT_ID,
        "f": "json",
    }


async def ping(username: str, salt: str, token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{NAVIDROME_URL}/rest/ping",
            params=auth_params(username, salt, token),
        )
        r.raise_for_status()
        return r.json().get("subsonic-response", {})


async def is_admin(username: str, salt: str, token: str) -> bool:
    """Return whether the user has the Navidrome admin role.

    Any user can query their own record with Subsonic `getUser`, which includes
    `adminRole`. Returns False on any error, so a failed lookup never grants
    elevated visibility.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{NAVIDROME_URL}/rest/getUser",
                params={"username": username, **auth_params(username, salt, token)},
            )
            r.raise_for_status()
        body = r.json().get("subsonic-response", {})
        if body.get("status") != "ok":
            return False
        return bool(body.get("user", {}).get("adminRole"))
    except Exception:
        return False


async def start_scan(
    username: str, salt: str, token: str, targets: list[str] | None = None,
) -> dict[str, Any]:
    """Start a Navidrome scan.

    `targets` (Navidrome >= 0.59) limits the scan to folders, each written as
    `<libraryId>:<path relative to the library root>`, and without it Navidrome
    scans the whole library."""
    params = list(auth_params(username, salt, token).items())
    params += [("target", t) for t in targets or []]
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{NAVIDROME_URL}/rest/startScan", params=params)
        r.raise_for_status()
        return r.json()


def scan_target(library_id: int | None, library_root: str | None, folder: str | Path) -> str | None:
    """Return `<libraryId>:<relative folder>` for a targeted scan of `folder`.

    Returns None when the target can't be expressed (unknown library, or a
    folder outside or equal to the root). Callers then fall back to a full scan.

    A folder that no longer exists is replaced by its nearest existing ancestor.
    Navidrome skips a missing target ("Target folder does not exist") and keeps
    the tracks that were in it. So after deleting an artist's last song, the scan
    has to cover the folder that contained the removed one."""
    if library_id is None or not library_root:
        return None
    root = Path(library_root).resolve()
    target = Path(folder).resolve()
    while target != root and not target.exists():
        target = target.parent
    try:
        rel = target.relative_to(root)
    except ValueError:
        return None
    if str(rel) in ("", "."):
        return None
    return f"{library_id}:{rel.as_posix()}"


# username -> library id, for sessions created before ids were stored.
_library_id_cache: dict[str, int] = {}


async def resolve_library_id(sess: dict) -> int | None:
    """Return the session's Navidrome library id.

    Older sessions didn't store it. For those, use the id of the user's music
    folder when they have exactly one."""
    if sess.get("library_id") is not None:
        return int(sess["library_id"])
    username = sess["username"]
    if username in _library_id_cache:
        return _library_id_cache[username]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{NAVIDROME_URL}/rest/getMusicFolders",
                params=auth_params(username, sess["salt"], sess["token"]),
            )
            r.raise_for_status()
            folders = (
                r.json().get("subsonic-response", {}).get("musicFolders", {}).get("musicFolder", [])
            )
    except Exception:
        return None
    if len(folders) != 1:
        return None
    _library_id_cache[username] = int(folders[0]["id"])
    return _library_id_cache[username]


async def _search_songs_strict(query: str, username: str, salt: str, token: str, count: int = 50) -> list[dict]:
    """Like search_songs, but raise on failure instead of returning [].

    Used by checks that must tell "no results" apart from "Navidrome errored"."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{NAVIDROME_URL}/rest/search3",
            params={"query": query, "songCount": count, "artistCount": 0, "albumCount": 0,
                    **auth_params(username, salt, token)},
        )
        r.raise_for_status()
    body = r.json().get("subsonic-response", {})
    if body.get("status") != "ok":
        raise RuntimeError(f"search3 failed: {body.get('error')}")
    return body.get("searchResult3", {}).get("song") or []


async def song_is_unlisted(track_id: str, title: str, username: str, salt: str, token: str) -> bool:
    """Return True once the track no longer shows up in the library.

    The check uses search because `getSong` can't detect a deleted file.
    Navidrome keeps a deleted file's track as "missing" until an admin purges it.
    Lookups by id keep succeeding after every listing (search, artists, albums)
    has dropped the track."""
    songs = await _search_songs_strict(title, username, salt, token)
    return all(s.get("id") != track_id for s in songs)


async def matching_song_ids(artist: str, title: str, username: str, salt: str, token: str) -> set[str]:
    """Return ids of library songs whose normalised artist and title match.

    Matching uses tags because the `path` Navidrome reports is built from the
    tags (Artist/Album/Title.ext). It doesn't show the file's real location."""
    want_artist, want_title = _norm(artist), _norm(title)
    songs = await search_songs(title, username, salt, token, count=50)
    return {
        s["id"] for s in songs
        if _norm(s.get("title") or "") == want_title and _norm(s.get("artist") or "") == want_artist
    }


async def new_song_visible(
    artist: str, title: str, known_ids: set[str], username: str, salt: str, token: str,
) -> bool:
    """Return True once a new song matching artist/title is searchable.

    Songs in `known_ids` (the matches from before the download) don't count."""
    return bool(await matching_song_ids(artist, title, username, salt, token) - known_ids)


async def scan_until(
    username: str,
    salt: str,
    token: str,
    done: Callable[[], Awaitable[bool]],
    targets: list[str] | None = None,
    timeout_s: float = 20.0,
    poll_s: float = 0.4,
    targeted_grace_s: float = 6.0,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """Start a scan (targeted when possible) and poll until `done()` sees the change.

    If a targeted scan hasn't made the change visible within `targeted_grace_s`,
    run one full scan. Returns whether the change became visible before
    `timeout_s`. Scan errors are caught, because a slow library refresh must
    never fail the download or delete."""
    start = clock()
    try:
        await start_scan(username, salt, token, targets)
    except Exception as e:
        log.warning("startScan failed (targets=%s): %s", targets, e)
    fell_back = not targets
    check_failed = False
    while clock() - start < timeout_s:
        try:
            if await done():
                log.info("library change visible after %.1fs (targets=%s)", clock() - start, targets)
                return True
        except Exception as e:
            if not check_failed:  # once, so a persistent failure doesn't flood the log
                check_failed = True
                log.warning("library visibility check failed, retrying: %r", e)
        if not fell_back and clock() - start >= targeted_grace_s:
            fell_back = True
            log.info("targeted scan not visible after %.1fs, running a full scan", targeted_grace_s)
            try:
                await start_scan(username, salt, token)
            except Exception:
                pass
        await asyncio.sleep(poll_s)
    log.warning("library change still not visible after %.0fs (targets=%s)", timeout_s, targets)
    return False


async def get_user_libraries(username: str, password: str) -> list[dict[str, Any]]:
    """Return the libraries assigned to the given user, via Navidrome's native API.

    Non-admin users can call /api/user/{their_own_id}. The response includes the
    `libraries` array (with paths) for every library assigned to that user. The
    call needs no admin role and no /api/library access.

    Each entry is `{id, name, path}`. Returns an empty list on failure so callers
    can fall back to the default MUSIC_DIR.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            login = await client.post(
                f"{NAVIDROME_URL}/auth/login",
                json={"username": username, "password": password},
            )
            login.raise_for_status()
            login_data = login.json() or {}
            token = login_data.get("token")
            user_id = login_data.get("id")
            if not token or not user_id:
                return []

            user_resp = await client.get(
                f"{NAVIDROME_URL}/api/user/{user_id}",
                headers={"x-nd-authorization": f"Bearer {token}"},
            )
            user_resp.raise_for_status()
            libraries = (user_resp.json() or {}).get("libraries") or []

            return [
                {"id": lib.get("id"), "name": lib.get("name") or "", "path": lib.get("path") or ""}
                for lib in libraries
                if lib.get("path")
            ]
    except Exception:
        return []


async def search_songs(query: str, username: str, salt: str, token: str, count: int = 10) -> list[dict]:
    """Search Navidrome for songs matching `query`. Returns a list of song dicts."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{NAVIDROME_URL}/rest/search3",
                params={
                    "query": query,
                    "songCount": count,
                    "artistCount": 0,
                    "albumCount": 0,
                    **auth_params(username, salt, token),
                },
            )
            r.raise_for_status()
        body = r.json().get("subsonic-response", {})
        if body.get("status") != "ok":
            return []
        return body.get("searchResult3", {}).get("song") or []
    except Exception:
        return []


async def find_song_id(artist: str, title: str, username: str, salt: str, token: str) -> str | None:
    """Return the Navidrome song id whose artist+title match (normalised), or None."""
    songs = await search_songs(title, username, salt, token)
    na, nt = _norm(artist), _norm(title)
    for s in songs:
        if _norm(s.get("title", "")) == nt and _norm(s.get("artist", "")) == na:
            return s.get("id")
    # Looser fallback that matches on title alone (handles "feat." artist mismatches).
    for s in songs:
        if _norm(s.get("title", "")) == nt:
            return s.get("id")
    return None


async def create_playlist(name: str, song_ids: list[str], username: str, salt: str, token: str) -> str | None:
    """Create a playlist with the given songs. Returns the new playlist id, or None."""
    try:
        params = [("name", name)]
        params += [("songId", sid) for sid in song_ids]
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{NAVIDROME_URL}/rest/createPlaylist",
                params=params + list(auth_params(username, salt, token).items()),
            )
            r.raise_for_status()
        body = r.json().get("subsonic-response", {})
        if body.get("status") != "ok":
            return None
        return (body.get("playlist") or {}).get("id")
    except Exception:
        return None


async def trigger_scan_and_wait(username: str, salt: str, token: str, scan_wait_s: float = 1.5) -> None:
    """Trigger a Navidrome scan and wait long enough for it to finish.

    Polling getScanStatus can't detect when the scan is done, because `lastScan`
    only changes on full scans and `scanning` returns to false after about 30 ms,
    which is too fast to catch. A short fixed wait is enough for Navidrome's
    on-demand scan in almost all cases, and if a download is still missing,
    opening the Library tab again fetches `getArtists` again."""
    try:
        await start_scan(username, salt, token)
    except Exception:
        return
    await asyncio.sleep(scan_wait_s)
