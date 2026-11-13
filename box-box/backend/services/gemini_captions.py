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
from dataclasses import dataclass, field

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
# Tries per clip: Gemini is often briefly overloaded (503) or rate limited
MAX_ATTEMPTS = 4
# Waits before retrying an overloaded server or a network error (seconds)
BACKOFF_S = (3.0, 8.0, 15.0)
# Team radio is full of swearing: don't let the safety filters drop a clip
SAFETY_OFF = [
    {"category": c, "threshold": "BLOCK_NONE"}
    for c in ("HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
              "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")
]

INSTRUCTIONS = """You caption Formula 1 team radio: short messages between a driver and their race engineer, often with engine noise and a poor signal.

1. Split what is said into lines by who speaks, a new line each time the voice changes:
   - "driver": the driver named as the speaker below (the clip is from their car).
   - "team": the race engineer or anyone else on the pit wall.
   Tell them apart by the voice (the driver's often has engine noise, wind or effort; the engineer's is calm and clear) and by what is said: the team gives information and instructions ("box this lap", "gap to Norris is 1.2", "copy"), the driver reports on the car, the tyres and other drivers. If one person speaks, that's one line.
2. "en" of each line: what is said, in English.
   - The audio decides. A draft from a speech-to-text model may be given; use it only as a hint.
   - Spell driver, team and F1 terms correctly, using the context below. Use British spelling ("tyres").
   - Don't add or explain anything that wasn't said. Keep "copy", "box, box" and swearing.
   - If part is unintelligible, caption the parts you can hear.
3. "pt" of each line: "en" translated into Brazilian Portuguese, as a Brazilian F1 broadcast would say it.
   - Natural and short, like a subtitle. Keep the tone, including swearing.
   - Keep terms Brazilians use in English: box, pit, pit stop, safety car, VSC, undercut, overcut, delta, DRS. "Copy" becomes "entendido". "Tyres" becomes "pneus"; softs/mediums/hards become macios/médios/duros.
   - Keep names as they are.

If nobody speaks, lines is empty.
Reply with JSON only: {"lines": [{"who": "team", "en": "...", "pt": "..."}, {"who": "driver", "en": "...", "pt": "..."}]} or {"lines": []}."""

_lock = threading.Lock()
_last_call = 0.0


@dataclass
class Caption:
    en: str | None
    pt: str | None
    # Who said what: [{"who": "driver" | "team", "en": ..., "pt": ...}]
    lines: list[dict] = field(default_factory=list)


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
    """The JSON reply as a Caption; None when it isn't the expected JSON.

    Takes the reply split by speaker ({"lines": [...]}) and the older single
    caption ({"en": ..., "pt": ...})."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("lines"), list):
        lines = []
        for item in data["lines"]:
            if not isinstance(item, dict):
                continue
            en, pt = _clean(item.get("en")), _clean(item.get("pt"))
            if not en:
                continue
            who = "driver" if str(item.get("who", "")).strip().lower() == "driver" else "team"
            if lines and lines[-1]["who"] == who:
                # Same voice twice in a row: one line
                lines[-1]["en"] += " " + en
                lines[-1]["pt"] = " ".join(x for x in (lines[-1]["pt"], pt) if x) or None
            else:
                lines.append({"who": who, "en": en, "pt": pt})
        if not lines:
            return Caption(None, None)
        en = " ".join(l["en"] for l in lines)
        pts = [l["pt"] for l in lines if l["pt"]]
        return Caption(en, " ".join(pts) if pts else None, lines)
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


def _retry_delay(resp) -> float:
    """How long Google asks us to wait after a 429 (its RetryInfo), capped."""
    try:
        for detail in resp.json().get("error", {}).get("details", []):
            delay = str(detail.get("retryDelay", ""))
            if delay.endswith("s"):
                return min(60.0, max(1.0, float(delay[:-1])))
    except Exception:
        pass
    return RETRY_WAIT_S


def _generate(key: str, payload: dict) -> tuple[str, str | None]:
    """Send a request, retrying what's worth retrying. Returns ("ok", text),
    ("empty", None) when Gemini answered with nothing to say, or
    ("fail", None) when it couldn't answer (network, limits, blocked)."""
    for attempt in range(MAX_ATTEMPTS):
        last = attempt == MAX_ATTEMPTS - 1
        backoff = BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)]
        try:
            resp = _request(key, payload)
        except Exception as e:
            logger.warning(f"Gemini request failed: {type(e).__name__}")
            if last:
                return "fail", None
            time.sleep(backoff)
            continue
        if resp.status_code == 429:
            if last:
                logger.warning("Gemini free plan limit reached; giving up on this clip for now")
                return "fail", None
            wait = _retry_delay(resp)
            logger.info(f"Gemini free plan limit reached; trying again in {wait:.0f}s")
            time.sleep(wait)
            continue
        if resp.status_code >= 500:
            logger.info(f"Gemini busy (HTTP {resp.status_code}); trying again in {backoff:.0f}s")
            if last:
                return "fail", None
            time.sleep(backoff)
            continue
        if resp.status_code != 200:
            logger.warning(f"Gemini request failed ({model()}): HTTP {resp.status_code} {resp.text[:200]}")
            return "fail", None
        body = None
        try:
            body = resp.json()
            parts = body["candidates"][0]["content"]["parts"]
            return "ok", "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError, ValueError):
            reason = (body.get("promptFeedback") or {}).get("blockReason") if isinstance(body, dict) else None
            finish = None
            try:
                finish = body["candidates"][0].get("finishReason")
            except Exception:
                pass
            if reason or (finish and finish != "STOP"):
                # Blocked or cut off: not "nobody speaks", so don't record it as silence
                logger.warning(f"Gemini returned nothing (block: {reason}, finish: {finish})")
                if last:
                    return "fail", None
                time.sleep(backoff)
                continue
            return "empty", None
    return "fail", None


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
        "generationConfig": {"temperature": 0, "maxOutputTokens": 800, "responseMimeType": "application/json"},
        "safetySettings": SAFETY_OFF,
    }
    for attempt in range(2):  # a second go if the reply isn't JSON
        status, text = _generate(key, payload)
        if status == "fail":
            return None
        if status == "empty":
            return Caption(None, None)
        result = parse_reply(text or "")
        if result is not None:
            return result
        logger.warning(f"Gemini reply wasn't JSON: {(text or '')[:200]}")
    return None


TRANSLATE_INSTRUCTIONS = """Translate this Formula 1 team radio caption into Brazilian Portuguese, as a Brazilian F1 broadcast would say it.
- Natural and short, like a subtitle. Keep the tone, including swearing.
- Keep terms Brazilians use in English: box, pit, pit stop, safety car, VSC, undercut, overcut, delta, DRS. "Copy" becomes "entendido". "Tyres" becomes "pneus"; softs/mediums/hards become macios/médios/duros.
- Keep names as they are. Don't add or explain anything.
Reply with the translation only."""


def translate(english: str, context: dict | None = None) -> str | None:
    """Portuguese for an English caption (text only), for clips Gemini
    couldn't caption from the audio. None if it couldn't."""
    key = api_key()
    if not key or not (english or "").strip():
        return None
    prompt = f"{TRANSLATE_INSTRUCTIONS}\n\n{_context_text({**(context or {})})}\n\nCaption: {english.strip()}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 400},
        "safetySettings": SAFETY_OFF,
    }
    status, text = _generate(key, payload)
    return _clean(text) if status == "ok" else None
