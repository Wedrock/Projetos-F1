"""OpenF1 as a data source for FastF1, for sessions downloaded without F1 TV.

Since 15 October 2026 F1's own timing archive needs an F1 TV sign-in. The
public OpenF1 API (https://openf1.org) keeps a free copy of the historical
data (2023 onwards) without one. This module downloads a session from OpenF1
and feeds it to FastF1 by standing in for the handful of `fastf1._api`
functions that read F1's raw feed. FastF1 then builds laps, telemetry and
everything else exactly as it does from F1's data, so the rest of the app
(replay frames, track map, telemetry, tyre model...) works unchanged.

Only sessions registered here (by FastF1 `api_path`) are served from OpenF1;
every other call goes to the original functions.

OpenF1 has no car positions or telemetry for sessions after F1's paywall, so
those still need F1 TV: `SessionNotOnOpenF1` says so.

OpenF1's data is CC BY-NC-SA 4.0: for personal, non-commercial use.
"""

from __future__ import annotations

import datetime
import gzip
import json
import logging
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Callable

import httpx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

API = "https://api.openf1.org/v1"
TIMEOUT = 180.0
MIN_REQUEST_GAP = 0.4  # seconds between requests, to stay well inside the free tier
MAX_RETRIES = 5

# FastF1 session type code -> OpenF1 session names (sprint qualifying was
# "Sprint Shootout" in 2023)
SESSION_NAMES = {
    "R": ("Race",),
    "Q": ("Qualifying",),
    "S": ("Sprint",),
    "SQ": ("Sprint Qualifying", "Sprint Shootout"),
    "FP1": ("Practice 1",),
    "FP2": ("Practice 2",),
    "FP3": ("Practice 3",),
}

TRACK_STATUS_MESSAGES = {
    "1": "AllClear", "2": "Yellow", "4": "SCDeployed",
    "5": "Red", "6": "VSCDeployed", "7": "VSCEnding",
}


class SessionNotOnOpenF1(Exception):
    """OpenF1 doesn't have (enough of) this session. Shown to the user as is."""


# ---------------------------------------------------------------------------
# HTTP client with a disk cache
# ---------------------------------------------------------------------------

_request_lock = threading.Lock()
_last_request = 0.0


def _cache_root() -> Path:
    data_dir = Path(os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data")))
    return data_dir / "openf1-cache"


def _get(endpoint: str, params: dict, cache_dir: Path | None = None, cache_name: str | None = None) -> list[dict]:
    """GET an OpenF1 endpoint. 'No results' is an empty list, not an error."""
    global _last_request
    cache_file = cache_dir / f"{cache_name}.json.gz" if cache_dir and cache_name else None
    if cache_file and cache_file.is_file():
        with gzip.open(cache_file, "rt", encoding="utf-8") as f:
            return json.load(f)

    # OpenF1 filters like date>... go in the query string as written
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{API}/{endpoint}?{query}"
    delay = 2.0
    for attempt in range(MAX_RETRIES):
        with _request_lock:
            wait = MIN_REQUEST_GAP - (time.monotonic() - _last_request)
            if wait > 0:
                time.sleep(wait)
            _last_request = time.monotonic()
        try:
            r = httpx.get(url, timeout=TIMEOUT, headers={"Accept": "application/json"})
        except httpx.HTTPError as e:
            logger.warning(f"OpenF1 {endpoint}: {e} (attempt {attempt + 1})")
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code == 404:
            data: list[dict] = []
            break
        if r.status_code in (429, 500, 502, 503, 504):
            logger.warning(f"OpenF1 {endpoint}: HTTP {r.status_code} (attempt {attempt + 1})")
            time.sleep(delay)
            delay *= 2
            continue
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):  # {"detail": "No results found."}
            data = []
        break
    else:
        raise SessionNotOnOpenF1("O OpenF1 não respondeu. Tente de novo em alguns minutos.")

    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_file.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, cache_file)
    return data


