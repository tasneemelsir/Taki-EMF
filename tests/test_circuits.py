"""Circuits set one by one, the two-voltage tower, sag that follows the span, and the line warnings."""

import copy
import math

import numpy as np
import pytest

from engine import benchmarks, earth, lines, physics
from engine.site import Site
from server import service

DOUBLE = "132kV Double Circuit Lattice"


def _line(preset=DOUBLE, **over):
    return dict(lines.default_line(preset), **over)


def _cfg(*line_cfgs, **corridor):
    cfg = service.default_config()
    cfg["lines"] = [copy.deepcopy(c) for c in line_cfgs]
    cfg["buildings"] = []
    cfg["corridor"].update(corridor)
    return service.normalise_config(cfg)


def _site(*line_cfgs, **corridor):
    return Site(_cfg(*line_cfgs, **corridor))


def _circuit(**over):
    return dict(lines.default_circuit(), **over)


# ---------------------------------------------------------------------------
# One circuit at a time
# ---------------------------------------------------------------------------
def test_an_empty_list_means_every_circuit_uses_the_lines_values():
    plain = lines.build_line(_line(load_pct=70.0))
    no_key = _line(load_pct=70.0)
    del no_key["circuits"]
    old = lines.build_line(no_key)
    assert not plain.separate and len(plain.circuits) == 2
    assert [k.operating_current_a for k in plain.circuits] == [pytest.approx(0.7 * plain.rated_current_a)] * 2
    assert [(c.x, c.y_sagged, c.phase, c.current_A) for c in plain.conductors] == \
           [(c.x, c.y_sagged, c.phase, c.current_A) for c in old.conductors]
    assert all(plain.energised)


def test_a_circuit_out_of_service_carries_nothing_and_is_earthed():
    ln = lines.build_line(_line(circuits=[_circuit(), _circuit(on=False)]))
    left, right = ln.circuits
    assert ln.separate and left.on and not right.on
    assert right.operating_current_a == 0.0 and right.thermal_sag_m == 0.0
    assert right.voltage_kv == 132.0                       # the nominal voltage is remembered
    off = [c for c in ln.conductors if c.circuit == 2]
    assert len(off) == 3 and all(c.current_A == 0.0 and c.voltage_kV == 0.0 for c in off)
    assert ln.energised == [True] * 3 + [False] * 3
    # the line is described by the circuit that is running
    assert ln.operating_current_a == left.operating_current_a > 0 and ln.voltage_kv == 132.0


def test_switching_a_circuit_off_removes_the_cancellation_between_the_two():
    both = _site(_line(arrangement="ABC-CBA")).summary()
    one = _site(_line(arrangement="ABC-CBA", circuits=[_circuit(), _circuit(phase_order="CBA", on=False)])).summary()
    assert one["peak_b"] > 1.5 * both["peak_b"]            # low-reactance phasing only helps with both in service


def test_an_earthed_circuit_still_shapes_the_electric_field():
    site = _site(_line(circuits=[_circuit(), _circuit(on=False)]))
    live = [c for c in site.conductors if c.current_A > 0]
    x = np.linspace(-40.0, 40.0, 81)
    b_all = physics.compute_b_field_1d(site.conductors, x, 1.0, site.ground_model, site.earth_rho, site.freq)
    b_live = physics.compute_b_field_1d(live, x, 1.0, site.ground_model, site.earth_rho, site.freq)
    assert np.allclose(b_all, b_live, rtol=1e-12, atol=0)   # no current: no magnetic field of its own
    e_all = physics.compute_e_field_1d(site.conductors, x, 1.0)
    e_live = physics.compute_e_field_1d(live, x, 1.0)
    far = x >= 25.0                                         # well out on the side the earthed circuit hangs on
    assert np.all(e_all[far] < 0.85 * e_live[far])          # earthed wires screen the far field...
    assert e_all.max() > e_live.max()                       # ...and raise it a little close to the line
    assert e_all.max() < 1.1 * e_live.max()


