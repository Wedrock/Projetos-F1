"""Bayesian tyre degradation model.

Ported from f1-race-replay (src/bayesian_tyre_model.py, MIT licence) and
adapted to run on a session's stored laps.json instead of a FastF1 session, so
it works for every downloaded session without loading anything from F1.

State equation:
    a[t+1] = (1 - I_pit) * (a[t] + nu * A_track) + I_pit * a_reset + eta
Observation equation:
    y[t] = a[t] + gamma * fuel[t] + delta_mismatch + eps

a: latent tyre pace, nu: degradation rate per compound (s/lap), A_track: track
abrasion, gamma: fuel effect (s/kg), delta_mismatch: penalty for the wrong
tyre for the conditions. Each compound's rate starts from a prior and is
updated from the session's stints (robust Theil-Sen slopes); a Kalman filter
then tracks each driver's latent pace and its uncertainty lap by lap.

Output is plain JSON: the fitted parameters (so the frontend can work out a
tyre's health from any frame's compound and tyre age, live timing included)
and a per-driver, per-lap table.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

SLICK, INTER, WET = "SLICK", "INTER", "WET"
DRY, DAMP = "DRY", "DAMP"  # WET doubles as a track condition


@dataclass
class TyreProfile:
    category: str
    degradation_rate: float  # seconds lost per lap (prior, then fitted)
    reset_pace: float
    warmup_laps: int
    max_analysis_laps: int | None
    max_degradation: float  # seconds of loss at which health reaches 0


def _default_profiles() -> dict[str, TyreProfile]:
    return {
        "HARD": TyreProfile(SLICK, 0.01, 69.5, 3, None, 2.0),
        "MEDIUM": TyreProfile(SLICK, 0.03, 69.0, 3, None, 2.0),
        "SOFT": TyreProfile(SLICK, 0.05, 68.5, 1, 10, 2.0),
        "INTERMEDIATE": TyreProfile(INTER, 0.04, 75.0, 2, None, 3.0),
        "WET": TyreProfile(WET, 0.02, 80.0, 2, None, 2.5),
    }


SIGMA_EPSILON = 0.3
SIGMA_ETA = 0.1
FUEL_EFFECT = 0.032  # s per kg
STARTING_FUEL = 110.0  # kg
FUEL_BURN = 1.6  # kg per lap

ABRASION_BASELINE = {"HARD": 0.003, "MEDIUM": 0.009, "SOFT": 0.015}
PRIOR_WEIGHT = {SLICK: 0.3, INTER: 0.4, WET: 0.5}

MISMATCH_PENALTIES: dict[tuple[str, str], float] = {
    (SLICK, DAMP): 2.0,
    (SLICK, WET): 8.0,
    (INTER, DRY): 1.5,
    (INTER, WET): 0.5,
    (WET, DRY): 4.0,
    (WET, DAMP): 1.0,
}

# Conditions a compound's laps are trusted for when fitting its rate
FIT_CONDITIONS = {SLICK: {DRY}, INTER: {DAMP, WET, DRY}, WET: {WET}}


def theil_sen_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Median of all pairwise slopes (as scipy.stats.theilslopes)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    i, j = np.triu_indices(len(x), k=1)
    dx = x[j] - x[i]
    keep = dx != 0
    if not keep.any():
        return 0.0
    return float(np.median((y[j] - y[i])[keep] / dx[keep]))


def parse_lap_time(value) -> float | None:
    """'1:23.456' or '59.123' -> seconds."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        s = str(value).strip()
        if ":" in s:
            mins, secs = s.split(":", 1)
            return int(mins) * 60 + float(secs)
        return float(s)
    except (TypeError, ValueError):
        return None


def mismatch_penalty(category: str, condition: str) -> float:
    return MISMATCH_PENALTIES.get((category, condition), 0.0)


def _abrasion_factor(category: str, abrasion: float) -> float:
    # Wet tyres barely feel the surface
    return 1.0 + 0.3 * (abrasion - 1.0) if category == WET else abrasion


def tyre_health(profile: TyreProfile, abrasion: float, laps_on_tyre: int, condition: str) -> dict:
    """Health 0-100 of a tyre after laps_on_tyre laps (as get_health in the original)."""
    eff = profile.degradation_rate * _abrasion_factor(profile.category, abrasion)
    max_laps = profile.max_degradation / max(eff, 0.001)
    penalty = mismatch_penalty(profile.category, condition)
    eff_laps = laps_on_tyre * (1.0 + penalty / 5.0) if penalty > 0.5 else laps_on_tyre
    health = max(0.0, min(100.0, 100.0 * (1.0 - eff_laps / max_laps)))
    return {"health": int(health), "expected_delta": round(eff * laps_on_tyre, 3)}


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