def find_session_key(year: int, session_type: str, session_date: pd.Timestamp | None, country: str | None) -> int:
    """The OpenF1 session for a FastF1 session, matched by name and date."""
    names = SESSION_NAMES.get(session_type)
    if not names:
        raise SessionNotOnOpenF1(f"Tipo de sessão sem suporte no OpenF1: {session_type}")
    candidates = [s for s in _get("sessions", {"year": year}) if s.get("session_name") in names]
    if not candidates:
        raise SessionNotOnOpenF1("Esta sessão não está no OpenF1.")
    if session_date is not None and not pd.isna(session_date):
        target = pd.Timestamp(session_date)
        target = target.tz_localize("UTC") if target.tzinfo is None else target.tz_convert("UTC")

        def dist(s):
            return abs((pd.Timestamp(s["date_start"]).tz_convert("UTC") - target).total_seconds())
        best = min(candidates, key=dist)
        if dist(best) <= 36 * 3600:
            return int(best["session_key"])
    if country:
        by_country = [s for s in candidates if str(s.get("country_name", "")).lower() == country.lower()]
        if len(by_country) == 1:
            return int(by_country[0]["session_key"])
    raise SessionNotOnOpenF1("Não foi possível encontrar esta sessão no OpenF1.")


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _dates(values) -> pd.DatetimeIndex:
    """ISO strings -> naive UTC timestamps (FastF1 works in naive UTC)."""
    return pd.to_datetime(pd.Series(values, dtype="object"), utc=True, format="ISO8601").dt.tz_localize(None)


def _td(seconds) -> pd.Timedelta:
    if seconds is None or (isinstance(seconds, float) and np.isnan(seconds)):
        return pd.NaT
    return pd.Timedelta(seconds=float(seconds))


