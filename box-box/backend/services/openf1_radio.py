"""Team radio from OpenF1, for sessions downloaded without an F1 TV sign-in.

OpenF1 lists the clips F1 picked for the world feed, with a link to F1's
public MP3. Its `date` is when the clip was published, up to a minute late;
the file name carries the local time it was recorded
(NOR_1_20261108_132915.mp3), so that is used with the session's UTC offset.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from services.openf1_source import _get

logger = logging.getLogger(__name__)

_NAME_TIME = re.compile(r"_(\d{8})_(\d{6})\.mp3$")
_OFFSET = re.compile(r"^(-)?(\d{1,2}):(\d{2})(?::(\d{2}))?$")


def _offset(value: str | None) -> timedelta | None:
    m = _OFFSET.match(str(value or "").strip())
    if not m:
        return None
    sign = -1 if m.group(1) else 1
    return sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3)), seconds=int(m.group(4) or 0))


def recorded_utc(url: str, published: str | None, gmt_offset: str | None) -> str | None:
    """When the clip was recorded, as F1's Utc string ("...Z")."""
    offset = _offset(gmt_offset)
    m = _NAME_TIME.search(url or "")
    if m and offset is not None:
        try:
            local = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
            when = local - offset
            # Trust the name unless it's far from the publish time (a wrong offset)
            if published:
                pub = datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
                if abs((pub - when).total_seconds()) > 3 * 3600:
                    when = pub
            return when.isoformat() + "Z"
        except ValueError:
            pass
    if published:
        try:
            pub = datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone(timezone.utc)
            return pub.replace(tzinfo=None).isoformat() + "Z"
        except ValueError:
            return None
    return None


def captures_for(session_key: int) -> list[dict]:
    """The session's clips as F1 TeamRadio captures, with the full MP3 link
    in "Url" (build_clips uses it in place of the session path)."""
    rows = _get("team_radio", {"session_key": session_key})
    sessions = _get("sessions", {"session_key": session_key})
    gmt_offset = (sessions[0] if sessions else {}).get("gmt_offset")
    captures = []
    for row in rows:
        url = row.get("recording_url")
        if not url or not str(url).startswith("https://"):
            continue
        utc = recorded_utc(url, row.get("date"), gmt_offset)
        if not utc:
            continue
        captures.append({
            "Utc": utc,
            "RacingNumber": str(row.get("driver_number", "")),
            "Path": url.rsplit("/", 1)[-1],
            "Url": url,
        })
    logger.info("OpenF1 has %d team radio clips for session %s", len(captures), session_key)
    return captures
