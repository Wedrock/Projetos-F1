"""Race alerts: push notifications for the big moments of a live session.

During a session's window (see routers/live_status), and only when some
device turned alerts on, the server keeps the live timing feed open and
watches it for: the start, Safety Car, Virtual Safety Car, red flag, the
restart, a new leader, the last lap and the result.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from services import push

logger = logging.getLogger(__name__)

CHECK_INTERVAL_S = 30
POLL_INTERVAL_S = 2
# A new leader must hold P1 this long before it's announced: positions jump
# around for a moment at pit stops and timing glitches
LEADER_SETTLE_S = 8
# How long after the scheduled end to keep watching (delays, red flags)
OVERRUN_S = 3600

SESSION_LABELS = {
    "R": "Corrida",
    "S": "Sprint",
    "Q": "Classificação",
    "SQ": "Classificação Sprint",
    "FP1": "Treino Livre 1",
    "FP2": "Treino Livre 2",
    "FP3": "Treino Livre 3",
}

_NEUTRALISED = ("sc", "vsc", "red")


def watched_session_types() -> set[str]:
    """PUSH_SESSIONS: comma-separated session types (default race, sprint and
    both qualifyings)."""
    raw = os.environ.get("PUSH_SESSIONS", "").strip()
    if not raw:
        return {"R", "S", "Q", "SQ"}
    return {t.strip().upper() for t in raw.split(",") if t.strip()}


def short_event_name(name: str) -> str:
    return name.replace("Grand Prix", "GP").strip() or "F1"


@dataclass
class Alert:
    title: str
    body: str
    tag: str


class RaceAlertDetector:
    """Turns successive live frames into alerts. Pure: no I/O, easy to test."""

    def __init__(self, session_type: str, event_name: str, key: str = ""):
        self.session_type = session_type
        self.is_race = session_type in ("R", "S")
        self.label = SESSION_LABELS.get(session_type, session_type)
        self.event = short_event_name(event_name)
        self.key = key
        self.started = False
        self.finished = False
        self.track = "green"
        self.leader: str | None = None
        self._candidate: str | None = None
        self._candidate_since = 0.0
        self._last_lap_sent = False

    # -- helpers -------------------------------------------------------

    def _where(self, frame: dict) -> str:
        lap, total = frame.get("lap") or 0, frame.get("total_laps") or 0
        if self.is_race and lap:
            return f"{self.event} · Volta {lap}/{total}" if total else f"{self.event} · Volta {lap}"
        return self.event

    def _alert(self, title: str, body: str, kind: str) -> Alert:
        return Alert(title, body, f"{self.key}-{kind}")

    @staticmethod
    def _ordered(frame: dict) -> list[dict]:
        drivers = [d for d in frame.get("drivers") or [] if d.get("position") and d.get("abbr")]
        return sorted(drivers, key=lambda d: d["position"])

    # -- main ----------------------------------------------------------

    def update(self, frame: dict, session_status: str, now: float) -> list[Alert]:
        if self.finished:
            return []
        alerts: list[Alert] = []
        ordered = self._ordered(frame)
        p1 = ordered[0]["abbr"] if ordered else None

        if not self.started:
            if session_status != "Started":
                return []
            self.started = True
            self.leader = p1
            status = frame.get("status") or "green"
            self.track = status if status in _NEUTRALISED else "green"
            if self.is_race:
                body = f"{self.event} · {p1} sai na pole" if p1 else self.event
                alerts.append(self._alert("🏁 Largada!", body, "start"))
            else:
                alerts.append(self._alert(f"🟢 {self.label} começou", self.event, "start"))
            return alerts

        alerts += self._track_status(frame)
        if self.is_race:
            alerts += self._leader(frame, ordered, p1, now)
            alerts += self._last_lap(frame, ordered)
        alerts += self._finish(frame, session_status, ordered)
        return alerts

    def _track_status(self, frame: dict) -> list[Alert]:
        status = frame.get("status") or "green"
        # Local yellows come and go all the time; they neither alert nor end
        # a neutralisation (SC in, yellow for a moment, then green)
        if status == "yellow" or status == self.track:
            return []
        previous, self.track = self.track, status
        where = self._where(frame)
        if status == "sc":
            return [self._alert("🟡 Safety Car na pista", where, "track")]
        if status == "vsc":
            return [self._alert("🟡 Virtual Safety Car", where, "track")]
        if status == "red":
            return [self._alert("🔴 Bandeira vermelha", f"{where} · sessão interrompida", "track")]
        if status == "green" and previous in _NEUTRALISED:
            title = {
                "sc": "🟢 Safety Car recolhido",
                "vsc": "🟢 Fim do Virtual Safety Car",
                "red": "🟢 Sessão retomada",
            }[previous]
            return [self._alert(title, f"{where} · bandeira verde", "track")]
        return []

    def _leader(self, frame: dict, ordered: list[dict], p1: str | None, now: float) -> list[Alert]:
        if not p1 or not (frame.get("lap") or 0) >= 1:
            return []
        if self.leader is None:
            self.leader = p1
            return []
        if p1 == self.leader:
            self._candidate = None
            return []
        if p1 != self._candidate:
            self._candidate, self._candidate_since = p1, now
            return []
        if now - self._candidate_since < LEADER_SETTLE_S:
            return []
        previous, self.leader, self._candidate = self.leader, p1, None
        return [self._alert(f"🔄 {p1} assume a liderança", f"{self._where(frame)} · à frente de {previous}", "leader")]

    def _last_lap(self, frame: dict, ordered: list[dict]) -> list[Alert]:
        lap, total = frame.get("lap") or 0, frame.get("total_laps") or 0
        if self._last_lap_sent or not total or lap < total or not ordered:
            return []
        self._last_lap_sent = True
        body = f"{self.event} · {ordered[0]['abbr']} lidera"
        if len(ordered) > 1 and ordered[1].get("interval"):
            body += f", {ordered[1]['abbr']} a {str(ordered[1]['interval']).lstrip('+')}s"
        return [self._alert("🏁 Última volta!", body, "lastlap")]

    def _finish(self, frame: dict, session_status: str, ordered: list[dict]) -> list[Alert]:
        if session_status not in ("Finished", "Finalised"):
            return []
        # Qualifying "finishes" between its parts too; only Q3's end counts
        phase = (frame.get("quali_phase") or {}).get("phase")
        if self.session_type in ("Q", "SQ") and phase and phase != "Q3":
            return []
        self.finished = True
        if not ordered:
            return [self._alert(f"🏆 Fim: {self.label}", self.event, "finish")]
        if self.is_race:
            podium = " · ".join(f"{i}º {d['abbr']}" for i, d in enumerate(ordered[:3], 1))
            return [self._alert(f"🏆 Fim: {self.label} · {self.event}", podium, "finish")]
        pole = ordered[0]
        time_str = f" ({pole['best_lap_time']})" if pole.get("best_lap_time") else ""
        title = "🏆 Pole position" if self.session_type in ("Q", "SQ") else f"🏁 Fim do {self.label}"
        return [self._alert(title, f"{self.event} · {pole['abbr']}{time_str}", "finish")]


# -- background loop -------------------------------------------------------

def _live_url(info: dict) -> str:
    return f"/live?year={info['year']}&round={info['round_number']}&type={info['session_type']}"


async def _send(alert: Alert, url: str) -> None:
    try:
        sent = await asyncio.to_thread(push.broadcast, alert.title, alert.body, url, alert.tag)
        logger.info("Race alert sent to %d device(s): %s", sent, alert.title)
    except Exception as e:
        logger.error("Race alert failed: %s", e)


async def _watch(info: dict) -> bool:
    """Watch one session; True once it is over (finished or past its window)."""
    from routers import live
    from routers.live_status import SESSION_DURATIONS

    year, rnd, stype = info["year"], info["round_number"], info["session_type"]
    key = f"{year}_{rnd}_{stype}"
    url = _live_url(info)
    start = datetime.fromisoformat(info["session_start"].replace("Z", "+00:00"))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    deadline = start.timestamp() + SESSION_DURATIONS.get(info.get("session_name", ""), 3600) + OVERRUN_S

    detector = RaceAlertDetector(stype, info.get("event_name", ""), key)
    session, holder = await live.acquire_session(year, rnd, stype)
    logger.info("Watching %s for race alerts", key)
    try:
        while time.time() < deadline and not detector.finished:
            sm = session._state_manager
            if sm is not None:
                frame = session.get_frame()
                if frame:
                    for alert in detector.update(frame, sm.session_status, time.monotonic()):
                        await _send(alert, url)
            await asyncio.sleep(POLL_INTERVAL_S)
    finally:
        await live.release_session(year, rnd, stype, session, holder)
        logger.info("Stopped watching %s", key)
    return True


async def race_alerts_loop() -> None:
    from routers.live_status import live_status

    reminded: set[str] = set()
    done: set[str] = set()
    task: asyncio.Task | None = None

    def _finished(t: asyncio.Task, key: str) -> None:
        # A watch that failed (F1 refused the connection, say) is retried
        if not t.cancelled() and t.exception() is None:
            done.add(key)
        elif not t.cancelled():
            logger.error("Race alerts watch failed: %s", t.exception())

    while True:
        try:
            info = (await live_status()).get("live")
            if info and info.get("session_type") in watched_session_types() and push.subscription_count():
                key = f"{info['year']}_{info['round_number']}_{info['session_type']}"
                url = _live_url(info)
                event = short_event_name(info.get("event_name", ""))
                label = SESSION_LABELS.get(info["session_type"], info["session_type"])

                if key not in reminded:
                    reminded.add(key)
                    if info.get("pre_session"):
                        start = datetime.fromisoformat(info["session_start"].replace("Z", "+00:00"))
                        if start.tzinfo is None:
                            start = start.replace(tzinfo=timezone.utc)
                        minutes = max(1, math.ceil((start - datetime.now(timezone.utc)).total_seconds() / 60))
                        await _send(Alert(f"⏱️ {label} em {minutes} min", event, f"{key}-soon"), url)

                if key not in done and (task is None or task.done()):
                    task = asyncio.create_task(_watch(info))
                    task.add_done_callback(lambda t, k=key: _finished(t, k))
        except asyncio.CancelledError:
            if task is not None:
                task.cancel()
            raise
        except Exception as e:
            logger.error("Race alerts check failed: %s", e)
        await asyncio.sleep(CHECK_INTERVAL_S)