def test_circuit_values_override_the_lines_and_the_towers():
    ln = lines.build_line(_line(current_a=900.0, voltage_kv=110.0, load_pct=80.0, circuits=[
        _circuit(current_a=500.0, load_pct=40.0), _circuit(voltage_kv=66.0, load_pct=100.0)]), max_thermal_sag_m=2.0)
    a, b = ln.circuits
    assert (a.rated_current_a, a.voltage_kv, a.load_pct) == (500.0, 110.0, 40.0)
    assert (b.rated_current_a, b.voltage_kv, b.load_pct) == (900.0, 66.0, 100.0)
    assert a.operating_current_a == pytest.approx(200.0) and b.operating_current_a == pytest.approx(900.0)
    assert a.thermal_sag_m < b.thermal_sag_m == pytest.approx(2.0)      # each circuit sags by its own loading
    lows = {k.id: min(c.y_sagged for c in ln.conductors if c.circuit == k.id) for k in ln.circuits}
    assert lows[1] > lows[2]
    volts = {c.circuit: c.voltage_kV for c in ln.conductors}
    assert volts == {1: 110.0, 2: 66.0}
    assert ln.operating_current_a == 900.0 and ln.voltage_kv == 110.0


def test_phase_order_per_circuit_gives_the_same_line_as_the_arrangement():
    for arrangement, orders in (("ABC-CBA", ("ABC", "CBA")), ("ABC-ABC", ("ABC", "ABC"))):
        whole = lines.build_line(_line(arrangement=arrangement))
        each = lines.build_line(_line(arrangement="ABC-ABC" if arrangement == "ABC-CBA" else "ABC-CBA",
                                      circuits=[_circuit(phase_order=o) for o in orders]))
        assert [c.phase for c in each.conductors] == [c.phase for c in whole.conductors]
        assert [k.phase_order for k in each.circuits] == list(orders)
    # with no order given, a circuit takes the one the line's arrangement implies
    implied = lines.build_line(_line(arrangement="ABC-CBA", circuits=[{"on": True}, {"on": True}]))
    assert [k.phase_order for k in implied.circuits] == ["ABC", "CBA"]


def test_circuit_lists_are_cleaned():
    clean = lines.clean_circuits
    assert clean([{"on": False}], 1) == [] and clean([], 2) == [] and clean("x", 2) == [] and clean(None, 4) == []
    got = clean([{"on": 0, "voltage_kv": "abc", "current_a": -5, "load_pct": 900, "phase_order": "BCA"},
                 "rubbish", {"extra": 1}], 2, load_pct=60.0, orders=["ABC", "CBA"])
    assert got == [
        {"on": False, "voltage_kv": 0.0, "current_a": 0.0, "load_pct": 200.0, "phase_order": "ABC"},
        {"on": True, "voltage_kv": 0.0, "current_a": 0.0, "load_pct": 60.0, "phase_order": "CBA"}]
    assert clean([{"load_pct": float("nan")}, {"current_a": float("inf")}], 2, load_pct=55.0) == [
        lines.default_circuit(55.0), lines.default_circuit(55.0)]
    assert len(clean([{}], 4)) == 4                         # a short list is filled out to the tower


def test_project_files_keep_circuit_settings_and_drop_them_for_single_circuit_towers():
    cfg = service.default_config()
    cfg["lines"] = [_line(circuits=[_circuit(load_pct=30.0), _circuit(on=False)]),
                    _line("275kV Monopole", circuits=[_circuit(on=False)])]
    out = service.normalise_config(cfg)
    assert [c["on"] for c in out["lines"][0]["circuits"]] == [True, False]
    assert out["lines"][0]["circuits"][0]["load_pct"] == 30.0
    assert out["lines"][1]["circuits"] == []                # one circuit: nothing to set separately
    assert service.normalise_config(out) == out
    sol = service.solve(out)
    first = sol["lines"][0]
    assert first["separate"] and [k["on"] for k in first["circuits"]] == [True, False]
    assert [k["label"] for k in first["circuits"]] == ["left", "right"]
    assert first["circuits"][1]["operating_a"] == 0 and first["circuits"][0]["operating_a"] > 0
    assert [c["on"] for c in first["conductors"]] == [True] * 3 + [False] * 3
    assert not sol["lines"][1]["separate"] and len(sol["lines"][1]["circuits"]) == 1


