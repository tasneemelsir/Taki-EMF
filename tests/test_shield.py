"""The finite-barrier solver: verification against exact solutions, and sanity on real geometries."""

import copy

import numpy as np
import pytest

from engine import earth, shield_bem, shield_engine as sh, validation
from engine.site import Site
from server import service


def _cfg(**shield):
    c = service.default_config()
    c["lines"][0]["load_pct"] = 100.0
    c["buildings"] = [dict(service.default_building(0), distance=30.0)]
    c["shield"].update({"enabled": True, "preset": "wall-between", "distance_m": 20.0, "height_m": 12.0,
                        "length_m": 80.0, "material_id": "aluminium", "thickness_mm": 3.0})
    c["shield"].update(shield)
    return service.normalise_config(c)


def test_all_self_checks_pass():
    checks = validation.self_checks()
    assert len(checks) >= 11 and {"shell_al", "shell_mu", "loop", "loop_comp"} <= {c["id"] for c in checks}
    for c in checks:
        assert c["passed"], f"{c['id']}: expected {c['expected']}, got {c['got']}"


def test_induced_currents_sum_to_zero_per_bonded_group():
    site = Site(_cfg())
    mag, _ = site.solution(0.0)
    m = mag.mesh
    for g in set(m.group.tolist()):
        net = np.sum(mag.K[m.group == g] * m.length[m.group == g])
        assert abs(net) < 1e-9 * np.sum(np.abs(mag.K) * m.length)


def test_wall_reduces_field_behind_it_and_not_under_the_line():
    site = Site(_cfg())
    behind = site.point(30.0, 5.0, 0.0)
    under = site.point(0.0, 1.0, 0.0)
    assert behind["bS"] < behind["b0"] and behind["eS"] < behind["e0"]
    assert under["bS"] == pytest.approx(under["b0"], rel=0.12)


def test_shield_only_acts_along_its_length():
    site = Site(_cfg(length_m=40.0))
    inside = site.point(30.0, 5.0, 0.0)
    outside = site.point(30.0, 5.0, 100.0)
    assert inside["bS"] != pytest.approx(inside["b0"], rel=1e-3)
    assert outside["bS"] == pytest.approx(outside["b0"]) and outside["eS"] == pytest.approx(outside["e0"])


def test_compliance_always_uses_the_unshielded_field():
    on, off = Site(_cfg()), Site(_cfg(enabled=False))
    assert on.summary()["peak_b"] == pytest.approx(off.summary()["peak_b"])
    assert on.summary()["overall"] == off.summary()["overall"]


def test_non_conducting_wall_leaves_the_magnetic_field_alone():
    site = Site(_cfg(material_id="concrete"))
    v = site.point(30.0, 5.0, 0.0)
    assert v["bS"] == pytest.approx(v["b0"], rel=0.02)


def test_enclosure_beats_a_wall_and_unbonded_seams_are_worse():
    wall = Site(_cfg()).receptors()[0]
    box = Site(_cfg(preset="enclosure", material_id="mildsteel", thickness_mm=6.0)).receptors()[0]
    assert box["barrier_b_reduction_pct"] > wall["barrier_b_reduction_pct"] > 0
    bonded = Site(_cfg(preset="enclosure")).receptors()[0]["barrier_b_reduction_pct"]
    loose = Site(_cfg(preset="enclosure", bonded=False)).receptors()[0]["barrier_b_reduction_pct"]
    assert loose < bonded


def test_floating_barrier_reports_an_induced_voltage_and_earthed_does_not():
    _, floating = Site(_cfg(grounded=False)).solution(0.0)
    _, earthed = Site(_cfg(grounded=True)).solution(0.0)
    assert floating.floating_voltage_kv > 0.05
    assert earthed.floating_voltage_kv == 0.0
    assert earthed.earth_current_ma_per_m(50.0) > 0.0


def test_points_on_the_sheet_do_not_blow_up():
    site = Site(_cfg())
    x = np.array([19.9, 20.0, 20.1])
    r = site.fields(x, np.full_like(x, 6.0), 0.0)
    assert np.all(np.isfinite(r["bS"])) and np.all(np.isfinite(r["eS"]))
    assert r["bS"].max() < 5.0 * r["b0"].max()


