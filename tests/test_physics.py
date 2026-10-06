"""The field solvers must reproduce the original Taki physics exactly at 100 % loading."""

import copy

import numpy as np
import pytest

from engine import earth, lines, physics

X = np.linspace(-60.0, 60.0, 121)
Y1 = np.full_like(X, 1.0)


def _ref_conductors(ref_physics, preset, arrangement="ABC-CBA", load=100.0, x_off=0.0):
    p = ref_physics.get_tower_presets()[preset]
    conds = copy.deepcopy(p["conductors"])
    for c in conds:
        c.radius_m = p.get("conductor_radius_m", 0.015)
    if len({c.circuit for c in conds}) > 1:
        conds = ref_physics.apply_phase_swap(conds, arrangement)
    conds = ref_physics.apply_sag(conds, load, 1.5)
    return ref_physics.translate_conductors(conds, x_off)


@pytest.mark.parametrize("preset", list(physics.get_tower_presets()))
@pytest.mark.parametrize("ground", [earth.PERFECT_CONDUCTOR, earth.FREE_SPACE, earth.COMPLEX_IMAGE])
def test_b_field_identical_to_original(ref, preset, ground):
    ref_physics, _ = ref
    line = lines.build_line({"preset": preset, "load_pct": 100.0, "arrangement": "ABC-CBA"})
    new = physics.compute_b_field_at_points(line.conductors, X, Y1, ground, 100.0, 50.0)
    old = ref_physics.compute_b_field_at_points(_ref_conductors(ref_physics, preset), X, Y1, ground, 100.0, 50.0)
    np.testing.assert_allclose(new, old, rtol=1e-12, atol=1e-15)


@pytest.mark.parametrize("preset", list(physics.get_tower_presets()))
def test_e_field_solver_identical_to_original(ref, preset):
    """
    The original pipeline lost the preset conductor radius in apply_phase_swap and so always
    solved E with the 15 mm fallback and no bundle correction. Given those same inputs the
    solver must return the same numbers; the corrected inputs must give a larger field.
    """
    ref_physics, _ = ref
    old_conds = _ref_conductors(ref_physics, preset)
    assert all(c.radius_m is None for c in old_conds)          # the original bug, reproduced
    old = ref_physics.compute_e_field_at_points(old_conds, X, Y1)

    line = lines.build_line({"preset": preset, "load_pct": 100.0, "arrangement": "ABC-CBA"})
    as_before = copy.deepcopy(line.conductors)
    for c in as_before:
        c.radius_m = 0.015
    same = physics.compute_e_field_at_points(as_before, X, Y1, bundle_equivalent=False)
    np.testing.assert_allclose(same, old, rtol=1e-10, atol=1e-14)

    corrected = physics.compute_e_field_at_points(line.conductors, X, Y1, bundle_equivalent=True)
    if any(len(c.bundle_offsets) > 1 for c in line.conductors):
        assert corrected.max() > 1.1 * old.max()


def test_single_wire_matches_closed_form():
    c = physics.Conductor(x=0.0, y_base=20.0, phase="A", circuit=1, current_A=1000.0, voltage_kV=132.0)
    c.y_sagged = 20.0
    b = physics.compute_b_field_at_points([c], np.array([15.0]), np.array([1.0]), earth.FREE_SPACE, 100.0, 50.0)
    expected = 4e-7 * np.pi * 1000.0 / (2 * np.pi * np.hypot(15.0, 19.0)) * 1e6
    assert b[0] == pytest.approx(expected, rel=1e-9)


def test_loading_scales_current_and_field():
    preset = list(physics.get_tower_presets())[1]
    full = lines.build_line({"preset": preset, "load_pct": 100.0})
    half = lines.build_line({"preset": preset, "load_pct": 50.0})
    assert half.operating_current_a == pytest.approx(0.5 * full.operating_current_a)
    assert half.rated_current_a == full.rated_current_a
    # Same geometry (no thermal sag change) -> the field is exactly proportional to the current.
    for c, f in zip(half.conductors, full.conductors):
        c.y_sagged = f.y_sagged
    b_full = physics.compute_b_field_at_points(full.conductors, X, Y1, earth.FREE_SPACE, 100.0, 50.0)
    b_half = physics.compute_b_field_at_points(half.conductors, X, Y1, earth.FREE_SPACE, 100.0, 50.0)
    np.testing.assert_allclose(b_half, 0.5 * b_full, rtol=1e-12)


def test_current_override_and_voltage_override():
    preset = list(physics.get_tower_presets())[0]
    ln = lines.build_line({"preset": preset, "load_pct": 80.0, "current_a": 500.0, "voltage_kv": 110.0})
    assert ln.rated_current_a == 500.0 and ln.operating_current_a == pytest.approx(400.0)
    assert all(c.voltage_kV == 110.0 for c in ln.conductors)


def test_unknown_preset_is_reported():
    with pytest.raises(lines.LineError):
        lines.build_line({"preset": "no such tower"})