# ---------------------------------------------------------------------------
# The tower with two voltage levels
# ---------------------------------------------------------------------------
def test_quad_tower_is_the_published_geometry():
    ref = benchmarks.load_references()["fikry2022_f1000research"]
    x = np.linspace(-60.0, 60.0, 241)
    for phasing, arrangement in (("untransposed", "ABC-ABC"), ("transposed", "ABC-CBA")):
        published = benchmarks.build_conductors_from_reference(ref, "275_132kV_QC", phasing)
        for c in published:
            c.y_sagged = c.y_base
        site = _site(_line(lines.QUAD_PRESET, arrangement=arrangement), max_sag_m=0.0)
        assert [(c.x, c.y_sagged, c.phase) for c in site.conductors] == \
               [(c.x, c.y_base, c.phase) for c in published]
        want = physics.compute_b_field_1d(published, x, 1.0, earth.PERFECT_CONDUCTOR, 100.0, 50.0)
        got = physics.compute_b_field_1d(site.conductors, x, 1.0, earth.PERFECT_CONDUCTOR, 100.0, 50.0)
        assert np.allclose(got, want, rtol=0, atol=1e-3)    # µT: the twin bundle moves the fourth decimal


def test_quad_tower_keeps_each_level_at_its_own_voltage_and_current():
    ln = lines.build_line(_line(lines.QUAD_PRESET))
    assert [(k.label, k.voltage_kv, k.rated_current_a) for k in ln.circuits] == [
        ("upper left", 275.0, 1232.0), ("upper right", 275.0, 1232.0),
        ("lower left", 132.0, 729.0), ("lower right", 132.0, 729.0)]
    assert [k.phase_order for k in ln.circuits] == ["ABC", "CBA", "CBA", "ABC"]     # the source's low-reactance order
    assert ln.voltage_kv == 275.0 and ln.is_double and ln.tower == "lattice"
    lower_off = lines.build_line(_line(lines.QUAD_PRESET, circuits=[
        _circuit(), _circuit(phase_order="CBA"), _circuit(phase_order="CBA", on=False), _circuit(on=False)]))
    assert lower_off.voltage_kv == 275.0
    assert sum(1 for on in lower_off.energised if on) == 6
    assert lower_off.required_clearance_m == pytest.approx(lines.indicative_ground_clearance_m(275.0))


def test_the_library_describes_each_towers_circuits():
    lib = service.library()
    towers = {t["name"]: t for t in lib["tower_presets"]}
    quad = towers[lines.QUAD_PRESET]["circuits"]
    assert [c["voltage_kv"] for c in quad] == [275.0, 275.0, 132.0, 132.0]
    assert [c["low_order"] for c in quad] == ["ABC", "CBA", "CBA", "ABC"]
    assert len(towers["275kV Monopole"]["circuits"]) == 1
    assert lib["default_circuit"] == lines.default_circuit() and lib["reference_span_m"] == 300.0
    quad_project = next(t for t in service.templates() if t["id"] == "quad")["config"]
    assert [c["on"] for c in quad_project["lines"][0]["circuits"]].count(False) == 1


# ---------------------------------------------------------------------------
# Sag and span
# ---------------------------------------------------------------------------
def test_span_alone_does_not_move_the_mid_span_reading():
    short, long_ = _site(_line(), span_m=160.0), _site(_line(), span_m=500.0)
    assert short.sag_scale == long_.sag_scale == 1.0
    assert short.summary()["peak_b"] == long_.summary()["peak_b"]
    assert [c.y_sagged for c in short.conductors] == [c.y_sagged for c in long_.conductors]