def test_shield_currents_do_not_use_a_perfect_earth_image():
    assert shield_bem.local_ground_model(earth.PERFECT_CONDUCTOR) == earth.COMPLEX_IMAGE
    assert shield_bem.local_ground_model(earth.COMPLEX_IMAGE) == earth.COMPLEX_IMAGE
    assert shield_bem.local_ground_model(earth.FREE_SPACE) == earth.FREE_SPACE


def test_analytical_sheet_formula_is_far_above_the_solved_reduction():
    site = Site(_cfg())
    sheet_db = site.se_simple.se_b
    v = site.point(30.0, 5.0, 0.0)
    solved_db = sh.se_db(v["b0"], v["bS"])
    assert sheet_db > 20.0 and solved_db < 0.5 * sheet_db


def test_all_models_and_presets_run():
    for preset in sh.PRESETS:
        for model in sh.MODELS:
            site = Site(_cfg(preset=preset, model=model))
            v = site.point(32.0, 4.0, 0.0)
            assert np.isfinite(v["bS"]) and np.isfinite(v["eS"]) and v["bS"] >= 0 and v["eS"] >= 0


# ------------------------------------------------- shielding around the building
def _around(**shield):
    base = {"preset": "enclosure", "distance_m": 18.0}
    base.update(shield)
    return _cfg(**base)


def test_default_shield_goes_around_the_building():
    assert sh.DEFAULT_PRESET == "enclosure" and service.default_shield()["preset"] == "enclosure"
    order = list(sh.PRESETS)
    assert order.index("enclosure") < order.index("wall-between")           # "around the building" comes first
    assert all(sh.PRESETS[k]["attached"] for k in sh.SURROUNDING)
    site = Site(_around())
    assert "around" in site.geom.description.lower()


def test_complete_envelope_beats_walls_and_roof_which_beats_one_face():
    def avg(preset):
        z = Site(_around(preset=preset)).zone_stats()
        return z["b"]["avgS"] / z["b"]["avg0"]
    envelope, enclosure, panel, floor = avg("envelope"), avg("enclosure"), avg("panel"), avg("floor")
    assert envelope < 0.05                                                   # closed conducting shell: > 95 %
    assert envelope < enclosure < panel < 1.0
    assert floor == pytest.approx(1.0, abs=0.02)                             # a floor alone does nothing


def test_shielded_room_is_judged_inside_the_room():
    site = Site(_around(preset="room"))
    zone = site.protected_zone()
    assert "room" in zone[0].lower()
    x0, x1, y0, y1 = zone[1:5]
    b = site.buildings[0]
    assert b["distance"] < x0 < x1 < b["distance"] + b["width"] and 0 < y0 < y1 < b["height"]
    ref = site.shield_reference_point()
    assert x0 < ref[0] < x1 and y0 < ref[1] < y1
    stats = site.zone_stats()
    assert stats["b"]["reduction_pct"] > 90 and stats["e"]["reduction_pct"] > 99
    outside = site.point(b["distance"] + 1.0, b["height"] - 1.0, 0.0)        # same building, outside the room
    assert outside["bS"] > 0.5 * outside["b0"]


def test_unbonded_room_is_far_worse_than_a_welded_one():
    welded = Site(_around(preset="room")).zone_stats()["b"]["reduction_pct"]
    loose = Site(_around(preset="room", bonded=False)).zone_stats()["b"]["reduction_pct"]
    assert welded > 90 and loose < welded - 30


def test_receptors_report_the_average_over_the_interior():
    r = Site(_around()).receptors()[0]
    for k in ("b_in_avg_uT", "b_in_max_uT", "b_in_avg_shield_uT", "b_in_max_shield_uT", "b_in_reduction_pct"):
        assert k in r and np.isfinite(r[k])
    assert r["b_in_avg_shield_uT"] < r["b_in_avg_uT"] <= r["b_in_max_uT"]


def test_two_material_construction_is_solved_and_changes_the_result():
    """A closed room is where the material matters; open shapes are limited by their openings."""
    def room(**kw):
        return Site(_around(preset="room", layers=2, layer_spacing_m=0.1, **kw))
    one, two = room(material_id="aluminium"), room(material_id="aluminium", layer2_material_id="mildsteel")
    assert one.shield_cfg.layer2_material is None and two.shield_cfg.layer2_material.id == "mildsteel"
    assert {p.material_id for p in two.geom.plates} == {None, "mildsteel"}
    a, b = (s.zone_stats()["b"]["avgS"] for s in (one, two))
    assert np.isfinite(b) and abs(b - a) > 0.05 * a           # the second material is really in the solution
    assert Site(_around(layer2_material_id="mildsteel")).shield_cfg.layer2_material is None     # needs 2 layers
    assert Site(_around(layers=2, layer2_material_id="nonsense")).shield_cfg.layer2_material is None