def test_conductors_rise_towards_the_towers():
    ln = lines.build_line({"preset": list(physics.get_tower_presets())[1], "load_pct": 100.0})
    mid = ln.at_z(0.0, 150.0)
    quarter = ln.at_z(75.0, 150.0)
    tower = ln.at_z(150.0, 150.0)
    for m, q, t, att in zip(mid, quarter, tower, ln.attach_heights):
        assert m.y_sagged < q.y_sagged < t.y_sagged
        assert t.y_sagged == pytest.approx(att)
        assert q.y_sagged == pytest.approx(m.y_sagged + 0.25 * (att - m.y_sagged))


def test_custom_geometry_layouts():
    for layout in lines.CUSTOM_LAYOUTS:
        ln = lines.build_line({"preset": lines.CUSTOM, "custom": dict(lines.DEFAULT_CUSTOM, layout=layout)})
        n = 6 if layout == "double-vertical" else 3
        assert len(ln.conductors) == n
        assert sorted({c.phase for c in ln.conductors}) == ["A", "B", "C"]
        assert all(len(c.bundle_offsets) == 2 for c in ln.conductors)


def test_bundle_offsets_are_regular_polygons():
    for n in (2, 3, 4, 6):
        offs = np.array(lines.bundle_offsets(n, 0.45))
        d = np.hypot(*(offs - np.roll(offs, 1, axis=0)).T)
        np.testing.assert_allclose(d, 0.45, rtol=1e-5)
        np.testing.assert_allclose(offs.mean(axis=0), 0.0, atol=1e-6)


def test_each_line_keeps_its_own_voltage_current_and_loading():
    """A corridor of one to four lines, each set independently."""
    from server import service
    names = list(lines.tower_presets())
    cfg = service.default_config()
    cfg["lines"] = []
    for i in range(4):
        ln = dict(service.library()["default_line"], preset=names[i % len(names)], x_offset=-45.0 + 30.0 * i,
                  voltage_kv=[132.0, 275.0, 500.0, 0.0][i], current_a=[400.0, 0.0, 1200.0, 0.0][i],
                  load_pct=[100.0, 50.0, 25.0, 80.0][i])
        cfg["lines"].append(ln)
    sol = service.solve(service.normalise_config(cfg))
    got = sol["lines"]
    assert len(got) == 4
    assert [g["kv"] for g in got[:3]] == [132.0, 275.0, 500.0]
    assert got[0]["operating_a"] == pytest.approx(400.0)                       # override x 100 %
    assert got[1]["operating_a"] == pytest.approx(0.5 * got[1]["rated_a"])     # preset rating x 50 %
    assert got[2]["operating_a"] == pytest.approx(0.25 * 1200.0)
    assert got[3]["operating_a"] == pytest.approx(0.8 * got[3]["rated_a"])
    for n in (1, 2, 3):
        fewer = dict(cfg, lines=cfg["lines"][:n])
        assert len(service.solve(service.normalise_config(fewer))["lines"]) == n


def test_loading_scales_the_current_and_the_sag():
    """
    Loading acts twice: the current is rated x load, and a hotter conductor sags
    lower. With the thermal sag switched off, B follows the load exactly.
    """
    from server import service
    def peaks(load, max_sag):
        cfg = service.default_config()
        cfg["lines"][0]["load_pct"] = load
        cfg["corridor"]["max_sag_m"] = max_sag
        s = service.solve(service.normalise_config(cfg))
        return s["peak_b"], s["peak_e"]
    b100, e100 = peaks(100.0, 0.0)
    b40, e40 = peaks(40.0, 0.0)
    b120, _ = peaks(120.0, 0.0)
    assert b40 == pytest.approx(0.4 * b100, rel=1e-4) and b120 == pytest.approx(1.2 * b100, rel=1e-4)
    assert e40 == pytest.approx(e100, rel=1e-6)                                # E follows voltage, not load
    s100, _ = peaks(100.0, 1.5)
    s40, es40 = peaks(40.0, 1.5)
    assert s40 < 0.4 * s100                                                    # cooler line also hangs higher
    assert s100 > b100                                                         # sag brings the conductors down


def test_voltage_changes_e_in_proportion_and_leaves_b_alone():
    from server import service
    def peaks(kv):
        cfg = service.default_config()
        cfg["lines"][0]["voltage_kv"] = kv
        s = service.solve(service.normalise_config(cfg))
        return s["peak_b"], s["peak_e"]
    b1, e1 = peaks(132.0)
    b2, e2 = peaks(264.0)
    assert e2 == pytest.approx(2.0 * e1, rel=1e-4) and b2 == pytest.approx(b1, rel=1e-9)


def test_raising_the_conductors_lowers_the_field_under_the_line():
    from server import service
    def peak(dh):
        cfg = service.default_config()
        cfg["lines"][0]["height_adjust_m"] = dh
        return service.solve(service.normalise_config(cfg))["peak_b"]
    assert peak(10.0) < peak(5.0) < peak(0.0)
