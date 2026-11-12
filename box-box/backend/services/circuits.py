"""Circuit names and outlines for the session picker.

Each round's circuit is found through the public OpenF1 meetings list, and its
outline comes from the MultiViewer circuit API (the same source FastF1's
get_circuit_info uses). Both are fetched by this server once and stored, so
the browser never contacts either site.
"""

from __future__ import annotations

import logging
import math
import time
from datetime import date

import httpx

from services import storage

logger = logging.getLogger(__name__)

OPENF1 = "https://api.openf1.org/v1"
MULTIVIEWER = "https://api.multiviewer.app/api/v1/circuits"
HEADERS = {"User-Agent": "F1ReplayTiming (self-hosted)"}
TIMEOUT = 30.0
VERSION = 1
MAX_POINTS = 220

# OpenF1 circuit short name -> official circuit name
CIRCUIT_NAMES = {
    "Sakhir": "Bahrain International Circuit",
    "Jeddah": "Jeddah Corniche Circuit",
    "Melbourne": "Albert Park Circuit",
    "Suzuka": "Suzuka International Racing Course",
    "Shanghai": "Shanghai International Circuit",
    "Miami": "Miami International Autodrome",
    "Imola": "Autodromo Enzo e Dino Ferrari",
    "Monte Carlo": "Circuit de Monaco",
    "Monaco": "Circuit de Monaco",
    "Catalunya": "Circuit de Barcelona-Catalunya",
    "Barcelona": "Circuit de Barcelona-Catalunya",
    "Montreal": "Circuit Gilles Villeneuve",
    "Spielberg": "Red Bull Ring",
    "Silverstone": "Silverstone Circuit",
    "Hungaroring": "Hungaroring",
    "Spa-Francorchamps": "Circuit de Spa-Francorchamps",
    "Zandvoort": "Circuit Zandvoort",
    "Monza": "Autodromo Nazionale Monza",
    "Baku": "Baku City Circuit",
    "Singapore": "Marina Bay Street Circuit",
    "Austin": "Circuit of the Americas",
    "Mexico City": "Autódromo Hermanos Rodríguez",
    "Interlagos": "Autódromo José Carlos Pace (Interlagos)",
    "Las Vegas": "Las Vegas Strip Circuit",
    "Lusail": "Lusail International Circuit",
    "Yas Marina Circuit": "Yas Marina Circuit",
    "Yas Island": "Yas Marina Circuit",
    "Madrid": "Madring",
}


def _get_json(url: str, params: dict | None = None):
    r = httpx.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def _outline(x: list[float], y: list[float], rotation: float) -> list[list[float]]:
    """Rotate as the broadcast shows it, fit into 0-1 (keeping the shape) and
    thin out to at most MAX_POINTS. Screen coordinates (y down)."""
    if not x or len(x) != len(y):
        return []
    rad = math.radians(rotation)
    c, s = math.cos(rad), math.sin(rad)
    pts = [(xi * c - yi * s, xi * s + yi * c) for xi, yi in zip(x, y)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y) or 1.0
    off_x = (span - (max_x - min_x)) / 2
    off_y = (span - (max_y - min_y)) / 2
    step = max(1, len(pts) // MAX_POINTS)
    out = []
    for px, py in pts[::step]:
        nx = (px - min_x + off_x) / span
        ny = 1 - (py - min_y + off_y) / span  # data is y-up
        out.append([round(nx, 4), round(ny, 4)])
    return out


def _shape(circuit_key: int, year: int) -> dict | None:
    """A circuit's outline, stored per circuit and reused across seasons."""
    path = f"circuits/shapes/{circuit_key}.json"
    cached = storage.get_json(path)
    if cached and cached.get("points"):
        return cached
    for y in (year, year - 1, year - 2):
        try:
            data = _get_json(f"{MULTIVIEWER}/{circuit_key}/{y}")
        except Exception as e:
            logger.info(f"No MultiViewer outline for circuit {circuit_key} ({y}): {e}")
            continue
        if data and data.get("x"):
            shape = {
                "points": _outline(data["x"], data["y"], float(data.get("rotation") or 0)),
                "corners": len(data.get("corners") or []),
            }
            storage.put_json(path, shape)
            return shape
    return None


def season_circuits(year: int, events: list[dict], force: bool = False) -> dict:
    """{round: {name, short_name, location, points, corners}} for a season."""
    path = f"circuits/{year}.json"
    cached = None if force else storage.get_json(path)
    if cached and cached.get("version") == VERSION and (
        len(cached.get("rounds", {})) >= len(events)
        or time.time() - cached.get("built", 0) < 24 * 3600  # new rounds appear on OpenF1 later
    ):
        return cached

    meetings = []
    try:
        meetings = _get_json(f"{OPENF1}/meetings", {"year": year}) or []
    except Exception as e:
        logger.warning(f"OpenF1 meetings for {year} unavailable: {e}")
    meetings = [m for m in meetings if "test" not in str(m.get("meeting_name", "")).lower()]

    rounds: dict[str, dict] = dict((cached or {}).get("rounds", {}))
    for evt in events:
        rnd = str(evt.get("round_number"))
        if rnd in rounds and rounds[rnd].get("points"):
            continue
        try:
            race_day = date.fromisoformat(str(evt.get("event_date"))[:10])
        except ValueError:
            continue
        match = None
        for m in meetings:
            try:
                start = date.fromisoformat(m["date_start"][:10])
                end = date.fromisoformat(m["date_end"][:10])
            except (KeyError, ValueError):
                continue
            if start <= race_day <= end:
                match = m
                break
        if match is None:
            continue
        short = match.get("circuit_short_name") or ""
        entry = {
            "short_name": short,
            "name": CIRCUIT_NAMES.get(short, short),
            "location": match.get("location"),
            "circuit_key": match.get("circuit_key"),
            "points": [],
            "corners": 0,
        }
        if match.get("circuit_key") is not None:
            shape = _shape(int(match["circuit_key"]), year)
            if shape:
                entry["points"] = shape["points"]
                entry["corners"] = shape.get("corners", 0)
        rounds[rnd] = entry

    result = {"version": VERSION, "year": year, "built": time.time(), "rounds": rounds}
    if rounds:
        storage.put_json(path, result)
    return result