# ------------------------------------------------------- loops and screening wires
def _loop(**kw):
    base = {"preset": "passive-loop", "loop_vertical": True, "distance_m": 8.0, "height_m": 6.0,
            "loop_spacing_m": 15.0, "wire_mm2": 400.0, "length_m": 300.0, "side": "right"}
    base.update(kw)
    return Site(_cfg(**base))


def test_passive_loop_carries_equal_and_opposite_currents():
    site = _loop()
    assert site.shield_cfg.is_wire and len(site.geom.wires) == 2
    mag, _ = site.solution(0.0)
    i_a, i_b = mag.plate_currents()
    assert abs(i_a) > 1.0 and abs(i_a + i_b) < 1e-9 * abs(i_a)
    assert mag.loss_w_per_m() > 0


def test_series_compensation_raises_the_loop_current():
    plain, comp = _loop(), _loop(loop_compensation_pct=50.0)
    i0 = abs(plain.solution(0.0)[0].plate_currents()[0])
    i1 = abs(comp.solution(0.0)[0].plate_currents()[0])
    assert i1 > 1.3 * i0
    assert "compensated" in comp.geom.description and "compensated" not in plain.geom.description


def test_loop_changes_b_but_not_much_e_and_only_along_its_length():
    site = _loop(length_m=100.0)
    near, far = site.point(31.0, 7.5, 0.0), site.point(31.0, 7.5, 120.0)
    assert near["bS"] != pytest.approx(near["b0"], rel=0.02)
    assert far["bS"] == pytest.approx(far["b0"])


def test_earthed_screening_wires_cut_e_and_leave_b():
    cfg = _cfg(preset="screen-wires")
    cfg["shield"].update(service.suggested_wires(Site(cfg), "screen-wires"))
    site = Site(service.normalise_config(cfg))
    assert len(site.geom.wires) == site.shield_cfg.wire_count >= 3
    z = site.zone_stats()
    assert z["e"]["reduction_pct"] > 30 and abs(z["b"]["reduction_pct"]) < 8
    floating = site.with_shield(grounded=False).zone_stats()
    assert floating["e"]["reduction_pct"] < z["e"]["reduction_pct"]


def test_loop_search_respects_clearances_and_beats_a_blind_placement():
    site = Site(_cfg(preset="enclosure"))
    cands = service.loop_candidates(site)
    clear = service._loop_clearance(site)
    b = site.buildings[0]
    assert len(cands) >= 10
    for c in cands:
        x = c["distance_m"] * (-1 if c["side"] == "left" else 1)
        pts = [(x, c["height_m"]), (x, c["height_m"] + c["loop_spacing_m"])] if c["loop_vertical"] else \
              [(x - c["loop_spacing_m"] / 2, c["height_m"]), (x + c["loop_spacing_m"] / 2, c["height_m"])]
        for px, py in pts:
            assert py >= 5.0
            assert min(np.hypot(px - k.x, py - k.y_sagged) for k in site.conductors) >= clear - 0.06
            assert not (b["distance"] - 1 <= px <= b["distance"] + b["width"] + 1 and py <= b["height"] + 1)
    found = service.best_passive_loop(site)
    assert found["tried"] >= len(cands) and found["best"]["reduction_pct"] >= found["uncompensated"]["reduction_pct"]
    assert found["best"]["reduction_pct"] > 5 and found["worst_pct"] < 0        # placement decides the sign
    # the reported figure is reproduced by applying the settings
    z = site.with_shield(**found["best"]["changes"]).zone_stats()
    assert z["b"]["reduction_pct"] == pytest.approx(found["best"]["reduction_pct"], abs=0.01)


def test_loop_search_mirrors_for_a_building_on_the_left():
    cfg = _cfg(preset="enclosure")
    cfg["buildings"][0]["side"] = "left"
    best = service.best_passive_loop(Site(service.normalise_config(cfg)))["best"]
    assert best["changes"]["side"] == "left" and best["reduction_pct"] > 5


