"""Team radio captions in English and Portuguese with Google's Gemini.

Turned on by GEMINI_API_KEY (a free key from aistudio.google.com), or by
pasting the key in the app (Settings > Team Radio). Gemini
listens to the clip itself, so it needs no Whisper: light enough for a phone
server. It writes what's said in English and a Portuguese translation that
keeps F1 terms people use in Brazil ("box", "pit", "safety car").

The free plan allows a few requests a minute, so calls are spaced out and a
refusal for going too fast is retried after a pause. Note that on the free
plan Google may use what's sent to improve its models.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass

import httpx

from services.caption_ai import _audio_format, _context_text

logger = logging.getLogger(__name__)

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}"
# Google's alias for its current Flash-Lite model, which the free plan covers
DEFAULT_MODEL = "gemini-flash-lite-latest"
TIMEOUT_S = 45.0
# The free plan's per-minute limit is around 15 requests for Flash-Lite
DEFAULT_MIN_INTERVAL_S = 4.5
RETRY_WAIT_S = 30.0

INSTRUCTIONS = """You caption Formula 1 team radio: short messages between a driver and their race engineer, often with engine noise and a poor signal.

1. "en": write what is said in the audio, in English, as one caption.
   - The audio decides. A draft from a speech-to-text model may be given; use it only as a hint.
   - Spell driver, team and F1 terms correctly, using the context below. Use British spelling ("tyres").
   - Don't add or explain anything that wasn't said. Keep "copy", "box, box" and swearing.
   - If part is unintelligible, caption the parts you can hear.
2. "pt": translate "en" into Brazilian Portuguese, as a Brazilian F1 broadcast would say it.
   - Natural and short, like a subtitle. Keep the tone, including swearing.
   - Keep terms Brazilians use in English: box, pit, pit stop, safety car, VSC, undercut, overcut, delta, DRS. "Copy" becomes "entendido". "Tyres" becomes "pneus"; softs/mediums/hards become macios/médios/duros.
   - Keep names as they are.

If nobody speaks, both are null.
Reply with JSON only: {"en": "...", "pt": "..."} or {"en": null, "pt": null}."""

_lock = threading.Lock()
_last_call = 0.0


@dataclass
class Caption:
    en: str | None
    pt: str | None


def api_key() -> str | None:
    """GEMINI_API_KEY from .env, or the key pasted in the app."""
    from services import caption_settings
    return caption_settings.gemini_key()


def check_key(key: str) -> None:
    """Make sure Google accepts a key before it's saved. Raises
    CaptionSettingsError with a message for the app."""
    from services.caption_settings import CaptionSettingsError

    if not key or len(key) < 20 or any(c.isspace() for c in key):
        raise CaptionSettingsError("Isso não parece uma chave do Gemini. Copie a chave inteira do Google AI Studio.")
    try:
        resp = httpx.get(MODEL_URL.format(model=model()), headers={"x-goog-api-key": key}, timeout=15.0)
    except Exception as e:
        raise CaptionSettingsError(f"Não consegui falar com o Google para conferir a chave ({type(e).__name__}).")
    if resp.status_code in (400, 401, 403):
        raise CaptionSettingsError("O Google recusou essa chave. Confira se copiou a chave inteira do Google AI Studio.")
    if resp.status_code != 200:
        raise CaptionSettingsError(f"O Google não confirmou a chave agora (HTTP {resp.status_code}). Tente de novo.")


def enabled() -> bool:
    return api_key() is not None


def model() -> str:
    return os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL


def _min_interval() -> float:
    try:
        return max(0.0, float(os.environ.get("GEMINI_MIN_INTERVAL_S", DEFAULT_MIN_INTERVAL_S)))
    except ValueError:
        return DEFAULT_MIN_INTERVAL_S


def _clean(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().strip('"').strip()
    return value or None


def parse_reply(text: str) -> Caption | None:
    """The JSON reply as a Caption; None when it isn't the expected JSON."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    en, pt = _clean(data.get("en")), _clean(data.get("pt"))
    return Caption(en, pt if en else None)


def _request(key: str, payload: dict) -> httpx.Response:
    global _last_call
    with _lock:
        wait = _last_call + _min_interval() - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            return httpx.post(
                API_URL.format(model=model()),
                json=payload,
                headers={"x-goog-api-key": key},
                timeout=TIMEOUT_S,
            )
        finally:
            _last_call = time.monotonic()


def caption(audio: bytes, context: dict | None = None, draft: str | None = None) -> Caption | None:
    """English and Portuguese captions for one clip. Caption(None, None) when
    nobody speaks; None if Gemini couldn't do it (no key, network, limits).
    Blocking: run it in a thread."""
    key = api_key()
    if not key:
        return None
    prompt = f"{INSTRUCTIONS}\n\n{_context_text({**(context or {})})}"
    if draft:
        prompt += f"\n\nDraft from speech-to-text: {draft}"
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": prompt},
                {"inline_data": {
                    "mime_type": f"audio/{_audio_format(audio)}",
                    "data": base64.b64encode(audio).decode("ascii"),
                }},
            ],
        }],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 400, "responseMimeType": "application/json"},
    }
    for attempt in range(2):
        try:
            resp = _request(key, payload)
        except Exception as e:
            logger.warning(f"Gemini caption request failed: {type(e).__name__}")
            return None
        if resp.status_code == 429 and attempt == 0:
            logger.info("Gemini free plan limit reached; trying again shortly")
            time.sleep(RETRY_WAIT_S)
            continue
        if resp.status_code != 200:
            logger.warning(f"Gemini caption request failed ({model()}): HTTP {resp.status_code} {resp.text[:200]}")
            return None
        try:
            parts = resp.json()["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError, ValueError):
            # No candidates: blocked or empty audio
            return Caption(None, None)
        result = parse_reply(text)
        if result is None:
            logger.warning(f"Gemini reply wasn't JSON: {text[:200]}")
        return result
    return None
