"""Web Push notifications (race alerts on the phone's lock screen).

The server signs each push with its own VAPID key, created on first use and
kept in DATA_DIR/push/, next to the list of devices that turned alerts on.
Browsers hand us a subscription (an endpoint at Apple, Google or Mozilla plus
two keys); we post encrypted messages to it. Nothing here holds personal data.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
from pathlib import Path

from app_config import _flag, is_public_mode

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# Push services want a contact (mailto: or an https origin, no path) in the
# VAPID claims; this one is generic, not anyone's address. PUSH_CONTACT
# overrides it, e.g. "mailto:voce@exemplo.com".
_DEFAULT_CONTACT = "https://github.com"

MAX_SUBSCRIPTIONS = 50


def push_enabled() -> bool:
    """Alerts need live timing, which public sites don't have."""
    return _flag("PUSH_ALERTS", True) and not is_public_mode()


def _dir() -> Path:
    base = Path(os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data")))
    path = base / "push"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _key_path() -> Path:
    return _dir() / "vapid_private.pem"


def _subs_path() -> Path:
    return _dir() / "subscriptions.json"


def _load_or_create_key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    path = _key_path()
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(pem)
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    logger.info("Created a VAPID key for push notifications")
    return key


def public_key() -> str:
    """The VAPID public key in the form PushManager.subscribe() expects."""
    from cryptography.hazmat.primitives import serialization

    with _lock:
        key = _load_or_create_key()
    raw = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _read_subs() -> list[dict]:
    path = _subs_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _write_subs(subs: list[dict]) -> None:
    path = _subs_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(subs))
    tmp.replace(path)


def valid_subscription(sub: object) -> bool:
    if not isinstance(sub, dict):
        return False
    endpoint = sub.get("endpoint")
    keys = sub.get("keys")
    return (
        isinstance(endpoint, str) and endpoint.startswith("https://") and len(endpoint) < 2048
        and isinstance(keys, dict)
        and isinstance(keys.get("p256dh"), str) and 0 < len(keys["p256dh"]) < 256
        and isinstance(keys.get("auth"), str) and 0 < len(keys["auth"]) < 256
    )


def add_subscription(sub: dict) -> None:
    clean = {
        "endpoint": sub["endpoint"],
        "keys": {"p256dh": sub["keys"]["p256dh"], "auth": sub["keys"]["auth"]},
        "created": int(time.time()),
    }
    with _lock:
        subs = [s for s in _read_subs() if s.get("endpoint") != clean["endpoint"]]
        subs.append(clean)
        _write_subs(subs[-MAX_SUBSCRIPTIONS:])


def remove_subscription(endpoint: str) -> bool:
    with _lock:
        subs = _read_subs()
        kept = [s for s in subs if s.get("endpoint") != endpoint]
        if len(kept) != len(subs):
            _write_subs(kept)
            return True
    return False


def has_subscription(endpoint: str) -> bool:
    with _lock:
        return any(s.get("endpoint") == endpoint for s in _read_subs())


def subscription_count() -> int:
    with _lock:
        return len(_read_subs())


def _send_one(sub: dict, payload: str, key_path: str, contact: str) -> bool:
    """Send to one device. False when the device has gone (unsubscribed or
    app removed), so it can be dropped."""
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
            data=payload,
            vapid_private_key=key_path,
            vapid_claims={"sub": contact},
            ttl=600,
            headers={"Urgency": "high"},
            timeout=10,
        )
        return True
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        if status in (404, 410):
            return False
        logger.warning("Push failed (HTTP %s)", status)
    except Exception as e:  # network trouble: keep the device
        logger.warning("Push failed: %s", type(e).__name__)
    return True


def broadcast(title: str, body: str, url: str = "/", tag: str | None = None) -> int:
    """Send a notification to every device. Blocking; run it in a thread.
    Returns how many devices it reached."""
    with _lock:
        _load_or_create_key()
        subs = _read_subs()
    if not subs:
        return 0
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag})
    contact = os.environ.get("PUSH_CONTACT", "").strip() or _DEFAULT_CONTACT
    key_path = str(_key_path())

    gone: list[str] = []
    sent = 0
    for sub in subs:
        if _send_one(sub, payload, key_path, contact):
            sent += 1
        else:
            gone.append(sub["endpoint"])
    for endpoint in gone:
        remove_subscription(endpoint)
    if gone:
        logger.info("Dropped %d push subscription(s) that no longer exist", len(gone))
    return sent


def send_to(endpoint: str, title: str, body: str, url: str = "/") -> bool:
    """Send to one device (the test button). Blocking."""
    with _lock:
        _load_or_create_key()
        sub = next((s for s in _read_subs() if s.get("endpoint") == endpoint), None)
    if sub is None:
        return False
    contact = os.environ.get("PUSH_CONTACT", "").strip() or _DEFAULT_CONTACT
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": "test"})
    ok = _send_one(sub, payload, str(_key_path()), contact)
    if not ok:
        remove_subscription(endpoint)
    return ok