def test_suggestion_endpoint_payload():
    site = Site(_cfg(preset="enclosure"))
    s = service.suggestion(site, "passive-loop")
    assert s["changes"]["wire_mm2"] > 0 and "placements tried" in s["note"] and "preset" not in s["changes"]
    w = service.suggestion(site, "screen-wires")
    assert w["changes"]["grounded"] is True and w["changes"]["height_m"] > site.buildings[0]["height"]
    assert service.suggestion(site, "enclosure") == {"changes": {}, "note": ""}
    cfg = _cfg(preset="enclosure"); cfg["buildings"] = []
    assert "right-of-way" in service.suggestion(Site(service.normalise_config(cfg)), "passive-loop")["note"]


def test_measures_table_lists_every_arrangement_and_the_line_measures():
    r = service.shield_sweep(_cfg(preset="enclosure"), "geometry")
    ids = [row.get("id") for row in r["rows"]]
    assert set(sh.PRESETS) - {"custom"} <= set(ids) and ids.count("line") >= 2
    assert "custom" not in ids                                              # nothing drawn yet
    loops = [row for row in r["rows"] if row["id"] == "passive-loop"]
    assert loops and all(row["changes"]["preset"] == "passive-loop" for row in loops)
    labels = " | ".join(row["label"] for row in r["rows"])
    assert "Raise the conductors by 5 m" in labels
    for row in r["rows"]:
        assert np.isfinite(row["bS"]) and np.isfinite(row["eS"]) and (row["id"] == "line" or row.get("short"))


# ------------------------------------------------ stand-off, walls only, custom layout
def test_sheets_can_stand_off_the_building():
    on = Site(_around())
    off = Site(_around(gap_m=2.0, roof_gap_m=1.0))
    b = on.buildings[0]
    near, far, h = b["distance"], b["distance"] + b["width"], b["height"]
    assert on.geom.walls == [(near, 0.0, near, h), (near, h, far, h), (far, h, far, 0.0)]
    assert off.geom.walls == [(near - 2, 0.0, near - 2, h + 1), (near - 2, h + 1, far + 2, h + 1), (far + 2, h + 1, far + 2, 0.0)]
    assert off.geom.z_half == pytest.approx(on.geom.z_half + 2.0)          # past the ends of the building too
    assert "2 m off the walls" in off.geom.description and "1 m above the roof" in off.geom.description
    assert "off the walls" not in on.geom.description
    a, c = on.zone_stats()["b"]["reduction_pct"], off.zone_stats()["b"]["reduction_pct"]
    assert a > 10 and c > 10 and abs(a - c) < 15                             # same kind of shield, moved out
    # towards the line the sheet stops short of the centreline, whatever gap is asked for
    huge = Site(_around(gap_m=30.0))
    assert min(w[0] for w in huge.geom.walls) >= 1.0 - 1e-9
    assert Site(_around(preset="panel", gap_m=1.5)).geom.walls[0][0] == pytest.approx(near - 1.5)
    canopy = Site(_around(preset="roof", roof_gap_m=2.0, gap_m=1.0)).geom
    assert canopy.walls == [(near - 1, h + 2, far + 1, h + 2)] and "canopy" in canopy.description
    assert Site(_around(preset="floor", floor_level_m=4.0)).geom.walls == [(near, 4.0, far, 4.0)]
    assert Site(_around(preset="floor", floor_level_m=999)).geom.walls[0][1] == pytest.approx(h - 0.5)


def test_walls_only_leaves_the_roof_open():
    site = Site(_around(preset="walls"))
    b = site.buildings[0]
    xs = sorted({w[0] for w in site.geom.walls})
    assert xs == [b["distance"], b["distance"] + b["width"]]
    assert all(w[0] == w[2] and max(w[1], w[3]) == b["height"] for w in site.geom.walls)   # two walls, no roof
    assert len({p.group for p in site.geom.plates}) == 1                     # joined round the building's ends
    assert "walls only" in site.geom.description and "walls" in sh.SURROUNDING
    walls = site.zone_stats()
    box = Site(_around(preset="enclosure")).zone_stats()
    assert 0 < walls["e"]["reduction_pct"] < box["e"]["reduction_pct"]
    assert walls["b"]["reduction_pct"] < box["b"]["reduction_pct"]