def _conditions_by_lap(rows: list[dict]) -> dict[int, str]:
    """The track's condition each lap, from the tyres the field is on.

    laps.json has no track condition, so it's inferred: most of the field on
    full wets -> WET, most on wet-weather tyres -> DAMP, otherwise DRY.
    """
    by_lap: dict[int, list[str]] = {}
    for r in rows:
        if r["compound"]:
            by_lap.setdefault(r["lap"], []).append(r["compound"])
    out: dict[int, str] = {}
    for lap, compounds in by_lap.items():
        n = len(compounds)
        wets = sum(c == "WET" for c in compounds)
        rain_tyres = wets + sum(c == "INTERMEDIATE" for c in compounds)
        if wets * 2 >= n:
            out[lap] = WET
        elif rain_tyres * 2 >= n:
            out[lap] = DAMP
        else:
            out[lap] = DRY
    return out


def _rows_from_laps(laps: list[dict]) -> list[dict]:
    """laps.json -> rows with stint numbers, sorted by driver and lap."""
    rows = []
    for lap in laps:
        driver = lap.get("driver")
        num = lap.get("lap_number")
        if not driver or not num:
            continue
        compound = lap.get("compound")
        compound = str(compound).upper() if compound else None
        if compound in ("NONE", "NAN", "UNKNOWN", "TEST_UNKNOWN", ""):
            compound = None
        rows.append({
            "driver": driver,
            "lap": int(num),
            "time": parse_lap_time(lap.get("lap_time")),
            "compound": compound,
            "tyre_life": lap.get("tyre_life"),
            "pit_in": bool(lap.get("pit_in")),
            "pit_out": bool(lap.get("pit_out")),
        })
    rows.sort(key=lambda r: (r["driver"], r["lap"]))

    # Stints: a new one after a pit stop, a compound change or a fresher tyre
    prev = None
    stint = 0
    for r in rows:
        if prev is None or prev["driver"] != r["driver"]:
            stint = 1
        elif (
            prev["pit_in"]
            or r["pit_out"]
            or (r["compound"] and prev["compound"] and r["compound"] != prev["compound"])
            or (r["tyre_life"] is not None and prev["tyre_life"] is not None
                and r["tyre_life"] < prev["tyre_life"])
        ):
            stint += 1
        r["stint"] = stint
        prev = r

    # Laps on the current tyre: its age where known, else the laps in the stint
    counts: dict[tuple[str, int], int] = {}
    for r in rows:
        key = (r["driver"], r["stint"])
        counts[key] = counts.get(key, 0) + 1
        r["laps_on_tyre"] = int(r["tyre_life"]) if r["tyre_life"] else counts[key]
    return rows


def _fit_rows(rows: list[dict], profiles: dict[str, TyreProfile]) -> list[dict]:
    """Laps usable for fitting: timed, on a known compound, not in/out laps, not lap 1."""
    out = []
    for r in rows:
        if r["lap"] <= 1 or r["pit_in"] or r["pit_out"] or r["time"] is None:
            continue
        if r["compound"] not in profiles:
            continue
        fuel = max(0.0, STARTING_FUEL - (r["lap"] - 1) * FUEL_BURN)
        out.append({**r, "fuel": fuel})
    return out


def _stints(rows: list[dict]) -> dict[tuple[str, int], list[dict]]:
    groups: dict[tuple[str, int], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["driver"], r["stint"]), []).append(r)
    return groups


# ---------------------------------------------------------------------------
# Fitting
# ---------------------------------------------------------------------------

def _estimate_abrasion(stints: dict, conditions: dict[int, str]) -> float:
    samples = []
    for laps in stints.values():
        compound = laps[0]["compound"]
        base = ABRASION_BASELINE.get(compound)
        if base is None:
            continue
        dry = [r for r in laps if r["compound"] == compound and conditions.get(r["lap"], DRY) == DRY]
        if len(dry) < 8:
            continue
        fc = np.array([r["time"] - FUEL_EFFECT * r["fuel"] for r in dry])
        delta = fc - fc[0]
        if delta.std() > 0:
            slope = theil_sen_slope(np.arange(1, len(dry) + 1), delta)
            if slope > 0:
                samples.append(slope / base)
    if len(samples) < 3:
        return 1.0
    return float(np.clip(np.median(samples), 0.7, 1.4))


def _estimate_rates(stints: dict, conditions: dict[int, str], profiles: dict[str, TyreProfile],
                    abrasion: float) -> dict[str, int]:
    """Update each compound's rate from its stints; returns how many stints were used."""
    slopes: dict[str, list[float]] = {name: [] for name in profiles}
    for laps in stints.values():
        compound = laps[0]["compound"]
        tyre = profiles.get(compound)
        if tyre is None or len(laps) < 5:
            continue
        valid = [r for r in laps if conditions.get(r["lap"], DRY) in FIT_CONDITIONS[tyre.category]]
        if len(valid) < 3:
            continue
        fc = np.array([r["time"] - FUEL_EFFECT * r["fuel"] for r in valid])
        delta = fc - fc[0]
        lap_on_tyre = np.arange(1, len(valid) + 1)
        mask = lap_on_tyre > tyre.warmup_laps
        if tyre.max_analysis_laps is not None:
            mask &= lap_on_tyre <= tyre.max_analysis_laps
        x, y = lap_on_tyre[mask], delta[mask]
        if len(x) <= 2 or np.std(y) == 0:
            continue
        slope = max(0.0, theil_sen_slope(x, y))
        if abrasion > 0:
            slope /= abrasion
        if tyre.category == INTER:
            dry_share = sum(conditions.get(r["lap"], DRY) == DRY for r in valid) / len(valid)
            if dry_share > 0.3:
                slope = min(slope, 0.08)
        slopes[compound].append(slope)

    used = {}
    for name, tyre in profiles.items():
        if slopes[name]:
            w = PRIOR_WEIGHT[tyre.category]
            tyre.degradation_rate = w * tyre.degradation_rate + (1 - w) * float(np.median(slopes[name]))
        used[name] = len(slopes[name])
    return used


