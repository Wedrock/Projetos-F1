from services.race_alerts import LEADER_SETTLE_S, RaceAlertDetector


def frame(order, lap=0, total=58, status="green", phase=None, **extra):
    drivers = [{"abbr": a, "position": i, "interval": "+1.2" if i > 1 else None, "best_lap_time": "1:10.123"}
               for i, a in enumerate(order, 1)]
    f = {"drivers": drivers, "lap": lap, "total_laps": total, "status": status, **extra}
    if phase:
        f["quali_phase"] = {"phase": phase}
    return f


def titles(alerts):
    return [a.title for a in alerts]


def test_nothing_before_the_start():
    d = RaceAlertDetector("R", "Brazilian Grand Prix")
    assert d.update(frame(["VER", "NOR"], status="red"), "Inactive", 0) == []
    assert not d.started


def test_race_start_names_the_pole_sitter():
    d = RaceAlertDetector("R", "Brazilian Grand Prix", "2026_21_R")
    alerts = d.update(frame(["VER", "NOR"], lap=1), "Started", 0)
    assert titles(alerts) == ["🏁 Largada!"]
    assert "VER" in alerts[0].body and "Brazilian GP" in alerts[0].body
    assert alerts[0].tag == "2026_21_R-start"
    # Not again
    assert d.update(frame(["VER", "NOR"], lap=1), "Started", 1) == []


def test_safety_car_and_restart_ignoring_yellows():
    d = RaceAlertDetector("R", "X")
    d.update(frame(["VER", "NOR"], lap=1), "Started", 0)
    assert titles(d.update(frame(["VER", "NOR"], lap=10, status="sc"), "Started", 1)) == ["🟡 Safety Car na pista"]
    assert d.update(frame(["VER", "NOR"], lap=11, status="sc"), "Started", 2) == []
    assert d.update(frame(["VER", "NOR"], lap=12, status="yellow"), "Started", 3) == []
    alerts = d.update(frame(["VER", "NOR"], lap=13, status="green"), "Started", 4)
    assert titles(alerts) == ["🟢 Safety Car recolhido"]
    assert "Volta 13/58" in alerts[0].body


def test_plain_yellow_never_alerts():
    d = RaceAlertDetector("R", "X")
    d.update(frame(["VER"], lap=1), "Started", 0)
    assert d.update(frame(["VER"], lap=2, status="yellow"), "Started", 1) == []
    assert d.update(frame(["VER"], lap=3, status="green"), "Started", 2) == []


def test_red_flag_and_vsc():
    d = RaceAlertDetector("R", "X")
    d.update(frame(["VER"], lap=1), "Started", 0)
    assert titles(d.update(frame(["VER"], lap=5, status="vsc"), "Started", 1)) == ["🟡 Virtual Safety Car"]
    assert titles(d.update(frame(["VER"], lap=6, status="red"), "Started", 2)) == ["🔴 Bandeira vermelha"]
    assert titles(d.update(frame(["VER"], lap=6, status="green"), "Started", 3)) == ["🟢 Sessão retomada"]


def test_new_leader_only_once_settled():
    d = RaceAlertDetector("R", "X")
    d.update(frame(["VER", "NOR"], lap=1), "Started", 0)
    # A blip shorter than the settle time is ignored
    assert d.update(frame(["NOR", "VER"], lap=20), "Started", 100) == []
    assert d.update(frame(["VER", "NOR"], lap=20), "Started", 102) == []
    assert d.update(frame(["NOR", "VER"], lap=21), "Started", 200) == []
    alerts = d.update(frame(["NOR", "VER"], lap=21), "Started", 200 + LEADER_SETTLE_S)
    assert titles(alerts) == ["🔄 NOR assume a liderança"]
    assert "VER" in alerts[0].body
    assert d.update(frame(["NOR", "VER"], lap=22), "Started", 300) == []


def test_last_lap_and_podium():
    d = RaceAlertDetector("R", "X")
    d.update(frame(["VER", "NOR", "LEC"], lap=1), "Started", 0)
    alerts = d.update(frame(["VER", "NOR", "LEC"], lap=58), "Started", 1)
    assert titles(alerts) == ["🏁 Última volta!"]
    assert "NOR a 1.2s" in alerts[0].body
    assert d.update(frame(["VER", "NOR", "LEC"], lap=58), "Started", 2) == []
    alerts = d.update(frame(["VER", "NOR", "LEC"], lap=58), "Finished", 3)
    assert alerts[0].body == "1º VER · 2º NOR · 3º LEC"
    assert d.finished
    assert d.update(frame(["VER"], lap=58, status="red"), "Finished", 4) == []


def test_qualifying_ends_only_after_q3():
    d = RaceAlertDetector("Q", "X")
    assert titles(d.update(frame(["VER"], phase="Q1"), "Started", 0)) == ["🟢 Classificação começou"]
    assert d.update(frame(["VER"], phase="Q1"), "Finished", 1) == []
    assert not d.finished
    alerts = d.update(frame(["PIA", "VER"], phase="Q3"), "Finished", 2)
    assert titles(alerts) == ["🏆 Pole position"]
    assert "PIA (1:10.123)" in alerts[0].body
    # No leader or last-lap alerts outside races
    assert d.finished