@pytest.mark.parametrize("preset", ["enclosure", "envelope", "walls", "wall-between"])
def test_custom_layout_gives_the_same_answer_as_the_same_shape_built_in(preset):
    """The same sheets, entered by hand as separate plates, must solve to the same field."""
    built_in = Site(_around(preset=preset))
    g = built_in.geom
    custom = Site(_around(preset="custom", custom_plates=[list(w) for w in g.walls],
                          length_m=2 * g.z_half, z_center_m=g.z_center))
    assert custom.shield_on and custom.shield_cfg.is_custom and len(custom.geom.walls) == len(g.walls)
    for x, y in ((31.0, 7.5), (50.0, 3.0), (10.0, 1.0), (75.0, 5.0)):
        a, c = built_in.point(x, y, 0.0), custom.point(x, y, 0.0)
        assert c["bS"] == pytest.approx(a["bS"], rel=0.02, abs=1e-4)
        assert c["eS"] == pytest.approx(a["eS"], rel=0.02, abs=1e-4)


def test_custom_layout_is_cleaned_and_can_be_empty():
    raw = [[20, 0, 20, 12], [20, 12, 28, 12], [1, 1, 1, 1.05], ["a", 1, 2, 3], [1, 2, 3], None, [5, -4, 9, 3]]
    cfg = _cfg(preset="custom", custom_plates=raw + [[30 + i, 0, 30 + i, 5] for i in range(30)])
    kept = cfg["shield"]["custom_plates"]
    assert kept[0] == [20.0, 0.0, 20.0, 12.0] and len(kept) <= sh.MAX_CUSTOM_PLATES
    assert all(isinstance(p, list) and len(p) == 4 and min(p[1], p[3]) >= 0 for p in kept)   # no plates underground
    site = Site(cfg)
    assert all(np.hypot(w[2] - w[0], w[3] - w[1]) >= 0.2 for w in site.geom.walls)           # the speck is dropped
    empty = service.solve(_cfg(preset="custom"))
    assert not empty["shield"]["on"] and any("add at least one plate" in w for w in empty["warnings"])
    assert empty["peak_b"] > 0


def test_custom_plates_follow_their_own_length_and_position():
    site = Site(_cfg(preset="custom", custom_plates=[[20, 0, 20, 12]], length_m=40.0, z_center_m=30.0))
    assert site.geom.z_center == 30.0 and site.geom.z_half == 20.0
    inside, outside = site.point(30.0, 5.0, 30.0), site.point(30.0, 5.0, -20.0)
    assert inside["eS"] < inside["e0"] and outside["eS"] == pytest.approx(outside["e0"])


def test_projects_saved_before_the_centre_was_shared_keep_their_position():
    """Until v4.1 only a custom layout could be moved along the line, under the name custom_z_m."""
    old = service.default_config()
    old["shield"].update({"enabled": True, "preset": "custom", "custom_plates": [[20, 0, 20, 12]], "custom_z_m": 30.0})
    del old["shield"]["z_center_m"]                               # an old file has no such key
    cfg = service.normalise_config(old)
    assert cfg["shield"]["z_center_m"] == 30.0 and "custom_z_m" not in cfg["shield"]
    assert Site(cfg).geom.z_center == 30.0


def test_shield_too_close_to_a_live_conductor_is_flagged():
    cond = Site(_cfg()).conductors[0]
    near = service.solve(_cfg(preset="custom", custom_plates=[[cond.x + 1.0, cond.y_sagged - 3, cond.x + 1.0, cond.y_sagged + 3]]))
    assert any("live conductor" in w for w in near["warnings"])
    assert not any("live conductor" in w for w in service.solve(_around())["warnings"])


def test_position_comparison_follows_the_arrangement():
    def labels(**kw):
        r = service.shield_sweep(_around(**kw), "distance")
        return r["xlabel"], [row["label"] for row in r["rows"]]
    assert labels()[0].startswith("Gap between the sheet") and labels()[1][0] == "0 m"
    assert labels(preset="surround-wall")[0].startswith("Gap between the wall")
    assert labels(preset="roof")[0].startswith("Height of the sheet")
    assert labels(preset="wall-between")[0] == "Distance from centreline"
    assert labels(preset="room")[1] == [] and labels(preset="custom", custom_plates=[[20, 0, 20, 9]])[1] == []
    listed = service.shield_sweep(_around(preset="custom", custom_plates=[[20, 0, 20, 9]]), "geometry")
    assert any(row["id"] == "custom" for row in listed["rows"])