def _latent_uncertainty(fit_rows: list[dict], conditions: dict[int, str],
                        profiles: dict[str, TyreProfile], abrasion: float) -> dict[tuple[str, int], float]:
    """Kalman filter over each driver's laps; returns the latent pace's std per (driver, lap)."""
    obs_var = SIGMA_EPSILON ** 2
    proc_var = SIGMA_ETA ** 2
    out: dict[tuple[str, int], float] = {}
    mu = var = None
    prev_driver = prev_stint = prev_wet = None
    for r in fit_rows:  # already sorted by driver, lap
        tyre = profiles[r["compound"]]
        condition = conditions.get(r["lap"], DRY)
        wet = condition != DRY
        if r["driver"] != prev_driver or r["stint"] != prev_stint or wet != prev_wet or mu is None:
            mu, var = tyre.reset_pace, proc_var
        else:
            nu = tyre.degradation_rate * _abrasion_factor(tyre.category, abrasion)
            penalty = mismatch_penalty(tyre.category, condition)
            if penalty > 0.5:
                nu *= 1.0 + penalty / 10.0
            var_pred = var + proc_var
            innovation = r["time"] - (mu + nu + FUEL_EFFECT * r["fuel"] + penalty)
            gain = var_pred / (var_pred + obs_var)
            mu = mu + nu * (1 - gain) + gain * innovation
            var = (1.0 - gain) * var_pred
        prev_driver, prev_stint, prev_wet = r["driver"], r["stint"], wet
        out[(r["driver"], r["lap"])] = math.sqrt(var + obs_var)
    return out


def build_tyre_model(laps: list[dict]) -> dict:
    """Fit the model to a session's laps.json and return its JSON."""
    profiles = _default_profiles()
    rows = _rows_from_laps(laps)
    conditions = _conditions_by_lap(rows)
    fit_rows = _fit_rows(rows, profiles)
    stints = _stints(fit_rows)

    abrasion = _estimate_abrasion(stints, conditions) if fit_rows else 1.0
    used = _estimate_rates(stints, conditions, profiles, abrasion) if fit_rows else {}
    uncertainty = _latent_uncertainty(fit_rows, conditions, profiles, abrasion) if fit_rows else {}

    drivers: dict[str, list[dict]] = {}
    for r in rows:
        tyre = profiles.get(r["compound"]) if r["compound"] else None
        if tyre is None:
            continue
        condition = conditions.get(r["lap"], DRY)
        entry = {
            "lap": r["lap"],
            "compound": r["compound"],
            "stint": r["stint"],
            "laps_on_tyre": r["laps_on_tyre"],
            **tyre_health(tyre, abrasion, r["laps_on_tyre"], condition),
        }
        std = uncertainty.get((r["driver"], r["lap"]))
        if std is not None:
            entry["uncertainty"] = round(std, 3)
        drivers.setdefault(r["driver"], []).append(entry)

    return {
        "version": 1,
        "track_abrasion": round(abrasion, 4),
        "compounds": {
            name: {
                "category": t.category,
                "degradation_rate": round(t.degradation_rate, 5),
                "max_degradation": t.max_degradation,
                "stints_used": used.get(name, 0),
            }
            for name, t in profiles.items()
        },
        "mismatch_penalties": [
            {"category": c, "condition": cond, "penalty": p}
            for (c, cond), p in MISMATCH_PENALTIES.items()
        ],
        "conditions": {str(k): v for k, v in sorted(conditions.items())},
        "drivers": drivers,
    }


def build_strategy(laps: list[dict]) -> dict:
    """Each driver's stints (compound, first and last lap, tyre age at the start)."""
    rows = _rows_from_laps(laps)
    out: dict[str, list[dict]] = {}
    for r in rows:
        stints = out.setdefault(r["driver"], [])
        if stints and stints[-1]["stint"] == r["stint"]:
            s = stints[-1]
            s["end_lap"] = r["lap"]
            s["laps"] += 1
            if not s["compound"] and r["compound"]:
                s["compound"] = r["compound"]
        else:
            stints.append({
                "stint": r["stint"],
                "compound": r["compound"],
                "start_lap": r["lap"],
                "end_lap": r["lap"],
                "laps": 1,
                "start_tyre_life": r["laps_on_tyre"],
                "new": r["tyre_life"] is not None and r["tyre_life"] <= 1,
            })
    total = max((r["lap"] for r in rows), default=0)
    return {"total_laps": total, "drivers": out}