def test_sag_can_follow_the_span():
    assert lines.sag_scale_for(300.0, True) == 1.0 and lines.sag_scale_for(900.0, False) == 1.0
    assert lines.sag_scale_for(450.0, True) == pytest.approx(2.25)
    ref = _site(_line(), span_m=300.0, sag_follows_span=True)
    plain = _site(_line(), span_m=300.0)
    assert [c.y_sagged for c in ref.conductors] == pytest.approx([c.y_sagged for c in plain.conductors])
    short = _site(_line(), span_m=200.0, sag_follows_span=True)
    long_ = _site(_line(), span_m=400.0, sag_follows_span=True)
    assert short.lines[0].attach_heights == pytest.approx(long_.lines[0].attach_heights)   # the towers do not move
    assert min(c.y_sagged for c in long_.conductors) < min(c.y_sagged for c in ref.conductors) \
        < min(c.y_sagged for c in short.conductors)
    assert long_.summary()["peak_b"] > ref.summary()["peak_b"] > short.summary()["peak_b"]
    ln = long_.lines[0]
    assert ln.design_sag_m == pytest.approx(lines.DEFAULT_DESIGN_SAG_M * (400.0 / 300.0) ** 2)
    assert ln.thermal_sag_m == pytest.approx(plain.lines[0].thermal_sag_m * (400.0 / 300.0) ** 2)
    sol = service.solve(_cfg(_line(), span_m=400.0, sag_follows_span=True))
    assert sol["corridor"]["sag_follows_span"] and sol["corridor"]["sag_scale"] == pytest.approx(16.0 / 9.0, abs=1e-3)


def test_a_line_that_hangs_too_low_is_flagged():
    need = lines.indicative_ground_clearance_m
    assert need(11.0) == pytest.approx(5.6) and need(132.0) == pytest.approx(5.6 + 0.01 * (132 / math.sqrt(3) - 22))
    assert need(500.0) > need(275.0) > need(132.0)
    fine = _site(_line())
    assert not [w for w in fine.warnings if "hangs" in w]
    assert service.solve(_cfg(_line()))["clearance"]["ok"]
    low = _site(_line(), span_m=500.0, sag_follows_span=True)
    assert low.lines[0].min_height_m < low.lines[0].required_clearance_m
    assert any("hangs" in w and "Line 1" in w for w in low.warnings)
    c = service.solve(_cfg(_line(), span_m=500.0, sag_follows_span=True))["clearance"]
    assert not c["ok"] and c["min_height_m"] == pytest.approx(low.lines[0].min_height_m, abs=1e-3)
    assert c["required_m"] == pytest.approx(need(132.0), abs=0.01)


def test_lowest_point_counts_the_bundle():
    ln = lines.build_line(_line("500kV Quadruple Bundle"))
    centre = min(c.y_sagged for c in ln.conductors)
    assert ln.min_height_m < centre                         # the lower sub-conductors hang below the bundle centre
    assert centre - ln.min_height_m == pytest.approx(
        -min(o[1] for c in ln.conductors for o in c.bundle_offsets))


# ---------------------------------------------------------------------------
# Lines too close to each other
# ---------------------------------------------------------------------------
def test_spacing_is_judged_by_the_true_distance_between_conductors():
    same = _site(_line(x_offset=0.0), _line(x_offset=0.0))
    assert any("same place" in w for w in same.warnings)
    above = _site(_line(x_offset=0.0), _line(x_offset=0.0, height_adjust_m=25.0))
    assert not [w for w in above.warnings if "same place" in w or "come within" in w]     # one above the other
    near = _site(_line(x_offset=0.0), _line(x_offset=7.0))
    msg = next(w for w in near.warnings if "come within" in w)
    gap = min(math.hypot(a.x - b.x, a.y_sagged - b.y_sagged)
              for a in near.lines[0].conductors for b in near.lines[1].conductors)
    assert f"{gap:.1f} m" in msg and gap < lines.spacing_threshold_m(132.0)
    apart = _site(_line(x_offset=-15.0), _line(x_offset=15.0))
    assert not [w for w in apart.warnings if "come within" in w or "same place" in w]
    assert lines.spacing_threshold_m(500.0) == pytest.approx(5.0)