# ------------------------------------- judged inside the building, placed fairly, moved along the line
def test_interior_average_is_a_true_area_average(monkeypatch):
    site = Site(_around())

    def fake(X, Y, z=0.0, want=("B", "E"), assume_shield=None):
        return {"b0": X * 1.0, "bS": X ** 2, "e0": np.ones_like(X), "eS": Y * 1.0}
    monkeypatch.setattr(site, "fields", fake)
    st = site.area_stats(10.0, 30.0, 0.0, 12.0, 0.0)
    a, b = 11.0, 29.0                                        # 1 m clear of the walls
    assert st["b"]["avg0"] == pytest.approx(20.0)            # exact for a field that varies linearly
    exact = (b ** 3 - a ** 3) / (3 * (b - a))
    assert st["b"]["avgS"] == pytest.approx(exact, rel=1e-3)
    plain_mean = float(np.mean(np.linspace(a, b, Site.AREA_GRID[0]) ** 2))
    assert abs(st["b"]["avgS"] - exact) < 0.1 * abs(plain_mean - exact)     # a plain mean over-weights the edges
    assert st["e"]["avg0"] == pytest.approx(1.0) and st["e"]["avgS"] == pytest.approx(6.0)
    assert st["b"]["max0"] == pytest.approx(29.0) and st["b"]["maxS"] == pytest.approx(841.0)
    assert st["b"]["reduction_pct"] == pytest.approx(sh.atten_pct(20.0, st["b"]["avgS"]))
    thin = site.area_stats(10.0, 11.0, 0.0, 12.0, 0.0)       # a narrow space keeps the margin inside itself
    assert thin["b"]["max0"] <= 10.75 and thin["b"]["avg0"] == pytest.approx(10.5)


def test_shield_headline_is_the_average_inside_the_building():
    cfg = _around()
    site = Site(cfg)
    head, zone = service.shield_headline(site), site.zone_stats()
    assert head["basis"] == "inside" and head["covered"] and head["where"] == site.buildings[0]["name"]
    assert head["b0"] == pytest.approx(zone["b"]["avg0"], rel=1e-5)
    assert head["bS"] == pytest.approx(zone["b"]["avgS"], rel=1e-5)
    assert head["b_red_pct"] == pytest.approx(zone["b"]["reduction_pct"], abs=1e-3)
    assert head["e_red_pct"] == pytest.approx(zone["e"]["reduction_pct"], abs=1e-3)
    sol = service.solve(cfg)
    assert sol["shield"]["headline"] == head
    probe = sol["shield"]["probe"]                           # one point, 1 m inside the wall facing the line
    assert probe["x"] == pytest.approx(site.buildings[0]["distance"] + 1.0)
    assert abs(probe["b_red_pct"] - head["b_red_pct"]) > 0.5              # a single point tells a different story
    assert service.shield_headline(Site(_around(enabled=False))) is None
    bare = _cfg()
    bare["buildings"] = []
    h2 = service.shield_headline(Site(service.normalise_config(bare)))
    assert h2["basis"] == "point" and "reference point" in h2["where"] and h2["bS"] < h2["b0"]


def test_a_free_standing_shield_can_be_moved_along_the_line():
    for preset in ("wall-between", "double-barrier", "mesh-barrier", "screen-wires", "passive-loop"):
        g = Site(_cfg(preset=preset, length_m=40.0, z_center_m=60.0)).geom
        assert (g.z_center, g.z_half) == (60.0, 20.0), preset
    site = Site(_cfg(length_m=40.0, z_center_m=60.0))
    at_shield, at_mid_span = site.point(30.0, 5.0, 60.0), site.point(30.0, 5.0, 0.0)
    assert at_shield["eS"] < 0.8 * at_shield["e0"] and at_shield["bS"] != pytest.approx(at_shield["b0"], rel=1e-3)
    assert at_mid_span["eS"] == pytest.approx(at_mid_span["e0"]) and at_mid_span["bS"] == pytest.approx(at_mid_span["b0"])
    # a sheet fixed to a building stays with the building whatever centre is given
    fixed = _around(z_center_m=60.0)
    fixed["buildings"][0]["z_offset"] = -25.0
    assert Site(service.normalise_config(fixed)).geom.z_center == -25.0


def test_a_shield_that_misses_the_building_along_the_line_says_so():
    cfg = _cfg(length_m=20.0, z_center_m=120.0)
    site = Site(cfg)
    assert not site.covers_building(0) and Site(_cfg()).covers_building(0)
    head = service.shield_headline(site)
    assert head["basis"] == "inside" and not head["covered"]
    assert head["b_red_pct"] == pytest.approx(0.0, abs=1e-6) and head["e_red_pct"] == pytest.approx(0.0, abs=1e-6)
    sol = service.solve(cfg)
    assert any("does not reach" in w and "Centre along the line" in w for w in sol["warnings"])
    assert not any("does not reach" in w for w in service.solve(_cfg())["warnings"])


