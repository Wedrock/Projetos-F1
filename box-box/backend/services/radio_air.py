"""When the F1 TV broadcast plays each team radio clip.

The world feed airs a clip some seconds (sometimes minutes) after it was
recorded, and not every clip makes it on air. For each clip, the broadcast's
audio just after the clip's time is searched for the clip itself (normalised
cross-correlation of the speech band), so the app can play its own copy of
the clip, captioned, at the moment the broadcast does, with the broadcast
turned down.

Times are replay seconds. The broadcast sync (broadcast_sync) gives the
video time of the replay's 0:00, so video time = replay time + offset.
Worked out once per session in the background and stored next to it.
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from typing import Any

import numpy as np

from services import broadcast_sync, f1tv_video
from services.storage import aget_json, get_bytes, put_json

logger = logging.getLogger(__name__)

VERSION = 1
SR = broadcast_sync._SR  # the broadcast audio comes decoded at this rate
# How long after a clip's time the broadcast may air it, and a little before
LOOK_BEFORE_S = 3.0
LOOK_AFTER_S = 150.0
# Broadcast audio fetched in pieces of at most this long
MAX_CHUNK_S = 20 * 60
# A match counts when the correlation is this strong and stands well above
# the rest of the window
MIN_SCORE = 0.2
MIN_PROMINENCE = 20.0
SPEECH_BAND = (300.0, 3400.0)

_running: dict[str, asyncio.Task] = {}
_failed: dict[str, tuple[str, float]] = {}
_RETRY_AFTER_S = 30 * 60


def clip_key(clip: dict) -> str:
    return f"{clip.get('t')}_{clip.get('racing_number')}"


def _path(year: int, round_num: int, session_type: str) -> str:
    return f"sessions/{year}/{round_num}/{session_type}/team_radio_air.json"


# --- Matching ---------------------------------------------------------------

def _band(x: np.ndarray, lo: float = SPEECH_BAND[0], hi: float = SPEECH_BAND[1]) -> np.ndarray:
    """The speech band only: radio voices, not engines or crowd rumble."""
    n = len(x)
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    spec[(freqs < lo) | (freqs > hi)] = 0
    return np.fft.irfft(spec, n).astype(np.float32)


def find(clip: np.ndarray, broadcast: np.ndarray) -> tuple[int, float, float] | None:
    """Where clip best matches inside broadcast: (sample index, score,
    prominence). Score is the normalised cross-correlation (1 = identical);
    prominence is how far the best match stands above the typical one."""
    m, n = len(clip), len(broadcast)
    if m < SR // 2 or n < m:
        return None
    c = _band(clip)
    b = _band(broadcast)
    c = c - c.mean()
    c_norm = float(np.sqrt(np.sum(c * c)))
    if c_norm == 0:
        return None
    size = 1 << int(np.ceil(np.log2(n + m)))
    corr = np.fft.irfft(np.fft.rfft(b, size) * np.conj(np.fft.rfft(c, size)), size)[: n - m + 1]
    # Energy of each broadcast window the clip is compared with
    cum = np.concatenate([[0.0], np.cumsum(b.astype(np.float64) ** 2)])
    energy = np.sqrt(np.maximum(cum[m:] - cum[:-m], 1e-12))
    ncc = corr / (energy * c_norm)
    best = int(np.argmax(ncc))
    score = float(ncc[best])
    typical = float(np.median(np.abs(ncc))) or 1e-9
    return best, score, score / typical


def _decode_clip(audio: bytes) -> np.ndarray | None:
    import av

    try:
        container = av.open(io.BytesIO(audio))
        resampler = av.AudioResampler(format="flt", layout="mono", rate=SR)
        out = []
        for frame in container.decode(audio=0):
            out.extend(f.to_ndarray().reshape(-1) for f in resampler.resample(frame))
        return np.concatenate(out) if out else None
    except Exception as e:
        logger.info("Couldn't decode a team radio clip: %s", e)
        return None


def _chunks(times: list[float], offset: float) -> list[tuple[float, float]]:
    """Video-time stretches covering every clip's window, merged, in pieces
    of at most MAX_CHUNK_S."""
    spans = sorted((t + offset - LOOK_BEFORE_S, t + offset + LOOK_AFTER_S) for t in times)
    merged: list[list[float]] = []
    for a, b in spans:
        if merged and a <= merged[-1][1] and b - merged[-1][0] <= MAX_CHUNK_S:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(max(0.0, a), b) for a, b in merged]


# --- Session ----------------------------------------------------------------

def _clip_audio(base: str, clip: dict) -> bytes | None:
    from services import team_radio

    if clip.get("audio"):
        found = get_bytes(f"{base}/team_radio/{clip['audio']}")
        if found:
            return found[0]
    return team_radio.fetch_audio(clip["url"]) if clip.get("url") else None


async def _compute(year: int, round_num: int, session_type: str) -> dict[str, Any]:
    base = f"sessions/{year}/{round_num}/{session_type}"
    clips = [c for c in ((await aget_json(f"{base}/team_radio.json")) or {}).get("clips") or []
             if c.get("t") is not None and (c.get("audio") or c.get("url"))]
    if not clips:
        raise RuntimeError("This session has no team radio")
    sync = await broadcast_sync.offset(year, round_num, session_type)
    offset = float(sync["offset"])
    play = await f1tv_video.play(sync["content_id"])  # the world feed

    air: dict[str, float] = {}
    checked = 0
    for start, end in _chunks([float(c["t"]) for c in clips], offset):
        try:
            pcm, pcm_start = await broadcast_sync._audio(play["manifest_url"], start, end)
        except RuntimeError as e:
            if "encrypted" in str(e):
                raise broadcast_sync.AudioProtected("F1 TV encrypts the broadcast's sound") from e
            raise
        for clip in clips:
            t = float(clip["t"])
            lo, hi = t + offset - LOOK_BEFORE_S, t + offset + LOOK_AFTER_S
            if lo < start - 1 or hi > end + 1:
                continue
            audio = await asyncio.to_thread(_clip_audio, base, clip)
            samples = await asyncio.to_thread(_decode_clip, audio) if audio else None
            if samples is None:
                continue
            checked += 1
            i0 = max(0, int((lo - pcm_start) * SR))
            i1 = min(len(pcm), int((hi - pcm_start) * SR) + len(samples))
            found = await asyncio.to_thread(find, samples, pcm[i0:i1])
            if not found:
                continue
            index, score, prominence = found
            if score >= MIN_SCORE and prominence >= MIN_PROMINENCE:
                aired_video = pcm_start + (i0 + index) / SR
                air[clip_key(clip)] = round(aired_video - offset, 2)
                logger.info("Radio %s aired %.1fs after it was recorded (score %.2f)",
                            clip_key(clip), aired_video - offset - t, score)
    logger.info("Team radio on the broadcast: %d of %d clips found", len(air), checked)
    return {"version": VERSION, "status": "ready", "content_id": sync["content_id"],
            "offset": offset, "checked": checked, "air": air}


async def airtimes(year: int, round_num: int, session_type: str) -> dict[str, Any]:
    """{"status": "ready", "air": {clip key: replay time it airs}} once worked
    out; {"status": "working"} while it is; {"status": "protected"} when F1
    TV encrypts the broadcast's sound, so it can't be."""
    path = _path(year, round_num, session_type)
    saved = await aget_json(path)
    if saved and saved.get("version") == VERSION and saved.get("status") in ("ready", "protected"):
        return saved
    failed = _failed.get(path)
    if failed and time.time() - failed[1] < _RETRY_AFTER_S:
        return {"status": "failed", "detail": failed[0]}
    if path not in _running:
        async def run():
            try:
                result = await _compute(year, round_num, session_type)
            except broadcast_sync.AudioProtected as e:
                result = {"version": VERSION, "status": "protected", "detail": str(e)}
            except Exception as e:
                logger.info("Team radio air times for %s %s %s: %s", year, round_num, session_type, e)
                _failed[path] = (str(e), time.time())
                return
            finally:
                _running.pop(path, None)
            await asyncio.to_thread(put_json, path, result)
        _running[path] = asyncio.create_task(run())
    return {"status": "working"}

