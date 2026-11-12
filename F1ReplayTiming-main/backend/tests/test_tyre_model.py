"""Tests for the Bayesian tyre model ported from f1-race-replay."""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.tyre_model import (  # noqa: E402
    _default_profiles,
    build_strategy,
    build_tyre_model,
    parse_lap_time,
    theil_sen_slope,
    tyre_health,
)


def fmt(secs: float) -> str:
    m = int(secs // 60)
    return f"{m}:{secs - m * 60:06.3f}"


def make_race(n_drivers=6, laps=40, pit_lap=20, soft_wear=0.08, hard_wear=0.02, wet=False):
    """Two-stint race: SOFT until pit_lap, then HARD, with linear wear and fuel burn."""
    out = []
    for d in range(n_drivers):
        drv = f"D{d:02d}"
        for lap in range(1, laps + 1):
            first_stint = lap <= pit_lap
            compound = ("INTERMEDIATE" if wet else "SOFT") if first_stint else "HARD"
            life = lap if first_stint else lap - pit_lap
            wear = soft_wear if first_stint else hard_wear
            fuel = 110 - (lap - 1) * 1.6
            t = 90 + 0.032 * fuel + wear * life + 0.01 * d
            out.append({
                "driver": drv,
                "lap_number": lap,
                "lap_time": fmt(t),
                "compound": compound,
                "tyre_life": life,
                "pit_in": lap == pit_lap,
                "pit_out": lap == pit_lap + 1,
            })
    return out


def test_parse_lap_time():
    assert parse_lap_time("1:23.456") == pytest.approx(83.456)
    assert parse_lap_time("59.1") == pytest.approx(59.1)
    assert parse_lap_time(None) is None
    assert parse_lap_time("bad") is None


def test_theil_sen_matches_linear_and_ignores_outlier():
    x = np.arange(1, 11)
    y = 0.05 * x
    y[4] += 10  # one huge outlier
    assert theil_sen_slope(x, y) == pytest.approx(0.05, abs=1e-9)
    assert theil_sen_slope(np.array([1, 1]), np.array([0, 1])) == 0.0


def test_health_falls_with_age_and_is_bounded():
    soft = _default_profiles()["SOFT"]
    fresh = tyre_health(soft, 1.0, 1, "DRY")["health"]
    old = tyre_health(soft, 1.0, 30, "DRY")["health"]
    dead = tyre_health(soft, 1.0, 500, "DRY")["health"]
    assert 0 <= dead <= old < fresh <= 100
    assert dead == 0


def test_slicks_in_the_wet_wear_faster():
    soft = _default_profiles()["SOFT"]
    assert tyre_health(soft, 1.0, 10, "WET")["health"] < tyre_health(soft, 1.0, 10, "DRY")["health"]


def test_fit_learns_soft_wears_faster_than_hard():
    model = build_tyre_model(make_race())
    rates = {k: v["degradation_rate"] for k, v in model["compounds"].items()}
    assert model["compounds"]["SOFT"]["stints_used"] > 0
    assert model["compounds"]["HARD"]["stints_used"] > 0
    assert rates["SOFT"] > rates["HARD"]
    # Updated away from the prior towards the data
    assert rates["SOFT"] > 0.05
    assert 0.7 <= model["track_abrasion"] <= 1.4


def test_driver_table_resets_after_pit_stop():
    model = build_tyre_model(make_race())
    laps = {e["lap"]: e for e in model["drivers"]["D00"]}
    assert laps[20]["compound"] == "SOFT" and laps[21]["compound"] == "HARD"
    assert laps[21]["stint"] == laps[20]["stint"] + 1
    assert laps[21]["health"] > laps[20]["health"]
    assert laps[19]["health"] >= laps[20]["health"]
    assert "uncertainty" in laps[10]


def test_conditions_inferred_from_tyres():
    model = build_tyre_model(make_race(wet=True))
    assert model["conditions"]["5"] == "DAMP"
    assert model["conditions"]["30"] == "DRY"


def test_empty_and_untimed_laps_dont_crash():
    assert build_tyre_model([])["drivers"] == {}
    laps = [{"driver": "AAA", "lap_number": 1, "lap_time": None, "compound": None,
             "tyre_life": None, "pit_in": False, "pit_out": False}]
    model = build_tyre_model(laps)
    assert model["track_abrasion"] == 1.0


def test_strategy_stints():
    strat = build_strategy(make_race(n_drivers=1))
    stints = strat["drivers"]["D00"]
    assert strat["total_laps"] == 40
    assert [(s["compound"], s["start_lap"], s["end_lap"]) for s in stints] == [
        ("SOFT", 1, 20), ("HARD", 21, 40),
    ]
    assert stints[0]["new"] and stints[1]["new"]
