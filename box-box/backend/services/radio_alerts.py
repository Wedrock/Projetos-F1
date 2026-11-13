"""Push alerts for new team radio from the drivers a device follows."""

from __future__ import annotations

import asyncio
import logging

from services import push

logger = logging.getLogger(__name__)

MAX_BODY = 180


def alert_text(driver: str, transcript: str | None, transcript_pt: str | None) -> tuple[str, str]:
    title = f"📻 Rádio de {driver}"
    body = transcript_pt or transcript or "Nova mensagem de rádio. Toque para ouvir."
    if len(body) > MAX_BODY:
        body = body[: MAX_BODY - 1].rstrip() + "…"
    return title, body


async def notify(session, clip: dict, transcript: str | None, transcript_pt: str | None) -> None:
    """Called once a live clip is captioned (or found to have no caption)."""
    try:
        if not push.push_enabled() or session._state_manager is None or not push.any_follows_radio():
            return
        driver = session._state_manager.radio_driver(clip.get("racing_number", ""))
        if not driver:
            return
        year, rnd, stype = session.key.split("_", 2)
        url = f"/live?year={year}&round={rnd}&type={stype}&tab=radio"
        title, body = alert_text(driver, transcript, transcript_pt)
        sent = await asyncio.to_thread(
            push.broadcast, title, body, url, f"radio-{clip.get('id', '')}", push.follows_radio(driver),
        )
        if sent:
            logger.info("Radio alert for %s sent to %d device(s)", driver, sent)
    except Exception as e:
        logger.warning("Radio alert failed: %s", e)