def test_comparison_rows_give_the_inside_average_with_the_wall_point_beside_it():
    cfg = _around()
    site = Site(cfg)
    r = service.shield_sweep(cfg, "thickness")
    name = site.buildings[0]["name"]
    assert r["basis"] == "inside" and r["receptor"] == f"inside {name}" and r["probe"] == name
    st = site.building_stats(0)
    assert r["b0"] == pytest.approx(st["b"]["avg0"], rel=1e-5) and r["e0"] == pytest.approx(st["e"]["avg0"], rel=1e-5)
    for row in r["rows"]:
        assert row["basis"] == "inside" and row["where"] == name
        assert row["b0"] == pytest.approx(r["b0"]) and row["b_max0"] >= row["b0"] and row["b_maxS"] >= row["bS"]
        assert row["b_pt0"] > 0 and np.isfinite(row["b_pt_red_pct"]) and np.isfinite(row["e_pt_red_pct"])
    same = next(row for row in r["rows"] if row["label"] == "3 mm")        # the thickness in use
    assert same["bS"] == pytest.approx(site.zone_stats()["b"]["avgS"], rel=1e-5)
    # a single point can still be asked for, and then the row is that point
    at = service.shield_sweep(cfg, "thickness", {"x": 40.0, "y": 2.0, "z": 0.0})
    assert at["basis"] == "point" and at["receptor"] == "at the selected point"
    assert all(row["basis"] == "point" and row["b_max0"] is None and row["b0"] == row["b_pt0"] for row in at["rows"])
    models = service.shield_models(cfg)
    assert models["basis"] == "inside" and models["receptor"] == f"inside {name}"
    assert models["rows"][0]["bS"] == pytest.approx(same["bS"], rel=1e-5)


def test_studies_are_judged_on_the_building_the_shield_protects():
    cfg = _around()
    cfg["buildings"].append(dict(service.default_building(1), distance=90.0, name="Far depot"))
    cfg["shield"]["target_building"] = 1
    cfg = service.normalise_config(cfg)
    assert service.shield_sweep(cfg, "material")["receptor"] == "inside Far depot"
    other = service.shield_sweep(cfg, "material", 0)
    assert other["receptor"] == f"inside {cfg['buildings'][0]['name']}" and other["other_building"] == "Far depot"
    assert service.shield_assistant(cfg, target_b=0.5)["status"] in ("already", "reachable", "not_reachable")


def test_a_barrier_is_placed_beside_the_building_it_protects():
    cfg = _cfg()
    cfg["buildings"][0].update({"side": "left", "z_offset": 35.0, "height": 9.0, "depth": 24.0})
    site = Site(service.normalise_config(cfg))
    b = site.buildings[0]
    cands = service.barrier_candidates(site, 0)
    assert 1 <= len(cands) <= 4
    for c in cands:
        assert c["side"] == "left" and c["height_m"] == 9.0 and c["z_center_m"] == 35.0 and c["length_m"] == 44.0
        assert service._loop_clearance(site) + 3.0 <= c["distance_m"] <= b["distance"] - 1.0   # clear of the conductors
    best = service.best_barrier(site)
    assert best["changes"] in cands and best["tried"] == len(cands)
    placed = site.with_shield(enabled=True, preset="wall-between", **best["changes"])
    assert placed.covers_building(0) and all(w[0] < 0 for w in placed.geom.walls)
    got = placed.building_stats(0)["b"]["reduction_pct"]
    assert got == pytest.approx(best["reduction_pct"], abs=0.01)
    for c in cands:                                           # none of the others does better
        alt = site.with_shield(enabled=True, preset="wall-between", **c).building_stats(0)["b"]["reduction_pct"]
        assert alt <= got + 0.01
    s = service.suggestion(site, "double-barrier")
    assert s["changes"] == best["changes"] and b["name"] in s["note"] and "positions tried" in s["note"]
    bare = _cfg()
    bare["buildings"] = []
    assert service.suggestion(Site(service.normalise_config(bare)), "wall-between") == {"changes": {}, "note": ""}