def _fmt_gap(value) -> str | None:
    """OpenF1 gap (seconds, or '+1 LAP') -> F1's GapToLeader string."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return f"+{value:.3f}"
    s = str(value).strip().upper()
    if "LAP" in s:
        digits = "".join(ch for ch in s if ch.isdigit()) or "1"
        return f"{digits}L"
    return s if s.startswith("+") else f"+{s}"


# ---------------------------------------------------------------------------
# One session's data, in the shapes fastf1._api returns
# ---------------------------------------------------------------------------

class OpenF1Session:
    def __init__(self, api_path: str, session_key: int, session_type: str, on_status: Callable[[str], None] | None = None):
        self.api_path = api_path
        self.session_key = session_key
        self.session_type = session_type
        self.cache_dir = _cache_root() / str(session_key)
        self._status = on_status or (lambda m: None)

    # -- download ----------------------------------------------------------

    def _fetch(self, endpoint: str, cache_name: str | None = None, **params) -> list[dict]:
        return _get(endpoint, {"session_key": self.session_key, **params}, self.cache_dir, cache_name or endpoint)

    def download(self) -> None:
        self._status("Baixando a sessão do OpenF1...")
        self.session = (self._fetch("sessions") or [{}])[0]
        self.drivers = self._fetch("drivers")
        if not self.drivers:
            raise SessionNotOnOpenF1("O OpenF1 não tem dados desta sessão.")
        self.laps = self._fetch("laps")
        self.pits = self._fetch("pit")
        self.stints = self._fetch("stints")
        self.race_control = self._fetch("race_control")
        self.weather = self._fetch("weather")
        self.intervals = self._fetch("intervals") if self.session_type in ("R", "S") else []
        self.positions = self._fetch("position")
        self.results = self._fetch("session_result")

        self.car: dict[str, list[dict]] = {}
        self.loc: dict[str, list[dict]] = {}
        numbers = sorted({str(d["driver_number"]) for d in self.drivers}, key=int)
        self._probe_positions(numbers)
        for i, num in enumerate(numbers, start=1):
            self._status(f"Baixando a telemetria do OpenF1 ({i}/{len(numbers)})...")
            self.loc[num] = self._fetch("location", f"location_{num}", driver_number=num)
            self.car[num] = self._fetch("car_data", f"car_data_{num}", driver_number=num)
        if not any(self.loc.values()):
            raise SessionNotOnOpenF1(
                "O OpenF1 não tem a posição dos carros desta sessão (sessões depois de "
                "15/10/2026 só existem com o F1 TV). Entre com a sua conta F1 TV para baixá-la."
            )
        self._prepare()

    def _probe_positions(self, numbers: list[str]) -> None:
        """Fail fast when OpenF1 has no car positions for this session (after
        F1's paywall it doesn't), before downloading everyone's telemetry."""
        if not self.laps:
            raise SessionNotOnOpenF1("O OpenF1 não tem as voltas desta sessão.")
        timed = [l for l in self.laps if l.get("date_start")]
        if not timed:
            return
        sample = sorted(timed, key=lambda l: l["date_start"])[len(timed) // 2]
        start = pd.Timestamp(sample["date_start"])
        end = start + pd.Timedelta(seconds=10)
        fmt = "%Y-%m-%dT%H:%M:%S"
        rows = _get("location", {
            "session_key": self.session_key,
            "driver_number": sample["driver_number"],
            "date>": start.strftime(fmt),
            "date<": end.strftime(fmt),
        })
        if not rows:
            raise SessionNotOnOpenF1(
                "O OpenF1 não tem a posição dos carros desta sessão (sessões depois de "
                "15/10/2026 só existem com o F1 TV). Entre com a sua conta F1 TV para baixá-la."
            )

    # -- shared preprocessing ----------------------------------------------

    def _prepare(self) -> None:
        all_dates = []
        for rows in list(self.loc.values()) + list(self.car.values()):
            if rows:
                all_dates.append(rows[0]["date"])
        for rows in (self.positions, self.weather, self.race_control):
            if rows:
                all_dates.extend(r["date"] for r in rows[:1])
        if self.session.get("date_start"):
            all_dates.append(self.session["date_start"])
        # t0: the moment session time is zero; a little before the first sample
        self.t0 = _dates(all_dates).min().floor("s") - pd.Timedelta(seconds=1)

        lap_df = pd.DataFrame(self.laps)
        if lap_df.empty:
            raise SessionNotOnOpenF1("O OpenF1 não tem as voltas desta sessão.")
        lap_df["driver"] = lap_df["driver_number"].astype(str)
        lap_df["start"] = _dates(lap_df["date_start"]) - self.t0
        lap_df = lap_df.sort_values(["driver", "lap_number"]).reset_index(drop=True)
        # End of a lap: start + duration, or else the next lap's start
        dur = pd.to_timedelta(lap_df["lap_duration"].astype(float), unit="s")
        nxt = lap_df.groupby("driver")["start"].shift(-1)
        lap_df["end"] = (lap_df["start"] + dur).fillna(nxt)
        self.lap_df = lap_df

        pit_df = pd.DataFrame(self.pits)
        if not pit_df.empty:
            pit_df["driver"] = pit_df["driver_number"].astype(str)
            pit_df["time"] = _dates(pit_df["date"]) - self.t0
            lane = pit_df["lane_duration"].fillna(pit_df["pit_duration"]).astype(float).fillna(25.0)
            pit_df["exit"] = pit_df["time"] + pd.to_timedelta(lane, unit="s")
        self.pit_df = pit_df

        self.leader_lap_starts = (
            lap_df.dropna(subset=["start"]).groupby("lap_number")["start"].min().sort_index()
        )

    def _session_time(self, iso) -> pd.Timedelta:
        return _dates([iso]).iloc[0] - self.t0

    # -- fastf1._api stand-ins ---------------------------------------------

    def session_info(self) -> dict:
        s = self.session
        start = _dates([s.get("date_start")]).iloc[0] if s.get("date_start") else None
        end = _dates([s.get("date_end")]).iloc[0] if s.get("date_end") else None
        gmt = pd.to_timedelta(s.get("gmt_offset") or "00:00:00")
        return {
            "Meeting": {
                "Key": s.get("meeting_key"),
                "Name": s.get("meeting_name") or s.get("location"),
                "Location": s.get("location"),
                "Country": {"Key": s.get("country_key"), "Code": s.get("country_code"), "Name": s.get("country_name")},
                "Circuit": {"Key": s.get("circuit_key"), "ShortName": s.get("circuit_short_name")},
            },
            "ArchiveStatus": {"Status": "Complete"},
            "Key": s.get("session_key"),
            "Type": s.get("session_type"),
            "Name": s.get("session_name"),
            "StartDate": (start + gmt).to_pydatetime() if start is not None else None,
            "EndDate": (end + gmt).to_pydatetime() if end is not None else None,
            "GmtOffset": gmt.to_pytimedelta(),
            "Path": self.api_path.removeprefix("/static/"),
        }

    def driver_info(self) -> dict:
        out = {}
        for d in self.drivers:
            num = str(d["driver_number"])
            out[num] = {
                "RacingNumber": num,
                "BroadcastName": d.get("broadcast_name"),
                "FullName": d.get("full_name"),
                "Tla": d.get("name_acronym"),
                "Line": None,
                "TeamName": d.get("team_name"),
                "TeamColour": d.get("team_colour") or "FFFFFF",
                "FirstName": d.get("first_name"),
                "LastName": d.get("last_name"),
                "Reference": None,
                "HeadshotUrl": d.get("headshot_url"),
                "CountryCode": d.get("country_code"),
            }
        return out

    def _quali_split_times(self) -> list:
        default = [datetime.timedelta(days=1)] * 3
        if self.session_type not in ("Q", "SQ"):
            return default
        ss = self.session_status_data()
        finishes = [t for t, s in zip(ss["Time"], ss["Status"]) if s == "Finished"]
        for i, t in enumerate(finishes[:3]):
            default[i] = t
        return default

    def extended_timing_data(self):
        laps = self.lap_df
        pit_df = self.pit_df
        rows = []
        for drv, d in laps.groupby("driver"):
            d = d.sort_values("lap_number")
            dpits = pit_df[pit_df["driver"] == drv].sort_values("time") if not pit_df.empty else pit_df
            pits_done = 0
            best = None
            prev_end = None
            for _, lap in d.iterrows():
                end = lap["end"]
                if pd.isna(end):
                    continue
                start = lap["start"] if pd.notna(lap["start"]) else prev_end
                lap_time = _td(lap.get("lap_duration"))
                pit_in = pd.NaT
                pit_out = pd.NaT
                if not dpits.empty:
                    # Entered the pits on this lap: the stop logged against it,
                    # or one whose time falls inside it
                    hit = dpits[(dpits["lap_number"] == lap["lap_number"])]
                    if hit.empty and pd.notna(start):
                        hit = dpits[(dpits["time"] > start) & (dpits["time"] <= end)]
                    if not hit.empty:
                        pit_in = min(hit["time"].iloc[0], end)
                        pits_done += 1
                    # Left the pits on this lap: the previous lap's stop
                    prev = dpits[dpits["lap_number"] == lap["lap_number"] - 1]
                    if not prev.empty:
                        pit_out = max(prev["exit"].iloc[0], start) if pd.notna(start) else prev["exit"].iloc[0]
                if pd.isna(pit_out) and bool(lap.get("is_pit_out_lap")) and pd.notna(start):
                    pit_out = start  # out of the garage
                s1, s2, s3 = (_td(lap.get(f"duration_sector_{i}")) for i in (1, 2, 3))
                s1_end = start + s1 if pd.notna(start) and pd.notna(s1) else pd.NaT
                s2_end = s1_end + s2 if pd.notna(s1_end) and pd.notna(s2) else pd.NaT
                is_pb = False
                if pd.notna(lap_time) and pd.isna(pit_in) and pd.isna(pit_out):
                    if best is None or lap_time < best:
                        best = lap_time
                        is_pb = True
                rows.append({
                    "Time": end,
                    "Driver": drv,
                    "LapTime": lap_time,
                    "NumberOfLaps": int(lap["lap_number"]),
                    "NumberOfPitStops": pits_done,
                    "PitOutTime": pit_out,
                    "PitInTime": pit_in,
                    "Sector1Time": s1,
                    "Sector2Time": s2,
                    "Sector3Time": s3,
                    "Sector1SessionTime": s1_end,
                    "Sector2SessionTime": s2_end,
                    "Sector3SessionTime": end if pd.notna(s3) else pd.NaT,
                    "SpeedI1": lap.get("i1_speed"),
                    "SpeedI2": lap.get("i2_speed"),
                    "SpeedFL": np.nan,
                    "SpeedST": lap.get("st_speed"),
                    "IsPersonalBest": is_pb,
                })
                prev_end = end
        laps_data = pd.DataFrame(rows)
        for col in ("SpeedI1", "SpeedI2", "SpeedFL", "SpeedST"):
            laps_data[col] = pd.to_numeric(laps_data[col], errors="coerce").astype(float)
        laps_data[["IsPersonalBest"]] = laps_data[["IsPersonalBest"]].astype(bool)
        return laps_data, self.stream_data(), self._quali_split_times()

    def stream_data(self) -> pd.DataFrame:
        cols = ["Time", "Driver", "Position", "GapToLeader", "IntervalToPositionAhead"]
        if not self.intervals:
            return pd.DataFrame(columns=cols)
        iv = pd.DataFrame(self.intervals)
        iv["Time"] = _dates(iv["date"]) - self.t0
        iv["Driver"] = iv["driver_number"].astype(str)
        iv = iv.sort_values("Time")

        pos = pd.DataFrame(self.positions)
        if not pos.empty:
            pos["Time"] = _dates(pos["date"]) - self.t0
            pos["Driver"] = pos["driver_number"].astype(str)
            pos = pos.sort_values("Time")[["Time", "Driver", "position"]]
            iv = pd.merge_asof(iv, pos, on="Time", by="Driver", direction="backward")
        else:
            iv["position"] = np.nan

        starts = self.leader_lap_starts
        lap_times = starts.values
        lap_numbers = starts.index.values

        def leader_lap(t):
            i = np.searchsorted(lap_times, t, side="right") - 1
            return int(lap_numbers[i]) if i >= 0 else 1

        gaps, ints = [], []
        for _, r in iv.iterrows():
            g = r.get("gap_to_leader")
            if (g is None or g == 0 or (isinstance(g, float) and np.isnan(g))) and r.get("position") == 1:
                gaps.append(f"LAP {leader_lap(r['Time'].to_timedelta64())}")
                ints.append(f"LAP {leader_lap(r['Time'].to_timedelta64())}")
            else:
                gaps.append(_fmt_gap(None if isinstance(g, float) and np.isnan(g) else g))
                i = r.get("interval")
                ints.append(_fmt_gap(None if isinstance(i, float) and np.isnan(i) else i))
        return pd.DataFrame({
            "Time": iv["Time"].values,
            "Driver": iv["Driver"].values,
            "Position": iv["position"].values,
            "GapToLeader": gaps,
            "IntervalToPositionAhead": ints,
        })

    def timing_app_data(self) -> pd.DataFrame:
        rows = []
        pit_df = self.pit_df
        for st in sorted(self.stints, key=lambda s: (s["driver_number"], s["stint_number"])):
            drv = str(st["driver_number"])
            n = int(st["stint_number"])
            if n <= 1:
                t = pd.Timedelta(0)
            else:
                # OpenF1 starts a stint on the in-lap; the tyres go on as the
                # car leaves the pits, so the out-lap is the first on them
                t = None
                if not pit_df.empty:
                    hit = pit_df[(pit_df["driver"] == drv) & (pit_df["lap_number"] == st.get("lap_start"))]
                    if not hit.empty:
                        t = hit["exit"].iloc[0]
                if t is None:
                    lap = self.lap_df[(self.lap_df["driver"] == drv) & (self.lap_df["lap_number"] == st.get("lap_start"))]
                    t = lap["end"].iloc[0] if not lap.empty and pd.notna(lap["end"].iloc[0]) else None
                if t is None:
                    continue
            age = st.get("tyre_age_at_start")
            rows.append({
                "LapNumber": float(st.get("lap_start") or np.nan),
                "Driver": drv,
                "LapTime": None,
                "Stint": n - 1,
                "TotalLaps": float(age) if age is not None else np.nan,
                "Compound": (st.get("compound") or "UNKNOWN").upper(),
                "New": bool(age == 0) if age is not None else None,
                "TyresNotChanged": None,
                "Time": t,
                "LapFlags": np.nan,
                "LapCountTime": None,
                "StartLaps": float(age) if age is not None else 0.0,
                "Outlap": None,
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("Time").reset_index(drop=True)
        return df

    def _telemetry(self, src: dict[str, list[dict]], kind: str) -> dict[str, pd.DataFrame]:
        out = {}
        for num, rows in src.items():
            if not rows:
                continue
            df = pd.DataFrame(rows)
            date = _dates(df["date"])
            if kind == "car":
                frame = pd.DataFrame({
                    "Time": date - self.t0,
                    "Date": date,
                    "RPM": df["rpm"].fillna(0).astype(int),
                    "Speed": df["speed"].fillna(0).astype(int),
                    "nGear": df["n_gear"].fillna(0).astype(int),
                    "Throttle": df["throttle"].fillna(0).astype(int),
                    "Brake": df["brake"].fillna(0).astype(float) > 0,
                    "DRS": df["drs"].fillna(0).astype(int),
                    "Source": "car",
                })
            else:
                frame = pd.DataFrame({
                    "Time": date - self.t0,
                    "Date": date,
                    "Status": "OnTrack",
                    "X": df["x"].fillna(0).astype(int),
                    "Y": df["y"].fillna(0).astype(int),
                    "Z": df["z"].fillna(0).astype(int),
                    "Source": "pos",
                })
            out[num] = frame.sort_values("Date").reset_index(drop=True)
        return out

    def car_data(self) -> dict:
        return self._telemetry(self.car, "car")

    def position_data(self) -> dict:
        return self._telemetry(self.loc, "pos")

    def weather_data(self) -> dict:
        data = {k: [] for k in ("Time", "AirTemp", "Humidity", "Pressure", "Rainfall", "TrackTemp", "WindDirection", "WindSpeed")}
        for w in sorted(self.weather, key=lambda w: w["date"]):
            data["Time"].append(self._session_time(w["date"]).to_pytimedelta())
            data["AirTemp"].append(w.get("air_temperature"))
            data["Humidity"].append(w.get("humidity"))
            data["Pressure"].append(w.get("pressure"))
            data["Rainfall"].append(bool(w.get("rainfall")))
            data["TrackTemp"].append(w.get("track_temperature"))
            data["WindDirection"].append(w.get("wind_direction"))
            data["WindSpeed"].append(w.get("wind_speed"))
        return data

    def race_control_messages(self) -> dict:
        data = {k: [] for k in ("Time", "Category", "Message", "Status", "Flag", "Scope", "Sector", "RacingNumber", "Lap")}
        for m in sorted(self.race_control, key=lambda m: m["date"]):
            data["Time"].append(_dates([m["date"]]).iloc[0].to_pydatetime())
            data["Category"].append(m.get("category"))
            data["Message"].append(m.get("message"))
            data["Status"].append(None)
            data["Flag"].append(m.get("flag"))
            data["Scope"].append(m.get("scope"))
            data["Sector"].append(int(m["sector"]) if m.get("sector") is not None else None)
            data["RacingNumber"].append(str(m["driver_number"]) if m.get("driver_number") is not None else None)
            data["Lap"].append(int(m["lap_number"]) if m.get("lap_number") is not None else None)
        return data

    def _rc_sorted(self) -> list[dict]:
        return sorted(self.race_control, key=lambda m: m["date"])

    def track_status_data(self) -> dict:
        """Track status from race control: F1's codes 1 (clear), 2 (yellow),
        4 (Safety Car), 5 (red), 6 (VSC) and 7 (VSC ending)."""
        events: list[tuple[pd.Timedelta, str]] = []
        neutral: str | None = None  # "4", "6", "7", "5" or None
        yellows: set = set()
        sc_in_lap: int | None = None

        def current() -> str:
            if neutral:
                return neutral
            return "2" if yellows else "1"

        def emit(t):
            code = current()
            if not events or events[-1][1] != code:
                events.append((t, code))

        emit(pd.Timedelta(0))
        lap_starts = self.leader_lap_starts
        for m in self._rc_sorted():
            t = self._session_time(m["date"])
            # The SC came in at the end of the lap it was announced on
            if sc_in_lap is not None and neutral == "4":
                nxt = lap_starts[lap_starts.index > sc_in_lap]
                if len(nxt) and nxt.iloc[0] <= t:
                    neutral = None
                    sc_in_lap = None
                    emit(nxt.iloc[0])
            msg = str(m.get("message") or "").upper()
            flag = str(m.get("flag") or "").upper()
            scope = str(m.get("scope") or "").title()
            cat = str(m.get("category") or "")
            if cat == "SafetyCar" or "SAFETY CAR" in msg:
                if "VIRTUAL" in msg:
                    if "ENDING" in msg:
                        neutral = "7"
                    elif "DEPLOYED" in msg:
                        neutral = "6"
                else:
                    if "DEPLOYED" in msg:
                        neutral = "4"
                        sc_in_lap = None
                    elif "IN THIS LAP" in msg:
                        sc_in_lap = m.get("lap_number")
            elif flag == "RED" and scope in ("Track", ""):
                neutral = "5"
            elif flag in ("GREEN", "CLEAR") and scope in ("Track", ""):
                if neutral in ("5", "7") or (neutral == "6"):
                    neutral = None
                if neutral == "4" and sc_in_lap is None:
                    pass  # green flags elsewhere don't end a Safety Car
                yellows.clear()
            elif flag in ("YELLOW", "DOUBLE YELLOW") and scope == "Sector":
                yellows.add(m.get("sector"))
            elif flag == "CLEAR" and scope == "Sector":
                yellows.discard(m.get("sector"))
            elif flag == "CHEQUERED":
                neutral = None if neutral != "4" else neutral
            emit(t)
        if sc_in_lap is not None and neutral == "4":
            nxt = lap_starts[lap_starts.index > sc_in_lap]
            if len(nxt):
                neutral = None
                emit(nxt.iloc[0])
        return {
            "Time": [t.to_pytimedelta() for t, _ in events],
            "Status": [c for _, c in events],
            "Message": [TRACK_STATUS_MESSAGES[c] for _, c in events],
        }

    def session_status_data(self) -> dict:
        """Started / Finished / Aborted, from race control and the laps."""
        events: list[tuple[pd.Timedelta, str]] = [(pd.Timedelta(0), "Inactive")]
        is_race = self.session_type in ("R", "S")
        running = False
        if is_race and len(self.leader_lap_starts):
            events.append((self.leader_lap_starts.iloc[0], "Started"))
            running = True
        for m in self._rc_sorted():
            t = self._session_time(m["date"])
            msg = str(m.get("message") or "").upper()
            flag = str(m.get("flag") or "").upper()
            scope = str(m.get("scope") or "").title()
            if flag == "RED" and scope in ("Track", "") and running:
                events.append((t, "Aborted"))
                running = False
            elif flag == "CHEQUERED" and running:
                events.append((t, "Finished"))
                running = False
            elif not running and flag == "GREEN" and scope in ("Track", "") and (
                not is_race or "PIT EXIT" not in msg or any(s == "Aborted" for _, s in events)
            ):
                if is_race and not any(s == "Started" for _, s in events):
                    continue
                if is_race and events[-1][1] == "Finished":
                    continue
                events.append((t, "Started"))
                running = True
        if running:
            end = self.lap_df["end"].max()
            events.append((end + pd.Timedelta(seconds=5), "Finished"))
        events.append((events[-1][0] + pd.Timedelta(minutes=1), "Finalised"))
        return {"Time": [t.to_pytimedelta() for t, _ in events], "Status": [s for _, s in events]}

    def lap_count(self) -> dict:
        total = None
        if self.results:
            laps = [r.get("number_of_laps") for r in self.results if r.get("number_of_laps")]
            total = max(laps) if laps else None
        if total is None and len(self.leader_lap_starts):
            total = int(self.leader_lap_starts.index.max())
        times = [pd.Timedelta(t).to_pytimedelta() for t in self.leader_lap_starts.values]
        return {
            "Time": [datetime.timedelta(0)] + times,
            "TotalLaps": [total] + [None] * len(times),
            "CurrentLap": [1] + [int(n) for n in self.leader_lap_starts.index],
        }


# ---------------------------------------------------------------------------
# Standing in for fastf1._api
# ---------------------------------------------------------------------------

_registry: dict[str, OpenF1Session] = {}
_registry_lock = threading.Lock()
_patched = False


def _install() -> None:
    global _patched
    if _patched:
        return
    import fastf1._api as core_api
    import fastf1.api as public_api

    def wrap(name, method):
        original = getattr(core_api, name)

        def replacement(path, *args, **kwargs):
            src = _registry.get(path)
            if src is None:
                return original(path, *args, **kwargs)
            return method(src, *args, **kwargs)
        replacement.__name__ = name
        replacement.__wrapped__ = original
        for mod in (core_api, public_api):
            if hasattr(mod, name):
                setattr(mod, name, replacement)

    wrap("session_info", lambda s, **k: s.session_info())
    wrap("driver_info", lambda s, **k: s.driver_info())
    wrap("_extended_timing_data", lambda s, **k: s.extended_timing_data())
    wrap("timing_data", lambda s, **k: s.extended_timing_data()[:2])
    wrap("timing_app_data", lambda s, **k: s.timing_app_data())
    wrap("car_data", lambda s, **k: s.car_data())
    wrap("position_data", lambda s, **k: s.position_data())
    wrap("weather_data", lambda s, **k: s.weather_data())
    wrap("race_control_messages", lambda s, **k: s.race_control_messages())
    wrap("track_status_data", lambda s, **k: s.track_status_data())
    wrap("session_status_data", lambda s, **k: s.session_status_data())
    wrap("lap_count", lambda s, **k: s.lap_count())
    # Raw pages (team radio, mini-sectors) aren't on OpenF1: nothing to read
    wrap("fetch_page", lambda s, *a, **k: None)
    _patched = True


def register(fastf1_session, session_type: str, on_status: Callable[[str], None] | None = None) -> OpenF1Session:
    """Download a session from OpenF1 and serve FastF1's reads of it from there."""
    _install()
    event = fastf1_session.event
    try:
        date = event.get_session_date(fastf1_session.name, utc=True)
    except Exception:
        date = None
    key = find_session_key(
        int(event.year),
        session_type,
        date,
        str(event.get("Country", "")) or None,
    )
    src = OpenF1Session(fastf1_session.api_path, key, session_type, on_status)
    src.download()
    with _registry_lock:
        _registry[fastf1_session.api_path] = src
    logger.info(f"Serving {fastf1_session.api_path} from OpenF1 session {key}")
    return src


def unregister(api_path: str, delete_cache: bool = True) -> None:
    with _registry_lock:
        src = _registry.pop(api_path, None)
    if src is not None and delete_cache:
        shutil.rmtree(src.cache_dir, ignore_errors=True)


def is_registered(api_path: str) -> bool:
    return api_path in _registry
