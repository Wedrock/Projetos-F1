"""Runtime settings read from the environment, and shared request validation."""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache

from fastapi import HTTPException

logger = logging.getLogger(__name__)

SESSION_TYPES = ("R", "Q", "S", "SQ", "FP1", "FP2", "FP3")

MIN_YEAR = 2018
MAX_YEAR = 2035
MAX_ROUND = 30

_DRIVER_RE = re.compile(r"^[A-Z]{3}$")


def _flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("true", "1", "yes", "on")


def allowed_hosts() -> list[str]:
    """Host names the server answers to (ALLOWED_HOSTS, comma separated).

    Defaults to this computer only, so a web page can't reach the server
    through DNS rebinding. Add your domain or LAN address to serve it beyond
    this computer, or "*" to allow any.
    """
    raw = os.environ.get("ALLOWED_HOSTS", "").strip()
    hosts = [h.strip() for h in raw.split(",") if h.strip()]
    return hosts or ["localhost", "127.0.0.1", "*.localhost"]


def is_public_mode() -> bool:
    """Public mode turns off admin and processing features for a shared site."""
    return _flag("PUBLIC_MODE", False)


# The date F1 started requiring an F1 TV login for its timing archive.
PAYWALL_SINCE = "2026-10-15"

_ARCHIVE_LAST_RE = re.compile(r"^(\d{4})/(\d{1,2})$")


@lru_cache(maxsize=1)
def public_archive_last() -> tuple[int, int] | None:
    """Last (year, round) a public site serves, from PUBLIC_ARCHIVE_LAST ("2026/17").

    Rounds after it were never free to download, so a public site must not
    serve them even when they're in the shared bucket. Unset means no cutoff.
    """
    value = os.environ.get("PUBLIC_ARCHIVE_LAST", "").strip()
    if not value:
        return None
    m = _ARCHIVE_LAST_RE.match(value)
    if not m:
        logger.warning(f"Invalid PUBLIC_ARCHIVE_LAST '{value}' (expected YEAR/ROUND, e.g. 2026/17); no cutoff applied")
        return None
    return int(m.group(1)), int(m.group(2))


def is_after_public_cutoff(year: int, round_num: int) -> bool:
    if not is_public_mode():
        return False
    last = public_archive_last()
    return last is not None and (year, round_num) > last


def retention_sweep_enabled() -> bool:
    return _flag("RETENTION_SWEEP_ENABLED", True)


def replay_player() -> str:
    """Which replay player the frontend uses: "static" (default) or "websocket"."""
    value = os.environ.get("REPLAY_PLAYER", "static").strip().lower()
    return value if value in ("static", "websocket") else "static"


def origin_secret() -> str:
    return os.environ.get("ORIGIN_SECRET", "").strip()


def photo_sync_available() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY")) and not is_public_mode()


def set_cache(response, seconds: int, immutable: bool = False) -> None:
    """Cache-Control for read-only data.

    Shared caches (Cloudflare) may only store it when the site has no
    passphrase; behind a passphrase it stays in the viewer's own browser.
    """
    from auth import is_auth_enabled

    scope = "private" if is_auth_enabled() else "public"
    value = f"{scope}, max-age={seconds}"
    if immutable:
        value += ", immutable"
    response.headers["Cache-Control"] = value


def validate_session(year: int, round_num: int, session_type: str) -> None:
    """Reject out-of-range sessions before they reach storage paths or FastF1."""
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise HTTPException(status_code=400, detail=f"Ano sem suporte: {year}")
    if not 1 <= round_num <= MAX_ROUND:
        raise HTTPException(status_code=400, detail=f"Etapa sem suporte: {round_num}")
    if session_type not in SESSION_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipo de sessão desconhecido: {session_type}")
    if is_after_public_cutoff(year, round_num):
        raise HTTPException(
            status_code=404,
            detail="Esta sessão não está disponível neste site. A F1 agora exige uma assinatura do F1 TV para os dados de cronometragem.",
        )


def is_valid_session(year: int, round_num: int, session_type: str) -> bool:
    try:
        validate_session(year, round_num, session_type)
        return True
    except HTTPException:
        return False


def validate_driver(driver: str) -> None:
    if not _DRIVER_RE.match(driver or ""):
        raise HTTPException(status_code=400, detail=f"Código de piloto inválido: {driver}")
