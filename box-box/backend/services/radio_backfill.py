"""Fill in team radio for a session that's already been processed.

- No clips (downloaded from OpenF1 before it read team radio, or without an
  F1 TV sign-in): the list comes from OpenF1, timed against the replay.
- Clips without a Portuguese caption split by who speaks (Gemini turned on
  later, or captioned before lines came in): each gets captioned, and the file is saved after every clip so the page can show
  them as they come.

One session at a time, in a background thread; the page polls status().
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from services import gemini_captions, team_radio
from services.storage import get_bytes, get_json, put_json

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def _key(year: int, round_num: int, session_type: str) -> str:
    return f"{year}_{round_num}_{session_type}"


def status(year: int, round_num: int, session_type: str) -> dict:
    with _lock:
        job = _jobs.get(_key(year, round_num, session_type))
        return dict(job) if job else {"running": False}


def _pending(c: dict) -> bool:
    """With Gemini: whether a clip still lacks its Portuguese caption split
    by who speaks."""
    if c.get("lines"):
        return False
    # English only (Gemini couldn't caption the audio): at least translate it
    if c.get("transcript") and not c.get("transcript_pt"):
        return True
    if c.get("lines_tried"):
        return False
    # Marked silent though Whisper heard words: likely blocked by Gemini's
    # filters before they were turned off, so try once more
    if c.get("no_speech") and not c.get("transcript"):
        return False
    # Captioned before lines came in
    return True


def needs_work(clips: list[dict]) -> int:
    """Clips still missing the captions this server can make."""
    if not team_radio.captions_enabled():
        return 0
    if gemini_captions.enabled():
        return sum(1 for c in clips if _pending(c))
    return sum(1 for c in clips if not c.get("transcript") and not c.get("no_speech"))


def start(year: int, round_num: int, session_type: str) -> dict:
    key = _key(year, round_num, session_type)
    with _lock:
        job = _jobs.get(key)
        if job and job.get("running"):
            return dict(job)
        if any(j.get("running") for j in _jobs.values()):
            return {"running": False, "error": "Já estou completando os rádios de outra sessão. Tente daqui a pouco."}
        _jobs[key] = {"running": True, "done": 0, "total": 0, "step": "Buscando os rádios..."}
    threading.Thread(target=_run, args=(year, round_num, session_type), daemon=True).start()
    return status(year, round_num, session_type)


def _update(key: str, **fields) -> None:
    with _lock:
        _jobs[key].update(fields)


def _drivers(info: dict) -> dict[str, dict]:
    out = {}
    for d in info.get("drivers") or []:
        number = str(d.get("driver_number", ""))
        if not number:
            continue
        full = str(d.get("full_name") or "")
        out[number] = {
            "abbr": d.get("abbreviation", ""),
            "first_name": full.split(" ")[0] if full else None,
            "name": full or None,
            "team": d.get("team_name") or None,
        }
    return out


def _clips_from_openf1(year: int, round_num: int, session_type: str, info: dict, base: str) -> list[dict]:
    import pandas as pd

    from services import openf1_radio, openf1_source

    start_utc = info.get("replay_start_utc")
    if not start_utc:
        raise RuntimeError("Esta sessão foi baixada antes de guardar o horário do replay. Reprocesse a sessão.")
    start_date = datetime.fromtimestamp(float(start_utc), tz=timezone.utc).replace(tzinfo=None)
    session_key = openf1_source.find_session_key(year, session_type, pd.Timestamp(start_date), info.get("country") or None)
    captures = openf1_radio.captures_for(session_key)
    label = f"{year} {info.get('event_name', '')}".strip()
    return team_radio.build_clips(
        captures, "", start_date, _drivers(info), year=year, session=label,
        store_prefix=None, with_captions=False,
    )


def _audio(base: str, clip: dict) -> bytes | None:
    if clip.get("audio"):
        found = get_bytes(f"{base}/team_radio/{clip['audio']}")
        if found:
            return found[0]
    return team_radio.fetch_audio(clip["url"]) if clip.get("url") else None


def _run(year: int, round_num: int, session_type: str) -> None:
    key = _key(year, round_num, session_type)
    base = f"sessions/{year}/{round_num}/{session_type}"
    try:
        info = get_json(f"{base}/info.json") or {}
        data = get_json(f"{base}/team_radio.json") or {}
        clips = data.get("clips") or []
        if not clips:
            clips = _clips_from_openf1(year, round_num, session_type, info, base)
            data = {"clips": clips}
            put_json(f"{base}/team_radio.json", data)
            if not clips:
                _update(key, running=False, step="O OpenF1 não tem rádios desta sessão.")
                return

        todo = [c for c in clips if needs_work([c])]
        _update(key, total=len(todo), step="Legendando os rádios...")
        drivers = _drivers(info)
        roster = [team_radio._driver_label(d) for d in drivers.values() if d.get("abbr")]
        label = f"{year} {info.get('event_name', '')}".strip()
        failures = 0
        for i, clip in enumerate(todo, 1):
            if gemini_captions.enabled() and clip.get("lines_tried") and clip.get("transcript"):
                # Gemini already listened and couldn't caption it: translate the English
                drv = drivers.get(clip.get("racing_number", ""), {})
                pt = gemini_captions.translate(clip["transcript"], {
                    "speaker": team_radio._driver_label(drv) if drv else None, "drivers": roster, "session": label,
                })
                if pt:
                    clip["transcript_pt"] = pt
                    put_json(f"{base}/team_radio.json", data)
                _update(key, done=i)
                continue
            audio = _audio(base, clip)
            if audio:
                drv = drivers.get(clip.get("racing_number", ""), {})
                context = {
                    "speaker": team_radio._driver_label(drv) if drv else None,
                    "drivers": roster,
                    "session": label,
                }
                if gemini_captions.enabled():
                    result = gemini_captions.caption(audio, {**context, "year": year}, clip.get("transcript"))
                    if result is None and clip.get("transcript"):
                        # Couldn't caption the audio: Portuguese from the English at least
                        pt = gemini_captions.translate(clip["transcript"], {**context, "year": year})
                        if pt:
                            clip["transcript_pt"] = pt
                            clip["lines_tried"] = True
                            result = False  # handled
                    if result is None:
                        failures += 1
                        if failures >= 3:
                            raise RuntimeError("O Gemini não está respondendo (talvez o limite diário do plano grátis). "
                                               "Tente de novo mais tarde; o que já foi legendado ficou salvo.")
                    elif result is not False:
                        failures = 0
                        if result.en:
                            clip["transcript"] = result.en if result.lines else (clip.get("transcript") or result.en)
                            clip["transcript_pt"] = result.pt
                            if result.lines:
                                clip["lines"] = result.lines
                            else:
                                clip["lines_tried"] = True  # answered without lines: don't ask again
                        elif clip.get("transcript"):
                            # Gemini hears nobody, Whisper did: keep Whisper's words, in Portuguese
                            clip["lines_tried"] = True
                            clip["transcript_pt"] = clip.get("transcript_pt") or gemini_captions.translate(
                                clip["transcript"], {**context, "year": year})
                        else:
                            clip["no_speech"] = True  # nobody speaks: don't ask again
                else:
                    en, _pt = team_radio.caption_both(audio, drv.get("first_name"), year, context)
                    if en:
                        clip["transcript"] = en
                put_json(f"{base}/team_radio.json", data)
            _update(key, done=i)
        _update(key, running=False, step="Pronto")
    except Exception as e:
        logger.warning("Team radio backfill failed for %s: %s", key, e)
        _update(key, running=False, error=str(e) or "Não deu para completar os rádios.")