def test_arrangement_comparison_places_every_option_fairly():
    """Up to v4.1 a barrier was compared wherever the last-used settings happened to leave it."""
    cfg = _around(distance_m=3.0, height_m=2.0, length_m=5.0)              # leftovers that would make a wall useless
    r = service.shield_sweep(cfg, "geometry")
    rows = {row["id"]: row for row in r["rows"] if row["id"] != "line"}
    assert [row["id"] for row in r["rows"] if row.get("in_use")] == ["enclosure"]
    assert "as you set it" in rows["enclosure"]["sub"]
    site = Site(cfg)
    b = site.buildings[0]
    wall = rows["wall-between"]
    assert wall["changes"]["height_m"] == b["height"] and wall["changes"]["length_m"] == b["depth"] + 20.0
    assert wall["changes"]["distance_m"] > 10.0 and wall["e_red_pct"] > 20 and abs(wall["b_red_pct"]) > 1.0
    assert "positions" in wall["sub"] or "m from the centreline" in wall["sub"]
    assert rows["mesh-barrier"]["changes"]["distance_m"] == wall["changes"]["distance_m"]
    assert rows["panel"]["changes"]["height_m"] == b["height"] and rows["surround-wall"]["changes"]["standoff_m"] == 2.0
    # "Use" applies exactly what the row was solved with
    for key in ("wall-between", "panel", "screen-wires", "passive-loop"):
        c2 = copy.deepcopy(cfg)
        c2["shield"].update(rows[key]["changes"], enabled=True)
        st = Site(service.normalise_config(c2)).building_stats(0)
        assert st["b"]["avgS"] == pytest.approx(rows[key]["bS"], rel=1e-4), key
        assert st["e"]["avgS"] == pytest.approx(rows[key]["eS"], rel=1e-4, abs=1e-6), key
    assert "standard placement" in r["note"]


@pytest.mark.parametrize("ground", [earth.FREE_SPACE, earth.PERFECT_CONDUCTOR, earth.COMPLEX_IMAGE])
@pytest.mark.parametrize("shield", [
    dict(preset="enclosure"), dict(preset="envelope", material_id="mildsteel", thickness_mm=6.0),
    dict(preset="wall-between", material_id="mildsteel", thickness_mm=6.0), dict(preset="passive-loop")])
def test_the_potential_drawn_as_field_lines_is_the_solved_field(ground, shield):
    """B = curl(A z). If the contours of A are the field lines, its curl must be the field the solver reports."""
    cfg = _around(**shield)
    cfg["corridor"]["ground_model"] = ground
    site = Site(service.normalise_config(cfg))
    mag, _ = site.solution(site.geom.z_center)
    X, Y = np.meshgrid(np.linspace(-40.0, 80.0, 25), np.linspace(0.6, 40.0, 13))
    keep = np.ones(X.shape, bool)
    for x1, y1, x2, y2 in site.geom.walls:                   # stay off the sheets and the wires themselves
        dx, dy = x2 - x1, y2 - y1
        t = np.clip(((X - x1) * dx + (Y - y1) * dy) / (dx * dx + dy * dy), 0.0, 1.0)
        keep &= np.hypot(X - (x1 + t * dx), Y - (y1 + t * dy)) > 1.0
    for wx, wy in site.geom.wires:
        keep &= np.hypot(X - wx, Y - wy) > 1.0
    for c in site.conductors:
        keep &= np.hypot(X - c.x, Y - c.y_sagged) > 1.5
    X, Y = X[keep], Y[keep]
    h = 1e-3
    bx = (mag.a_total(X, Y + h) - mag.a_total(X, Y - h)) / (2 * h)
    by = -(mag.a_total(X + h, Y) - mag.a_total(X - h, Y)) / (2 * h)
    want_x, want_y = mag.b_total(X, Y)
    _, sx, sy = shield_bem.source_abh(site.conductors, X, Y, site.ground_model, site.earth_rho, site.freq)
    err = np.hypot(np.abs(bx - want_x), np.abs(by - want_y)) / np.hypot(np.abs(sx), np.abs(sy))
    assert X.size > 250 and float(np.median(err)) < 1e-6 and float(err.max()) < 1e-3
    # and the shield really is in it: without the induced part the curl is the bare line's field
    shielded = np.hypot(np.abs(want_x), np.abs(want_y))
    assert float(np.max(np.abs(shielded - np.hypot(np.abs(sx), np.abs(sy))) / np.hypot(np.abs(sx), np.abs(sy)))) > 0.02
