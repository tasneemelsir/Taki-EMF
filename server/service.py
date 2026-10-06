"""
service.py
==========
Turns a project configuration (plain JSON) into results (plain JSON) by calling
the engine. Nothing here knows about HTTP or accounts; server/main.py wraps
these functions as API routes.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import os
import threading
from collections import OrderedDict
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine import (benchmarks, earth, field_lines, libraries, lines as lines_mod, physics,
                    references, shield_engine as sh, shielding, standards, validation)
from engine.site import Site, normalise_building

from . import config

SCHEMA = 4
MAX_POINTS = 60


# ---------------------------------------------------------------------------
# Defaults and migration
# ---------------------------------------------------------------------------
def default_building(i: int = 0) -> dict:
    types = list(libraries.BUILDING_TYPES)
    t = "Data centre" if i == 0 else types[i % len(types)]
    bt = libraries.BUILDING_TYPES[t]
    if i == 0:
        return {"name": "Data Center", "type": "Data centre", "shape": "box", "roof": "flat",
                "width": 40.0, "depth": 20.0, "height": 15.0, "distance": 25.0, "side": "right",
                "z_offset": 0.0, "material": "none", "b_pct": None, "e_pct": None, "floor_h": None}
    return {"name": f"Building {i + 1}", "type": t, "shape": "box", "roof": bt["roof"],
            "width": float(bt["width"]), "depth": float(bt["depth"]), "height": float(bt["height"]),
            "distance": 25.0 + i * 20.0, "side": "right" if i % 2 == 0 else "left",
            "z_offset": 0.0, "material": "none", "b_pct": None, "e_pct": None, "floor_h": None}


def default_shield() -> dict:
    return {"enabled": False, "preset": sh.DEFAULT_PRESET, "side": "right", "target_building": 0,
            "standoff_m": 2.0, "gap_m": 0.0, "roof_gap_m": 0.0, "floor_level_m": sh.FLOOR_M,
            "custom_plates": [], "z_center_m": 0.0,
            "room_width_m": 8.0, "room_height_m": 3.2, "room_depth_m": 6.0, "room_offset_m": 2.0,
            "room_floor_m": 0.2, "loop_spacing_m": 6.0, "loop_vertical": True,
            "loop_compensation_pct": 0.0, "wire_mm2": 400.0, "wire_count": 5, "screen_width_m": 20.0,
            "layer2_material_id": None,
            "material_id": "aluminium", "custom_material": {"label": "Custom material",
                                                            "sigma": 1.0e7, "mu_r": 1.0},
            "model": "physical", "thickness_mm": 3.0, "layers": 1, "layer_spacing_m": 0.10,
            "coverage_pct": 100.0, "mesh": False, "aperture_mm": 5.0, "pitch_mm": 10.0,
            "grounded": True, "bonded": True, "distance_m": 18.0, "height_m": 12.0,
            "length_m": 60.0, "emp_b_pct": None, "emp_e_pct": None}


def default_config() -> dict:
    return {
        "schema": SCHEMA,
        "corridor": {"row_half_width": 12.0, "span_m": 300.0, "max_sag_m": 1.5, "freq_hz": 50.0,
                     "meas_height": 1.0, "ground_model": earth.DEFAULT_MODEL, "earth_rho": 100.0,
                     "soil_type": "farmland", "bundle_eq": True, "sag_follows_span": False},
        "lines": [lines_mod.default_line()],
        "buildings": [default_building(0)],
        "shield": default_shield(),
        "standards": list(standards.DEFAULT_STANDARD_IDS),
        "points": [],
        "twin": {"iso_level_uT": 2.0},
        "numerics": {"x_half_width": 0, "y_max": 0, "grid_nx": 141, "grid_ny": 81},
    }


def _deep_fill(target: dict, defaults: dict) -> dict:
    for k, v in defaults.items():
        if k not in target or target[k] is None and v is not None and not isinstance(v, (int, float)):
            target[k] = copy.deepcopy(v)
        elif isinstance(v, dict) and isinstance(target[k], dict):
            _deep_fill(target[k], v)
    return target


def migrate_legacy(sc: dict) -> dict:
    """
    Convert a scenario exported by the Streamlit versions of Taki (v1/v2 files
    with 'lines', 'max_sag_m', 'row_boundary_m' and a flat 'settings' block of
    widget keys) into the current project configuration.
    """
    cfg = default_config()
    ss = sc.get("settings") or {}
    cor = cfg["corridor"]
    cor["max_sag_m"] = float(sc.get("max_sag_m", 1.5))
    cor["row_half_width"] = float(sc.get("row_boundary_m", 12))
    for src, dst in (("ground_model", "ground_model"), ("earth_rho", "earth_rho"),
                     ("freq_hz", "freq_hz"), ("bundle_eq", "bundle_eq"), ("meas_height", "meas_height")):
        if src in ss:
            cor[dst] = ss[src]
    cfg["lines"] = []
    for i, ln in enumerate(sc.get("lines") or []):
        d = lines_mod.default_line(index=i, count=len(sc["lines"]))
        d.update({"preset": ln.get("preset_name") or ln.get("preset") or d["preset"],
                  "x_offset": float(ln.get("x_offset", 0)), "load_pct": float(ln.get("load", 100)),
                  "arrangement": ln.get("arrangement", "ABC-CBA"),
                  "current_a": float(ln.get("current_override", 0) or 0),
                  "voltage_kv": float(ln.get("voltage_override", 0) or 0),
                  "phase_offset_deg": float(ln.get("phase_offset", ss.get(f"poff_{i}", 0)) or 0)})
        cfg["lines"].append(d)
    if not cfg["lines"]:
        cfg["lines"] = [lines_mod.default_line()]
    n_b = int(ss.get("num_buildings", 0) or 0)
    if n_b:
        cfg["buildings"] = []
        for i in range(n_b):
            cfg["buildings"].append({
                "name": ss.get(f"bname_{i}", f"Building {i + 1}"), "shape": ss.get(f"bshape_{i}", "box"),
                "type": ss.get(f"btype_{i}", "Warehouse"), "roof": "flat",
                "width": float(ss.get(f"bw_{i}", 40)), "depth": float(ss.get(f"bd_{i}", 20)),
                "height": float(ss.get(f"bh_{i}", 15)), "distance": float(ss.get(f"bdist_{i}", 25 + 20 * i)),
                "side": "right", "z_offset": float(ss.get(f"bzoff_{i}", 0)),
                "material": ss.get(f"bmat_{i}", "none"), "b_pct": ss.get(f"bpct_{i}"),
                "e_pct": ss.get(f"epct_{i}")})
    if "std_ids" in ss:
        cfg["standards"] = [standards.resolve_id(s) for s in ss["std_ids"]]
    shd = cfg["shield"]
    for src, dst in (("sh_on", "enabled"), ("sh_preset", "preset"), ("sh_side", "side"),
                     ("sh_mat", "material_id"), ("sh_basis", "model"), ("sh_t", "thickness_mm"),
                     ("sh_layers", "layers"), ("sh_dist", "distance_m"), ("sh_h", "height_m"),
                     ("sh_len", "length_m"), ("sh_cov", "coverage_pct"), ("sh_ap", "aperture_mm"),
                     ("sh_pitch", "pitch_mm"), ("sh_gnd", "grounded"), ("sh_cont", "bonded"),
                     ("sh_target", "target_building"), ("sh_bpct", "emp_b_pct"), ("sh_epct", "emp_e_pct")):
        if src in ss:
            shd[dst] = ss[src]
    if "iso_thr" in ss:
        cfg["twin"]["iso_level_uT"] = float(ss["iso_thr"])
    if isinstance(ss.get("pins"), list):
        cfg["points"] = [{"x": float(p.get("x", 0)), "y": float(p.get("y", 1)), "z": float(p.get("z", 0)),
                          "label": str(p.get("label", ""))} for p in ss["pins"][:MAX_POINTS]]
    cfg["migrated_from"] = f"Taki scenario schema {sc.get('schema_version', 1)}"
    return cfg


def normalise_config(cfg: Optional[dict]) -> dict:
    """Fill defaults, migrate old files, and clamp list sizes. Never raises on odd input."""
    if not isinstance(cfg, dict):
        return default_config()
    if "corridor" not in cfg and "lines" in cfg and ("max_sag_m" in cfg or "settings" in cfg
                                                    or "num_lines" in cfg):
        cfg = migrate_legacy(cfg)
    cfg = copy.deepcopy(cfg)
    d = default_config()
    shd = cfg.get("shield")
    if isinstance(shd, dict) and "custom_z_m" in shd:
        # until v4.1 only custom layouts could be moved along the line, under this name
        old_z = shd.pop("custom_z_m")
        if shd.get("z_center_m") is None:
            shd["z_center_m"] = old_z
    for key in ("corridor", "shield", "twin", "numerics"):
        if not isinstance(cfg.get(key), dict):
            cfg[key] = {}
        _deep_fill(cfg[key], d[key])
    cfg["corridor"]["sag_follows_span"] = bool(cfg["corridor"].get("sag_follows_span", False))
    if not isinstance(cfg.get("lines"), list) or not cfg["lines"]:
        cfg["lines"] = d["lines"]
    cfg["lines"] = cfg["lines"][:4]
    presets = lines_mod.tower_presets()
    for i, ln in enumerate(cfg["lines"]):
        base = lines_mod.default_line(index=i, count=len(cfg["lines"]))
        if not isinstance(ln, dict):
            cfg["lines"][i] = base
            continue
        if "preset" not in ln and "preset_name" in ln:
            ln["preset"] = ln["preset_name"]
        if "load_pct" not in ln and "load" in ln:
            ln["load_pct"] = ln["load"]
        for k, v in base.items():
            if k not in ln or ln[k] is None:
                ln[k] = copy.deepcopy(v) if k != "x_offset" else v
        if not isinstance(ln.get("custom"), dict):
            ln["custom"] = dict(lines_mod.DEFAULT_CUSTOM)
        else:
            for k, v in lines_mod.DEFAULT_CUSTOM.items():
                ln["custom"].setdefault(k, v)
        if ln["preset"] != lines_mod.CUSTOM and ln["preset"] not in presets:
            ln["preset_missing"] = ln["preset"]
            ln["preset"] = list(presets)[0]
        # per-circuit settings: one clean entry per circuit of this tower, or none
        tower = lines_mod.tower_of(ln, presets)
        ids = lines_mod.circuit_ids(tower["conductors"]) if tower else [1]
        try:
            load = float(ln.get("load_pct", 100.0))
        except (TypeError, ValueError):
            load = 100.0
        orders = lines_mod.arrangement_orders(ids, ln.get("arrangement", "ABC-CBA"),
                                              tower.get("swap_circuits") if tower else None)
        ln["circuits"] = lines_mod.clean_circuits(ln.get("circuits"), len(ids), load, [orders[i] for i in ids])
    if not isinstance(cfg.get("buildings"), list):
        cfg["buildings"] = d["buildings"]
    cfg["buildings"] = [normalise_building(b, i) for i, b in enumerate(cfg["buildings"][:6])
                        if isinstance(b, dict)]
    if not isinstance(cfg.get("standards"), list):
        cfg["standards"] = d["standards"]
    known = standards.get_standards()
    seen, std = set(), []
    for s in cfg["standards"]:
        s = standards.resolve_id(str(s))
        if s in known and s not in seen:
            seen.add(s); std.append(s)
    cfg["standards"] = std
    pts = []
    for p in (cfg.get("points") or [])[:MAX_POINTS]:
        try:
            pts.append({"x": float(p["x"]), "y": max(0.0, float(p["y"])), "z": float(p.get("z", 0.0)),
                        "label": str(p.get("label", ""))[:40]})
        except (KeyError, TypeError, ValueError):
            continue
    cfg["points"] = pts
    # custom shield plates: keep only well-formed segments, as plain lists
    cfg["shield"]["custom_plates"] = [list(seg) for seg in sh.config_from_dict(cfg["shield"]).custom_plates]
    cfg["schema"] = SCHEMA
    return cfg


# ---------------------------------------------------------------------------
# Site cache
# ---------------------------------------------------------------------------
_PHYS_KEYS = ("corridor", "lines", "buildings", "shield", "standards", "numerics")
_cache: "OrderedDict[str, Site]" = OrderedDict()
_cache_lock = threading.Lock()
_CACHE_SIZE = 32


def config_hash(cfg: dict) -> str:
    blob = json.dumps({k: cfg.get(k) for k in _PHYS_KEYS}, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def site_for(cfg: dict) -> Site:
    """Resolved, cached Site for a (normalised) configuration."""
    key = config_hash(cfg)
    with _cache_lock:
        s = _cache.get(key)
        if s is not None:
            _cache.move_to_end(key)
            return s
    s = Site(cfg)
    s.lock = threading.RLock()          # type: ignore[attr-defined]
    s.key = key                         # type: ignore[attr-defined]
    with _cache_lock:
        _cache[key] = s
        while len(_cache) > _CACHE_SIZE:
            _cache.popitem(last=False)
    return s


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------
def arr(a, nd: int = 5) -> list:
    a = np.asarray(a, float)
    a = np.where(np.isfinite(a), a, 0.0)
    return np.round(a, nd).tolist()


def b64(a) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype="<f4").tobytes()).decode("ascii")


def _num(v, nd=6):
    if v is None:
        return None
    v = float(v)
    return round(v, nd) if math.isfinite(v) else None


def _q(q) -> dict:
    return {"value": _num(q.value), "limit": _num(q.limit), "status": q.status,
            "pct": _num(q.percent_of_limit, 3), "headroom": _num(q.headroom_percent, 3)}


def results_json(results) -> list:
    out = []
    for r in results:
        s = r.standard
        g = r.governing
        out.append({"id": s.id, "name": s.name, "jurisdiction": s.jurisdiction, "year": s.year,
                    "kind": s.kind, "population": s.population,
                    "needs_verification": s.needs_verification, "source": s.source, "url": s.url,
                    "notes": s.notes, "overall": r.overall, "b": _q(r.b), "e": _q(r.e),
                    "governing": g.quantity if g else None})
    return out


def lines_json(site: Site) -> list:
    out = []
    for ln, cfg in zip(site.lines, site.line_cfgs):
        out.append({
            "name": ln.name, "preset": ln.preset_name, "description": ln.description,
            "tower": ln.tower, "xc": _num(ln.x_centre, 3), "x_offset": ln.x_offset,
            "kv": ln.voltage_kv, "rated_a": ln.rated_current_a, "operating_a": ln.operating_current_a,
            "load_pct": ln.load_pct, "arrangement": ln.arrangement, "is_double": ln.is_double,
            "phase_offset_deg": ln.phase_offset_deg, "thermal_sag_m": _num(ln.thermal_sag_m, 3),
            "design_sag_m": _num(ln.design_sag_m, 3), "radius_m": ln.radius_m, "row_width_m": ln.row_width_m,
            "loading_context": libraries.loading_context(ln.load_pct),
            # each circuit of the tower as resolved; "separate" = they were set one by one
            "separate": ln.separate,
            "circuits": [{"id": k.id, "label": k.label, "on": k.on, "kv": k.voltage_kv,
                          "rated_a": k.rated_current_a, "operating_a": _num(k.operating_current_a, 2),
                          "load_pct": k.load_pct, "thermal_sag_m": _num(k.thermal_sag_m, 3),
                          "phase_order": k.phase_order} for k in ln.circuits],
            "min_height_m": _num(ln.min_height_m, 3), "clearance_m": _num(ln.required_clearance_m, 2),
            "conductors": [{"x": _num(c.x, 4), "y": _num(c.y_sagged, 4), "y_att": _num(ya, 4),
                            "phase": c.phase, "circuit": int(c.circuit), "on": bool(on),
                            "current_a": _num(c.current_A, 2), "voltage_kv": _num(c.voltage_kV, 2),
                            "bundle": [[float(dx), float(dy)] for dx, dy in (c.bundle_offsets or [])]}
                           for c, ya, on in zip(ln.conductors, ln.attach_heights, ln.energised)],
        })
    return out


def clearance_json(site: Site) -> Optional[dict]:
    """The lowest conductor at mid-span, and an indicative minimum for its voltage."""
    if not site.lines:
        return None
    ln = min(site.lines, key=lambda l: l.min_height_m - l.required_clearance_m)
    low = min(site.lines, key=lambda l: l.min_height_m)
    return {"min_height_m": _num(low.min_height_m, 3), "line": low.name,
            "tightest_line": ln.name, "tightest_height_m": _num(ln.min_height_m, 3),
            "required_m": _num(ln.required_clearance_m, 2),
            "ok": bool(ln.min_height_m >= ln.required_clearance_m - 1e-9)}


def shield_clearance(site: Site) -> Optional[Tuple[float, float]]:
    """(closest approach of the shield to a phase conductor, indicative clearance to keep), in metres."""
    if not site.shield_on:
        return None
    conds = site.conductors_at(site.geom.z_center if site.geom.covers_z(site.geom.z_center) else 0.0)
    best = None
    for x1, y1, x2, y2 in site.geom.walls:
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        for c in conds:
            t = 0.0 if l2 <= 0 else min(1.0, max(0.0, ((c.x - x1) * dx + (c.y_sagged - y1) * dy) / l2))
            d = math.hypot(c.x - (x1 + t * dx), c.y_sagged - (y1 + t * dy))
            best = d if best is None else min(best, d)
    return None if best is None else (best, _loop_clearance(site))


def shield_headline(site: Site) -> Optional[dict]:
    """
    What the shield does where it matters - for the top bar, the scenario table
    and the report: the change in the AVERAGE field inside the protected space
    (the building, or the shielded room). Without a building it is read at the
    reference point behind the barrier, and basis = "point".
    """
    if not site.shield_on:
        return None
    st = site.zone_stats()
    if st is not None:
        covered = site.geom.zone is not None or site.covers_building(site.shield_cfg.target_building)
        return {"basis": "inside", "where": st["label"], "covered": bool(covered),
                "b0": _num(st["b"]["avg0"]), "bS": _num(st["b"]["avgS"]),
                "e0": _num(st["e"]["avg0"]), "eS": _num(st["e"]["avgS"]),
                "b_red_pct": _num(st["b"]["reduction_pct"], 3), "e_red_pct": _num(st["e"]["reduction_pct"], 3)}
    ref = site.shield_reference_point()
    if ref is None:
        return None
    r = site.point(*ref)
    return {"basis": "point", "where": f"the reference point behind the barrier (x = {ref[0]:.1f} m, y = {ref[1]:.1f} m)",
            "covered": True, "b0": _num(r["b0"]), "bS": _num(r["bS"]), "e0": _num(r["e0"]), "eS": _num(r["eS"]),
            "b_red_pct": _num(sh.atten_pct(r["b0"], r["bS"]), 3), "e_red_pct": _num(sh.atten_pct(r["e0"], r["eS"]), 3)}


def shield_json(site: Site) -> dict:
    cfg, geom = site.shield_cfg, site.geom
    mat = cfg.material
    se = site.shield_se() if site.shield_on else site.se_simple
    props = None
    extra = {}
    if site.shield_on and site.physical:
        from engine import shield_bem
        mag, ele = site.solution(geom.z_center)
        if ele is not None:
            extra["floating_kv"] = _num(ele.floating_voltage_kv, 4)
            extra["earth_ma_per_m"] = _num(ele.earth_current_ma_per_m(site.freq), 5)
            extra["relaxation"] = _num(abs(ele.kappa), 5)
        if mag is not None:
            extra["max_sheet_current_a_per_m"] = _num(mag.max_sheet_current, 3)
            extra["loss_w_per_m"] = _num(mag.loss_w_per_m(), 4)
            extra["elements"] = int(mag.mesh.n)
            if cfg.is_wire:
                cur = np.abs(mag.plate_currents())
                extra["loop_current_a"] = _num(float(cur.max()) if cur.size else 0.0, 3)
    simple = site.se_simple
    return {
        "on": site.shield_on, "enabled": bool(cfg.enabled), "model": cfg.model,
        "model_label": sh.MODELS[cfg.model], "preset": cfg.preset,
        "label": geom.description, "attached": sh.PRESETS[cfg.preset]["attached"],
        "surrounding": cfg.preset in sh.SURROUNDING, "preset_label": sh.PRESETS[cfg.preset]["label"],
        "target_building": int(cfg.target_building), "is_wire": cfg.is_wire, "is_custom": cfg.is_custom,
        "gap_m": cfg.gap_m, "roof_gap_m": cfg.roof_gap_m,
        "wires": [[_num(x, 4), _num(y, 4)] for x, y in geom.wires],
        "wire_mm2": cfg.wire_mm2, "wire_radius_mm": _num(cfg.wire_radius_m * 1000.0, 3),
        "compensation_pct": cfg.loop_compensation_pct if cfg.is_wire else 0.0,
        "room": [_num(v, 3) for v in geom.zone] if geom.zone is not None else None,
        "layer2": cfg.layer2_material.label if cfg.layer2_material is not None else None,
        "protected": _zone_json(site) if site.shield_on else None,
        "headline": shield_headline(site),
        "mesh": cfg.is_mesh, "walls": [[_num(v, 4) for v in w] for w in geom.walls],
        "zc": geom.z_center, "zh": geom.z_half, "grounded": cfg.grounded, "bonded": cfg.continuous,
        "z_center_m": cfg.z_center_m,
        "material": {"id": mat.id, "label": mat.label, "category": mat.category, "sigma": mat.sigma,
                     "mu_r": mat.mu_r, "quality": mat.quality, "mechanisms": mat.mechanisms,
                     "limitations": mat.limitations},
        "thickness_mm": cfg.thickness_m * 1000.0, "layers": cfg.layers,
        "coverage_pct": cfg.coverage_pct, "fill": _num(cfg.fill_factor, 4),
        "skin_depth_mm": _num(sh.skin_depth(mat, site.freq) * 1000.0, 4)
        if math.isfinite(sh.skin_depth(mat, site.freq)) else None,
        "se_b": _num(se.se_b, 3), "se_e": _num(se.se_e, 3), "basis_used": se.basis_used,
        "note": se.note, "ref_point": list(se.ref_point) if se.ref_point else None,
        "ref_xyz": list(site.shield_reference_point() or []) or None,
        "probe": _probe_json(site),
        "analytical": {"se_b": _num(simple.se_b, 3), "se_e": _num(simple.se_e, 3),
                       "absorption": _num(simple.absorption, 3),
                       "reflection_e": _num(simple.reflection_e, 3),
                       "reflection_h": _num(simple.reflection_h, 3),
                       "multi_refl": _num(simple.multi_refl, 3), "ceiling": _num(simple.ceiling, 3),
                       "limited_by_e": simple.limited_by_e, "limited_by_b": simple.limited_by_b,
                       "basis": simple.basis_used, "note": simple.note},
        "source_distance_m": _num(geom.source_distance_m, 3),
        "no_geometry": bool(cfg.enabled and not geom.walls),
        **extra,
    }


def _probe_json(site: Site) -> Optional[dict]:
    """The field at the single reference point, without and with the shield (a secondary read-out)."""
    ref = site.shield_reference_point() if site.shield_on else None
    if ref is None:
        return None
    r = site.point(*ref)
    return {"x": _num(ref[0], 3), "y": _num(ref[1], 3), "z": _num(ref[2], 3),
            "b0": _num(r["b0"]), "bS": _num(r["bS"]), "e0": _num(r["e0"]), "eS": _num(r["eS"]),
            "b_red_pct": _num(sh.atten_pct(r["b0"], r["bS"]), 3), "e_red_pct": _num(sh.atten_pct(r["e0"], r["eS"]), 3)}


def _zone_json(site: Site) -> Optional[dict]:
    z = site.zone_stats()
    if z is None:
        return None
    return {"label": z["label"], "box": [_num(v, 3) for v in z["box"]], "z": _num(z["z"], 3),
            "b": {k: _num(v) for k, v in z["b"].items()}, "e": {k: _num(v) for k, v in z["e"].items()}}


def receptors_json(site: Site) -> list:
    out = []
    for r in site.receptors():
        out.append({k: (_num(v) if isinstance(v, (float, np.floating)) else v) for k, v in r.items()})
    return out


# ---------------------------------------------------------------------------
# Core solve
# ---------------------------------------------------------------------------
def solve(cfg: dict) -> dict:
    site = site_for(cfg)
    with site.lock:
        sm = site.summary()
        prof = site.profile()
        gov, gq = sm["governing"], sm["governing_q"]
        b_res = sm["binding"]
        warnings = list(site.warnings)
        for i, ln in enumerate(cfg.get("lines", [])):
            if ln.get("preset_missing"):
                warnings.append(f"Line {i + 1} referenced the tower preset '{ln['preset_missing']}', "
                                "which is not available; the first preset was used.")
        if not site.standard_ids:
            warnings.append("No standard is selected, so compliance cannot be assessed.")
        if site.shield_on and sm["peak_b_shield"] > 1.05 * sm["peak_b"]:
            warnings.append(
                f"Right beside the shield the magnetic field is higher than without it (up to "
                f"{sm['peak_b_shield']:.2f} µT at {site.meas_height:g} m above ground): the induced "
                "currents concentrate at the edges and corners of the sheet. The reduction is "
                + ("inside the building." if sh.PRESETS[site.shield_cfg.preset]["attached"]
                   else "behind the barrier, not next to it."))
        if site.shield_cfg.enabled and not site.geom.walls:
            warnings.append("The shield is switched on but has no geometry: "
                            + ("add at least one plate to the custom layout." if site.shield_cfg.is_custom
                               else "this arrangement needs a building to attach to."))
        if (site.shield_on and site.buildings and site.geom.zone is None
                and not site.covers_building(site.shield_cfg.target_building)):
            b = site.buildings[min(site.shield_cfg.target_building, len(site.buildings) - 1)]
            warnings.append(
                f"The shield does not reach {b['name']} along the line: it covers z = "
                f"{site.geom.z_center - site.geom.z_half:g} to {site.geom.z_center + site.geom.z_half:g} m and the "
                f"building is at z = {b['z_offset']:g} m, so it does nothing for it. Move the shield "
                "(\"Centre along the line\") or make it longer.")
        near = shield_clearance(site)
        if near is not None and near[0] < near[1]:
            warnings.append(f"The shield comes within {near[0]:.1f} m of a live conductor. Keep it at least "
                            f"{near[1]:.1f} m clear at this voltage (an indicative working clearance; the line "
                            "owner sets the real one), or the result has no practical meaning.")
        for b in site.buildings:
            if b["distance"] < site.row_half:
                warnings.append(f"{b['name']} is {b['distance']:g} m from the centreline, inside "
                                f"the +/-{site.row_half:g} m right-of-way.")
        info = earth.MODEL_INFO[site.ground_model]
        return {
            "hash": site.key,
            "peak_b": _num(sm["peak_b"]), "peak_e": _num(sm["peak_e"]),
            "peak_b_x": _num(sm["peak_b_x"], 3), "peak_e_x": _num(sm["peak_e_x"], 3),
            "peak_b_shield": _num(sm["peak_b_shield"]), "peak_e_shield": _num(sm["peak_e_shield"]),
            "row_b": _num(sm["row_b"]), "row_e": _num(sm["row_e"]),
            "overall": sm["overall"], "results": results_json(sm["results"]),
            "governing": {"standard": gov.standard.name, "id": gov.standard.id,
                          "quantity": gq.quantity, "value": _num(gq.value), "limit": _num(gq.limit),
                          "unit": "µT" if gq.unit == "uT" else gq.unit,
                          "pct": _num(gq.percent_of_limit, 3),
                          "headroom": _num(gq.headroom_percent, 3), "status": gq.status}
            if gov is not None else None,
            "binding_b": {"standard": b_res.standard.name, "limit": _num(b_res.b.limit),
                          "headroom": _num(b_res.b.headroom_percent, 3), "status": b_res.b.status}
            if b_res is not None else None,
            "profile": {"x": arr(prof["x"], 3), "b0": arr(prof["b0"]), "e0": arr(prof["e0"]),
                        "bS": arr(prof["bS"]), "eS": arr(prof["eS"])},
            "domain": {"x_min": site.x_min, "x_max": site.x_max, "y_max": site.y_max},
            "clearance": clearance_json(site),
            "corridor": {"row_half": site.row_half, "meas_height": site.meas_height,
                         "freq": site.freq, "half_span": site.half_span,
                         "sag_follows_span": site.sag_follows_span, "sag_scale": _num(site.sag_scale, 4),
                         "max_sag_m": site.max_sag,
                         "ground_model": site.ground_model, "ground_label": info["label"],
                         "ground_short": info["short"], "ground_validated": info["validated"],
                         "ground_note": site.earth_note(), "bundle_eq": site.bundle_eq},
            "lines": lines_json(site),
            "receptors": receptors_json(site),
            "shield": shield_json(site),
            "warnings": warnings,
        }


def grid(cfg: dict, z: float = 0.0, nx: Optional[int] = None, ny: Optional[int] = None) -> dict:
    site = site_for(cfg)
    with site.lock:
        g = site.grid(z=float(z), nx=nx, ny=ny)
        return {"hash": site.key, "z": float(z), "x0": float(g["x"][0]), "x1": float(g["x"][-1]),
                "y0": float(g["y"][0]), "y1": float(g["y"][-1]),
                "nx": int(g["x"].size), "ny": int(g["y"].size),
                "b0": b64(g["b0"]), "bS": b64(g["bS"]), "e0": b64(g["e0"]), "eS": b64(g["eS"]),
                "max_b": _num(np.max(g["b0"])), "max_e": _num(np.max(g["e0"])),
                "shield_here": site.shield_at(float(z))}


def points(cfg: dict, pts: Optional[List[dict]] = None) -> dict:
    site = site_for(cfg)
    pts = cfg.get("points", []) if pts is None else pts
    pts = pts[:MAX_POINTS]
    with site.lock:
        sm = site.summary()
        vals = site.at_points([(float(p["x"]), float(p["y"]), float(p.get("z", 0.0))) for p in pts]) if pts else []
        gov = sm["binding"]
        b_lim = gov.b.limit if gov else None
        e_lims = [r.e.limit for r in sm["results"] if r.e.limit is not None]
        e_lim = min(e_lims) if e_lims else None
        rows = []
        for i, (p, v) in enumerate(zip(pts, vals)):
            rows.append({
                "n": i + 1, "label": p.get("label", ""), "x": float(p["x"]), "y": float(p["y"]),
                "z": float(p.get("z", 0.0)),
                "b0": _num(v["b0"]), "bS": _num(v["bS"]), "e0": _num(v["e0"]), "eS": _num(v["eS"]),
                "b_red_pct": _num(sh.atten_pct(v["b0"], v["bS"]), 3),
                "e_red_pct": _num(sh.atten_pct(v["e0"], v["eS"]), 3),
                "b_se_db": _num(sh.se_db(v["b0"], v["bS"]), 3), "e_se_db": _num(sh.se_db(v["e0"], v["eS"]), 3),
                "b_pct_limit": _num(100.0 * v["b0"] / b_lim, 3) if b_lim else None,
                "e_pct_limit": _num(100.0 * v["e0"] / e_lim, 3) if e_lim else None,
                "in_shield_length": site.shield_at(float(p.get("z", 0.0))),
            })
        return {"hash": site.key, "rows": rows, "b_limit": _num(b_lim), "e_limit": _num(e_lim),
                "b_limit_name": gov.standard.name if gov else None}


def earth_envelope(cfg: dict) -> dict:
    site = site_for(cfg)
    with site.lock:
        x = site.profile()["x"]
        free = site.with_ground(earth.FREE_SPACE).profile()["b0"]
        perf = site.with_ground(earth.PERFECT_CONDUCTOR).profile()["b0"]
        sel = site.profile()["b0"] if site.ground_model == earth.COMPLEX_IMAGE else None
        # resistivity sweep through the complex-image model: how the peak moves with soil
        sweep = []
        for soil in libraries.SOIL_TYPES:
            c2 = copy.deepcopy(cfg)
            c2["corridor"]["ground_model"] = earth.COMPLEX_IMAGE
            c2["corridor"]["earth_rho"] = soil.resistivity
            sweep.append({"soil": soil.name, "rho": soil.resistivity,
                          "peak_b": _num(Site(c2).summary()["peak_b"])})
        pf, pp = float(np.max(free)), float(np.max(perf))
        return {"hash": site.key, "x": arr(x, 3), "free": arr(free), "perfect": arr(perf),
                "selected": arr(sel) if sel is not None else None,
                "selected_label": site.earth_note(), "peak_free": _num(pf), "peak_perfect": _num(pp),
                "ratio": _num(pp / pf, 4) if pf > 0 else None, "soil_sweep": sweep,
                "models": {k: v for k, v in earth.MODEL_INFO.items()}}


def fieldlines(cfg: dict) -> dict:
    """
    The complex vector potential over the cross-section, without and with the
    shield. Its contours at any instant are the magnetic field lines, so the
    browser draws and animates them without another request. Values are in
    µWb/m. Taken at mid-span, or through the shield when it does not reach
    mid-span.
    """
    site = site_for(cfg)
    with site.lock:
        hit = site._memo.get("fieldlines")
        if hit is not None:
            return hit
        z, mag = 0.0, None
        if site.shield_on and site.physical:
            z = 0.0 if site.shield_at(0.0) else float(site.geom.z_center)
            mag, _ = site.solution(z)
        conds = site.conductors_at(z)
        x, y, a0 = field_lines.potential_grid(conds, (site.x_min, site.x_max), (0.0, site.y_max),
                                              site.ground_model, site.earth_rho, site.freq)
        a_s = None
        if mag is not None:
            X, Y = np.meshgrid(x, y)
            a_s = a0 + mag.induced_a(X, Y)
        k = 1e6
        out = {"hash": site.key, "z": z, "x0": float(x[0]), "x1": float(x[-1]), "y0": float(y[0]),
               "y1": float(y[-1]), "nx": int(x.size), "ny": int(y.size),
               "scale": _num(field_lines.scale_of(a0) * k, 9),
               # how far the "show weak field" spacing reaches down: see engine/field_lines.py
               "softness": _num(field_lines.softness_of(a0), 4),
               "a0_re": b64(a0.real * k), "a0_im": b64(a0.imag * k),
               "aS_re": b64(a_s.real * k) if a_s is not None else None,
               "aS_im": b64(a_s.imag * k) if a_s is not None else None,
               "shield_included": a_s is not None,
               "has_current": bool(any(abs(c.current_A) > 0 for c in conds))}
        site._memo["fieldlines"] = out
        return out


def efieldlines(cfg: dict) -> dict:
    """
    What the browser needs to draw the electric field at any instant, without and with
    the shield: the charge on every conductor (as volts, so the field of a wire is
    lam / r), the potential over the cross-section (its contours are the equipotentials)
    and, with a shield, the field of the charge induced on it. Volts are sent as kV.
    Same section as the magnetic field lines.
    """
    site = site_for(cfg)
    with site.lock:
        hit = site._memo.get("efieldlines")
        if hit is not None:
            return hit
        z, ele = 0.0, None
        if site.shield_on and site.physical:
            z = 0.0 if site.shield_at(0.0) else float(site.geom.z_center)
            _, ele = site.solution(z)
        conds = site.conductors_at(z)
        d = field_lines.electric_data(conds, (site.x_min, site.x_max), (0.0, site.y_max),
                                      site.bundle_eq, ele)
        k = 1e-3
        x, y = d["x"], d["y"]

        def pair(a):
            return [[_num(v.real * k, 6), _num(v.imag * k, 6)] for v in a]

        on = bool(np.any(np.abs(d["lam0"]) > 0))
        out = {"hash": site.key, "z": z, "x0": float(x[0]), "x1": float(x[-1]), "y0": float(y[0]),
               "y1": float(y[-1]), "nx": int(x.size), "ny": int(y.size),
               "conductors": [{"x": _num(c.x, 4), "y": _num(c.y_sagged, 4)} for c in conds],
               "lam0": pair(d["lam0"]),
               "lam_ref": _num(float(np.max(np.abs(d["lam0"]))) * k if on else 0.0, 6),
               "scale": _num(field_lines.scale_of(d["v0"]) * k, 6),
               "softness": _num(field_lines.softness_of(d["v0"]), 4),
               "v0_re": b64(d["v0"].real * k), "v0_im": b64(d["v0"].imag * k),
               "shield_included": ele is not None, "has_voltage": on,
               "lamS": None, "vS_re": None, "vS_im": None,
               "exS_re": None, "exS_im": None, "eyS_re": None, "eyS_im": None,
               "walls": [], "wires": []}
        if ele is not None:
            out.update({
                "lamS": pair(d["lamS"]),
                "vS_re": b64(d["vS"].real * k), "vS_im": b64(d["vS"].imag * k),
                "exS_re": b64(d["exS"].real * k), "exS_im": b64(d["exS"].imag * k),
                "eyS_re": b64(d["eyS"].real * k), "eyS_im": b64(d["eyS"].imag * k),
                "walls": [[_num(v, 4) for v in w] for w in site.geom.walls],
                "wires": [[_num(wx, 4), _num(wy, 4)] for wx, wy in site.geom.wires]})
        site._memo["efieldlines"] = out
        return out


# ---------------------------------------------------------------------------
# Shield design: model comparison, sweeps, assistant
# ---------------------------------------------------------------------------
def _receptor_index(site: Site, receptor) -> Optional[int]:
    """
    The building a study is judged on. None when a point was given instead, or
    there is no building. With nothing chosen it is the building the shield protects.
    """
    if (isinstance(receptor, dict) and "x" in receptor) or not site.buildings:
        return None
    n = len(site.buildings)
    if receptor is None:
        return min(max(site.shield_cfg.target_building, 0), n - 1)
    try:
        return min(max(int(receptor), 0), n - 1)
    except (TypeError, ValueError):
        return 0


def _receptor_point(site: Site, receptor) -> Tuple[Tuple[float, float, float], str]:
    """One probe point for the receptor: 1 m inside the building's wall facing the line."""
    if isinstance(receptor, dict) and "x" in receptor:
        return (float(receptor["x"]), float(receptor.get("y", site.meas_height)),
                float(receptor.get("z", 0.0))), "the selected point"
    idx = _receptor_index(site, receptor)
    if idx is not None:
        b = site.buildings[idx]
        return sh.building_probe_point(b), b["name"]
    ref = site.shield_reference_point()
    if ref:
        return ref, "the reference point behind the barrier"
    return (site.row_half, site.meas_height, 0.0), "the right-of-way edge"


def _room_point(site: Site, pt, name):
    """A shielded room is judged at its own centre, not at the building's facade probe."""
    if site.geom.zone is None:
        return pt, name
    x0, x1, y0, y1, z0, z1 = site.geom.zone
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0), f"the centre of the shielded room in {name}"


def _inside(s2: Site, idx: Optional[int]) -> Optional[dict]:
    """
    The field in the space a shield is judged on: the inside of building `idx`
    (area average and worst point, without and with the shield), or the shielded
    room when the shield is a room in that building. None without a building.
    """
    if idx is None or not s2.buildings:
        return None
    tgt = min(max(s2.shield_cfg.target_building, 0), len(s2.buildings) - 1)
    if s2.shield_on and s2.geom.zone is not None and tgt == idx:
        return s2.zone_stats()
    return s2.building_stats(idx)


def _where(st: Optional[dict], point_name: str) -> str:
    return f"inside {st['label']}" if st is not None else f"at {point_name}"


def _row(label, s2: Site, idx: Optional[int], pt, sub: str = "") -> dict:
    """
    One line of a comparison. The headline values (b0, bS, e0, eS and the changes)
    are the AREA AVERAGE over the inside of the building being protected, because
    a single point can sit in a quiet spot or a hot one and tell the wrong story.
    The worst point inside and the value at the probe point (1 m inside the wall
    facing the line) are given beside it. With no building the row is the probe
    point alone and basis = "point".
    """
    v = s2.point(*pt)
    st = _inside(s2, idx)
    simple = s2.se_simple
    if st is not None:
        b0, b_s, e0, e_s = st["b"]["avg0"], st["b"]["avgS"], st["e"]["avg0"], st["e"]["avgS"]
    else:
        b0, b_s, e0, e_s = v["b0"], v["bS"], v["e0"], v["eS"]
    return {"label": label, "sub": sub, "basis": "inside" if st is not None else "point",
            "where": st["label"] if st is not None else "",
            "b0": _num(b0), "bS": _num(b_s), "e0": _num(e0), "eS": _num(e_s),
            "b_red_pct": _num(sh.atten_pct(b0, b_s), 3), "e_red_pct": _num(sh.atten_pct(e0, e_s), 3),
            "b_se_db": _num(sh.se_db(b0, b_s), 3), "e_se_db": _num(sh.se_db(e0, e_s), 3),
            "b_max0": _num(st["b"]["max0"]) if st else None, "b_maxS": _num(st["b"]["maxS"]) if st else None,
            "e_max0": _num(st["e"]["max0"]) if st else None, "e_maxS": _num(st["e"]["maxS"]) if st else None,
            "b_pt0": _num(v["b0"]), "b_ptS": _num(v["bS"]), "e_pt0": _num(v["e0"]), "e_ptS": _num(v["eS"]),
            "b_pt_red_pct": _num(sh.atten_pct(v["b0"], v["bS"]), 3),
            "e_pt_red_pct": _num(sh.atten_pct(v["e0"], v["eS"]), 3),
            "sheet_se_b": _num(simple.se_b, 2), "sheet_se_e": _num(simple.se_e, 2),
            "has_geometry": bool(s2.geom.walls)}


def _b_inside(s2: Site, idx: Optional[int], pt) -> float:
    """The magnetic field a design is judged on: average inside the building, or at the point."""
    st = _inside(s2, idx)
    return float(st["b"]["avgS"]) if st is not None else float(s2.point(*pt)["bS"])


def _cfg_changes(ch: dict) -> dict:
    """Shield changes as the project file names them (the engine calls bonded seams 'continuous')."""
    out = {}
    for k, v in ch.items():
        if k == "enabled":
            continue
        out["bonded" if k == "continuous" else k] = v
    return out


def _loop_clearance(site: Site) -> float:
    """Working clearance kept between a loop conductor and any phase conductor [m]."""
    kv = max([float(c.voltage_kV) for c in site.conductors] + [float(ln.voltage_kv) for ln in site.lines]
             or [132.0])
    return 3.0 + kv / 100.0


LOOP_COMPENSATIONS = (0.0, 30.0, 50.0, 70.0, 85.0)


def loop_candidates(site: Site, idx: Optional[int] = None) -> List[dict]:
    """
    Placements for a passive loop that respect a clearance to the phase conductors,
    5 m above ground, and stay out of the buildings: side-by-side loops under the
    line (several heights, widths and offsets towards the protected building) and
    one-above-the-other loops beside the line, between it and the building.
    """
    xs = [c.x for c in site.conductors] or [0.0]
    ys = [c.y_sagged for c in site.conductors] or [20.0]
    clear = _loop_clearance(site)
    centre = (max(xs) + min(xs)) / 2.0
    wline = max(xs) - min(xs)
    idx = _receptor_index(site, idx)
    b = site.buildings[idx] if idx is not None else None
    sg = -1.0 if (b is not None and b["side"] == "left") else 1.0
    edge = (max(xs) if sg > 0 else min(xs))                       # outermost conductor on the protected side
    near = sg * b["distance"] if b is not None else sg * max(site.row_half, abs(edge) + 8.0)
    gap = abs(near - edge)

    raw = []
    for h in sorted({max(5.0, min(ys) - clear), max(5.0, min(ys) - clear - 3.0), 6.0}):
        for wf in (0.8, 1.2, 1.65, 2.4):
            for off in (0.0, 0.25, 0.5):
                raw.append((False, centre + off * (near - centre), h, max(8.0, wline * wf)))
    for x in (edge + sg * clear, edge + sg * (clear + 0.3 * max(0.0, gap - clear - 3.0)),
              (edge + near) / 2.0, near - sg * 3.0):
        for sp in (6.0, 10.0, 15.0):
            raw.append((True, x, 6.0, sp))

    out, seen = [], set()
    for vertical, x, h, sp in raw:
        pts = [(x, h), (x, h + sp)] if vertical else [(x - sp / 2.0, h), (x + sp / 2.0, h)]
        if any(math.hypot(px - c.x, py - c.y_sagged) < clear for px, py in pts for c in site.conductors):
            continue
        if any(py < 5.0 for _, py in pts):
            continue
        inside = False
        for bb in site.buildings:
            x0, x1 = sorted(sh.building_x(bb))
            inside = inside or any(x0 - 1.0 <= px <= x1 + 1.0 and py <= bb["height"] + 1.0 for px, py in pts)
        if inside:
            continue
        key = (vertical, round(x, 1), round(h, 1), round(sp, 1))
        if key in seen:
            continue
        seen.add(key)
        out.append({"loop_vertical": vertical, "distance_m": round(abs(x), 1),
                    "side": "left" if x < 0 else "right", "height_m": round(h, 1),
                    "loop_spacing_m": round(sp, 1)})
    return out


def best_passive_loop(site: Site, idx: Optional[int] = None) -> dict:
    """
    Search the candidate placements and compensation levels for the loop that
    leaves the lowest average magnetic field inside the building (or, with no
    building, at the edge of the right-of-way). A loop lowers the field in one
    place and raises it in another, so it has to be placed for the receptor.
    Returns {"best": {...}, "uncompensated": {...}, "tried": n, "worst_pct": ...};
    each entry is {"changes": shield settings, "reduction_pct": expected change}.
    """
    idx = _receptor_index(site, idx)
    memo_key = ("loop", idx)
    if memo_key in site._memo:
        return site._memo[memo_key]            # type: ignore[return-value]
    common = {"preset": "passive-loop", "enabled": True, "length_m": round(2 * site.half_span, 0),
              "z_center_m": 0.0, "material_id": "aluminium", "wire_mm2": 400.0, "continuous": True}
    edge_pt = (site.row_half, site.meas_height, 0.0)

    def score(s2: Site) -> Tuple[float, float]:
        st = _inside(s2, idx)
        if st is not None:
            return st["b"]["avgS"], st["b"]["avg0"]
        v = s2.point(*edge_pt)
        return v["bS"], v["b0"]

    results = []
    for cand in loop_candidates(site, idx):
        for k in LOOP_COMPENSATIONS:
            ch = dict(common, loop_compensation_pct=k, **cand)
            try:
                got, ref = score(site.with_shield(**ch))
            except Exception:                                    # a degenerate candidate: skip it
                continue
            if ref > 0 and math.isfinite(got):
                results.append((got / ref, k, ch))
    if not results:
        out = {"best": None, "uncompensated": None, "tried": 0, "worst_pct": None, "where": ""}
        site._memo[memo_key] = out
        return out
    results.sort(key=lambda r: r[0])

    def pack(r):
        return {"changes": r[2], "reduction_pct": _num((1.0 - r[0]) * 100.0, 3)}

    plain = [r for r in results if r[1] == 0.0]
    out = {"best": pack(results[0]), "uncompensated": pack(plain[0]) if plain else None,
           "tried": len(results), "worst_pct": _num((1.0 - results[-1][0]) * 100.0, 3),
           "where": (f"Average field inside {site.buildings[idx]['name']}" if idx is not None
                     else "Field at the edge of the right-of-way")}
    site._memo[memo_key] = out
    return out


def barrier_candidates(site: Site, idx: int) -> List[dict]:
    """
    Positions for a free-standing barrier wall protecting building `idx`: on the
    building's side of the line, as tall as the building, 10 m longer than it at
    each end and centred on it, at up to four distances between the line (keeping
    a working clearance to the conductors) and 1 m in front of the building.
    """
    b = site.buildings[idx]
    sg = sh.building_sign(b)
    near = float(b["distance"])
    xs = [sg * c.x for c in site.conductors] or [0.0]
    lo = math.ceil(max(max(xs) + _loop_clearance(site), 2.0) * 10.0 - 1e-9) / 10.0   # never inside the clearance
    hi = math.floor((near - 1.0) * 10.0 + 1e-9) / 10.0
    ds = [max(1.0, hi)] if hi <= lo + 0.5 else [lo + f * (hi - lo) for f in (0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0)]
    return [{"distance_m": round(d, 1), "height_m": round(float(b["height"]), 1),
             "side": "left" if sg < 0 else "right", "length_m": float(round(float(b["depth"]) + 20.0)),
             "z_center_m": float(b["z_offset"])} for d in ds]


def best_barrier(site: Site, idx: Optional[int] = None) -> Optional[dict]:
    """
    The barrier-wall position that leaves the lowest average magnetic field inside
    the building: {"changes": settings, "tried": n, "reduction_pct": expected}.
    None when there is no building to place it for.
    """
    idx = _receptor_index(site, idx)
    if idx is None:
        return None
    memo_key = ("barrier", idx)
    if memo_key in site._memo:
        return site._memo[memo_key]            # type: ignore[return-value]
    results = []
    for cand in barrier_candidates(site, idx):
        try:
            st = _inside(site.with_shield(enabled=True, preset="wall-between", **cand), idx)
        except Exception:
            continue
        if st and st["b"]["avg0"] > 0:
            results.append((st["b"]["avgS"] / st["b"]["avg0"], st["e"]["avgS"], cand))
    out = None
    if results:
        results.sort(key=lambda r: (round(r[0], 4), r[1]))
        out = {"changes": results[0][2], "tried": len(results),
               "reduction_pct": _num((1.0 - results[0][0]) * 100.0, 3)}
    site._memo[memo_key] = out
    return out


def suggested_wires(site: Site, preset: str, idx: Optional[int] = None) -> dict:
    """
    A first placement for the conductor-based measures, from the site itself.
    Passive loop: the best of the searched placements (see best_passive_loop).
    Screening wires: a canopy over the building.
    """
    idx = _receptor_index(site, idx)
    if preset == "passive-loop":
        found = best_passive_loop(site, idx)["best"]
        if found is not None:
            return {k: v for k, v in found["changes"].items() if k not in ("preset", "enabled")}
        return {}
    if preset == "screen-wires" and idx is not None:
        b = site.buildings[idx]
        near = b["distance"]
        width = b["width"] + 4.0
        return {"distance_m": round(max(0.0, near - 2.0), 1), "side": b["side"],
                "screen_width_m": round(width, 1), "height_m": round(b["height"] + 3.0, 1),
                "wire_count": int(min(24, max(3, round(width / 5.0) + 1))),
                "length_m": float(round(b["depth"] + 10.0)), "z_center_m": float(b["z_offset"]),
                "material_id": "galvsteel", "wire_mm2": 50.0, "grounded": True}
    return {}


BARRIER_PRESETS = ("wall-between", "double-barrier", "mesh-barrier")


def _placement_text(ch: dict) -> str:
    return (f"{ch['distance_m']:g} m from the centreline, {ch['height_m']:g} m high, "
            f"{ch['length_m']:g} m long")


def suggestion(site: Site, preset: str) -> dict:
    """The /api/shield/suggest reply: the settings and a sentence saying what to expect."""
    if preset == "passive-loop":
        found = best_passive_loop(site)
        best = found["best"]
        if best is None:
            return {"changes": {}, "note": "No loop position keeps a safe clearance from the conductors here."}
        ch = _cfg_changes({k: v for k, v in best["changes"].items() if k != "preset"})
        red = best["reduction_pct"] or 0.0
        comp = ch.get("loop_compensation_pct", 0.0)
        how = ("one conductor above the other" if ch["loop_vertical"] else "side by side") \
            + f", {ch['distance_m']:g} m from the centreline"
        note = (f"Best of {found['tried']} placements tried: {how}"
                + (f", {comp:g}% compensated" if comp else ", no capacitor")
                + f". {found['where']} {'down' if red >= 0 else 'up'} {abs(red):.0f}%.")
        if red < 3.0:
            note += " A loop does little for this layout."
        return {"changes": ch, "note": note, "reduction_pct": red, "tried": found["tried"],
                "worst_pct": found["worst_pct"]}
    if preset in BARRIER_PRESETS:
        found = best_barrier(site)
        if found is None:
            return {"changes": {}, "note": ""}
        idx = _receptor_index(site, None)
        name = site.buildings[idx]["name"] if idx is not None else "the building"
        red = found["reduction_pct"] or 0.0
        note = (f"Placed beside {name}: {_placement_text(found['changes'])}"
                + (f" (the best of {found['tried']} positions tried)" if found["tried"] > 1 else "")
                + f". Average magnetic field inside {'down' if red >= 0 else 'up'} {abs(red):.0f}% "
                  "with the current sheet.")
        return {"changes": dict(found["changes"]), "note": note, "reduction_pct": red, "tried": found["tried"]}
    ch = suggested_wires(site, preset)
    return {"changes": ch, "note": ""}


def line_measures(cfg: dict) -> List[Tuple[str, str, dict]]:
    """Mitigation at the line itself: (label, note, modified configuration with the shield off)."""
    out = []
    base = copy.deepcopy(cfg)
    base["shield"]["enabled"] = False
    for dh in (5.0, 10.0):
        c = copy.deepcopy(base)
        for ln in c["lines"]:
            ln["height_adjust_m"] = float(ln.get("height_adjust_m", 0.0) or 0.0) + dh
        out.append((f"Raise the conductors by {dh:g} m", "at the line - taller towers", c))
    presets = lines_mod.tower_presets()
    swap = copy.deepcopy(base)
    changed = now_low = False
    for ln in swap["lines"]:
        tower = lines_mod.tower_of(ln, presets)
        ids = lines_mod.circuit_ids(tower["conductors"]) if tower else [1]
        if len(ids) < 2:
            continue
        low = lines_mod.arrangement_orders(ids, "ABC-CBA", tower.get("swap_circuits"))
        if ln.get("circuits"):                     # circuits set one by one: flip their phase orders
            is_low = all(spec["phase_order"] == low[i] for spec, i in zip(ln["circuits"], ids))
            for spec, i in zip(ln["circuits"], ids):
                spec["phase_order"] = "ABC" if is_low else low[i]
        else:
            is_low = ln.get("arrangement") == "ABC-CBA"
            ln["arrangement"] = "ABC-ABC" if is_low else "ABC-CBA"
        changed = True
        now_low = now_low or not is_low
    if changed:
        out.append(("Low-reactance phasing (ABC-CBA)" if now_low else "Same phasing on every circuit (ABC-ABC)",
                    "at the line - phase arrangement of the circuits", swap))
    return out


THICKNESSES_MM = (0.5, 1, 2, 3, 6, 12, 25, 50, 100)
COVERAGES = (50, 70, 80, 90, 95, 99, 100)


def shield_models(cfg: dict, receptor=None) -> dict:
    """The same shield under the three models, judged inside the building it protects."""
    site = site_for(cfg)
    with site.lock:
        key = ("models", json.dumps(receptor, sort_keys=True, default=str))
        if key in site._memo:
            return site._memo[key]             # type: ignore[return-value]
        idx = _receptor_index(site, receptor)
        pt, name = _receptor_point(site, receptor)
        base = site.with_shield(enabled=True)
        if idx is None and base.geom.walls and not base.geom.covers_z(pt[2]):
            pt = (pt[0], pt[1], base.geom.z_center)
        pt, pname = _room_point(base, pt, name)
        rows = []
        for m in ("physical", "analytical", "empirical"):
            s2 = base.with_shield(model=m)
            r = _row(sh.MODELS[m], s2, idx, pt)
            r["model"] = m
            r["available"] = not (m == "empirical" and s2.shield_cfg.material.empirical_key is None)
            rows.append(r)
        out = {"hash": site.key, "receptor": _where(_inside(base, idx), pname), "basis": rows[0]["basis"],
               "probe": pname, "point": [_num(v, 3) for v in pt], "rows": rows}
        site._memo[key] = out
        return out


def _standard_changes(site: Site, preset: str, idx: Optional[int]) -> dict:
    """How an arrangement around the building is shown when it is not the one in use: fixed to the building, full height."""
    ch: Dict[str, object] = {"preset": preset}
    if idx is None:
        return ch
    b = site.buildings[idx]
    ch["target_building"] = idx
    if preset in ("enclosure", "envelope", "walls", "roof"):
        ch.update(gap_m=0.0, roof_gap_m=0.0)
    elif preset == "panel":
        ch.update(gap_m=0.0, height_m=float(b["height"]))
    elif preset == "surround-wall":
        ch.update(standoff_m=2.0, height_m=float(math.ceil(b["height"])))
    elif preset == "floor":
        ch.update(floor_level_m=sh.FLOOR_M)
    return ch


def _geometry_rows(site: Site, cfg: dict, base: Site, idx: Optional[int], pt) -> List[dict]:
    """Every arrangement, each solved for this site, plus the measures at the line itself."""
    rows: List[dict] = []
    cur = site.shield_cfg
    n_b = len(site.buildings)
    cur_target = min(max(cur.target_building, 0), n_b - 1) if n_b else None

    def add(preset, label, short, changes, sub, in_use=False, point=None):
        s2 = base.with_shield(**changes)
        p2 = point or pt
        if s2.geom.zone is not None:
            zx0, zx1, zy0, zy1, zz0, zz1 = s2.geom.zone
            p2 = ((zx0 + zx1) / 2.0, (zy0 + zy1) / 2.0, (zz0 + zz1) / 2.0)
        elif idx is None and s2.geom.walls and not s2.geom.covers_z(p2[2]):
            p2 = (p2[0], p2[1], s2.geom.z_center)
        r = _row(label, s2, idx, p2, sub)
        r.update({"id": preset, "short": short, "changes": _cfg_changes(changes), "in_use": bool(in_use)})
        rows.append(r)

    wall = best_barrier(site, idx) if idx is not None else None
    for k, p in sh.PRESETS.items():
        same_target = idx is None or not p["attached"] or cur_target == idx
        in_use = bool(cur.enabled and cur.preset == k and same_target)
        family = ("around the building" if p["attached"] else "your own layout" if p["custom"]
                  else "between line and building") + (" - conductors" if p["wires"] else "")
        if p["custom"]:
            if cur.custom_plates:
                add(k, p["label"], p["short"], {"preset": k}, f"{family} - as you placed it", in_use)
            continue
        if in_use:
            ch = {"preset": k}
            if p["attached"] and idx is not None:
                ch["target_building"] = idx
            add(k, p["label"], p["short"], ch,
                ("inside the building - the room itself" if k == "room" else family) + " - as you set it", True)
            if k != "passive-loop":
                continue
        if k == "passive-loop":
            loops = best_passive_loop(site, idx)
            plain, best = loops["uncompensated"], loops["best"]
            variants = []
            if plain is not None:
                variants.append(("Passive loop, no capacitor", "Loop", plain["changes"]))
            if best is not None and best["changes"].get("loop_compensation_pct", 0.0) > 0:
                kk = best["changes"]["loop_compensation_pct"]
                variants.append((f"Passive loop, {kk:g}% series-compensated", f"Loop, {kk:g}% comp.",
                                 best["changes"]))
            for label, short, ch in variants:
                add(k, label, short, {a: b for a, b in ch.items() if a != "enabled"},
                    f"{family} - best of {loops['tried']} placements tried")
        elif k == "screen-wires":
            ch = {"preset": k, **suggested_wires(site, k, idx)}
            add(k, p["label"], p["short"], ch, f"{family} - a canopy 3 m above the roof")
        elif p["attached"]:
            ch = _standard_changes(site, k, idx)
            note = {"room": "inside the building - the room itself, as sized in the inputs",
                    "surround-wall": f"{family} - 2 m off the walls, as tall as the building",
                    "panel": f"{family} - the whole facade", "floor": f"{family} - the ground slab"}.get(
                        k, f"{family} - fixed to it")
            add(k, p["label"], p["short"], ch, note)
        else:                                                   # free-standing sheet barriers
            if wall is None:
                add(k, p["label"], p["short"], {"preset": k}, family)
            else:
                ch = {"preset": k, **wall["changes"]}
                add(k, p["label"], p["short"], ch,
                    f"{family} - {_placement_text(wall['changes'])}"
                    + (f"; best of {wall['tried']} positions" if wall["tried"] > 1 else ""))

    # measures at the line itself: no shield, the line changed
    st0 = _inside(site, idx)
    v0 = site.point(*pt)
    for label, sub, mod in line_measures(cfg):
        s2 = site_for(normalise_config(mod))
        with s2.lock:
            st, v = _inside(s2, idx), s2.point(*pt)
        if st0 is not None and st is not None:
            b0, b1, e0, e1 = st0["b"]["avg0"], st["b"]["avg0"], st0["e"]["avg0"], st["e"]["avg0"]
        else:
            b0, b1, e0, e1 = v0["b0"], v["b0"], v0["e0"], v["e0"]
        rows.append({"label": label, "sub": sub, "id": "line", "basis": "inside" if st0 is not None else "point",
                     "where": st0["label"] if st0 is not None else "",
                     "b0": _num(b0), "bS": _num(b1), "e0": _num(e0), "eS": _num(e1),
                     "b_red_pct": _num(sh.atten_pct(b0, b1), 3), "e_red_pct": _num(sh.atten_pct(e0, e1), 3),
                     "b_se_db": _num(sh.se_db(b0, b1), 3), "e_se_db": _num(sh.se_db(e0, e1), 3),
                     "b_max0": _num(st0["b"]["max0"]) if st0 else None, "b_maxS": _num(st["b"]["max0"]) if st else None,
                     "e_max0": _num(st0["e"]["max0"]) if st0 else None, "e_maxS": _num(st["e"]["max0"]) if st else None,
                     "b_pt0": _num(v0["b0"]), "b_ptS": _num(v["b0"]), "e_pt0": _num(v0["e0"]), "e_ptS": _num(v["e0"]),
                     "b_pt_red_pct": _num(sh.atten_pct(v0["b0"], v["b0"]), 3),
                     "e_pt_red_pct": _num(sh.atten_pct(v0["e0"], v["e0"]), 3),
                     "sheet_se_b": None, "sheet_se_e": None, "has_geometry": True, "in_use": False})
    return rows


SWEEP_NOTES = {
    "geometry": "The arrangement you are using is shown as you set it. The others are at a standard "
                "placement so they can be compared: sheets fixed to the building over its full height; "
                "a barrier wall as tall as the building, at the best of the positions tried between the "
                "line and the building; a loop at the best placement found. \"Use\" applies exactly what "
                "the row was solved with.",
}


def shield_sweep(cfg: dict, kind: str, receptor=None) -> dict:
    """One thing changed at a time, each option solved again and judged inside the building."""
    site = site_for(cfg)
    with site.lock:
        key = ("sweep", kind, json.dumps(receptor, sort_keys=True, default=str))
        if key in site._memo:
            return site._memo[key]             # type: ignore[return-value]
        out = _shield_sweep(site, cfg, kind, receptor)
        site._memo[key] = out
        return out


def _shield_sweep(site: Site, cfg: dict, kind: str, receptor) -> dict:
    idx = _receptor_index(site, receptor)
    pt, name = _receptor_point(site, receptor)
    base = site.with_shield(enabled=True)
    if idx is None and base.geom.walls and not base.geom.covers_z(pt[2]):
        pt = (pt[0], pt[1], base.geom.z_center)
    pname = name
    if kind not in ("geometry", "building"):
        pt, pname = _room_point(base, pt, name)
    rows: List[dict] = []
    xlabel = ""
    row = lambda label, s2, sub="": _row(label, s2, idx, pt, sub)        # noqa: E731
    if kind == "material":
        for m in sh.MATERIAL_ORDER:
            mat = sh.MATERIALS[m]
            rows.append(row(mat.label, base.with_shield(material_id=m), f"{mat.category} - {mat.quality}"))
    elif kind == "thickness":
        xlabel = "Thickness"
        for t in THICKNESSES_MM:
            rows.append(row(f"{t:g} mm", base.with_shield(thickness_m=t / 1000.0)))
    elif kind == "geometry":
        rows = _geometry_rows(site, cfg, base, idx, pt)
    elif kind == "coverage":
        xlabel = "Coverage"
        for c in COVERAGES:
            rows.append(row(f"{c:g} %", base.with_shield(coverage_pct=float(c))))
    elif kind == "height":
        xlabel = "Barrier height"
        for h in (2, 4, 6, 8, 10, 12, 15, 20, 25, 30):
            rows.append(row(f"{h:g} m", base.with_shield(height_m=float(h))))
    elif kind == "distance":
        preset = base.shield_cfg.preset
        if preset in ("enclosure", "envelope", "walls", "panel"):
            xlabel = "Gap between the sheet and the building"
            for g in (0, 0.5, 1, 2, 3, 5, 8):
                rows.append(row(f"{g:g} m", base.with_shield(gap_m=float(g))))
        elif preset == "surround-wall":
            xlabel = "Gap between the wall and the building"
            for g in (0.5, 1, 2, 3, 5, 8, 12):
                rows.append(row(f"{g:g} m", base.with_shield(standoff_m=float(g))))
        elif preset == "roof":
            xlabel = "Height of the sheet above the roof"
            for g in (0, 0.5, 1, 2, 3, 5):
                rows.append(row(f"{g:g} m", base.with_shield(roof_gap_m=float(g))))
        elif preset in ("wall-between", "double-barrier", "mesh-barrier", "passive-loop", "screen-wires"):
            xlabel = "Distance from centreline"
            lim = max(4.0, abs(pt[0]) - 1.0)
            for d in (5, 8, 10, 12, 15, 18, 20, 25, 30, 40, 50):
                if d < lim:
                    rows.append(row(f"{d:g} m", base.with_shield(distance_m=float(d))))
    elif kind == "layers":
        xlabel = "Layers"
        for n in (1, 2, 3):
            rows.append(row(f"{n} layer{'s' if n > 1 else ''}", base.with_shield(layers=n)))
    elif kind == "bonding":
        for lab, ch in (("Earthed, bonded seams", dict(grounded=True, continuous=True)),
                        ("Earthed, unbonded seams", dict(grounded=True, continuous=False)),
                        ("Unearthed, bonded seams", dict(grounded=False, continuous=True)),
                        ("Unearthed, unbonded seams", dict(grounded=False, continuous=False))):
            rows.append(row(lab, base.with_shield(**ch)))
    elif kind == "building":
        if idx is not None:
            for tname, bt in libraries.BUILDING_TYPES.items():
                c2 = copy.deepcopy(cfg)
                b = c2["buildings"][idx]
                b.update({"type": tname, "width": bt["width"], "depth": bt["depth"],
                          "height": bt["height"], "roof": bt["roof"]})
                c2["shield"]["enabled"] = cfg["shield"].get("enabled", False)
                s2 = Site(normalise_config(c2))
                p2 = sh.building_probe_point(s2.buildings[idx])
                rows.append(_row(tname, s2, idx, p2, bt["occupancy"]))
    else:
        raise ValueError(f"Unknown sweep '{kind}'.")
    st0 = _inside(site, idx)
    v0 = site.point(*pt)
    cur = site.shield_cfg
    foreign = bool(idx is not None and sh.PRESETS[cur.preset]["attached"] and kind not in ("geometry", "building")
                   and min(max(cur.target_building, 0), len(site.buildings) - 1) != idx)
    return {"hash": site.key, "kind": kind, "receptor": _where(st0, pname),
            "basis": "inside" if st0 is not None else "point", "probe": pname,
            "point": [_num(v, 3) for v in pt],
            "b0": _num(st0["b"]["avg0"] if st0 is not None else v0["b0"]),
            "e0": _num(st0["e"]["avg0"] if st0 is not None else v0["e0"]),
            "rows": rows, "xlabel": xlabel, "model": base.shield_cfg.model,
            "note": SWEEP_NOTES.get(kind, ""),
            # the shield is round another building than the one these numbers are for
            "other_building": (site.buildings[min(max(cur.target_building, 0), len(site.buildings) - 1)]["name"]
                               if foreign else None)}


def shield_assistant(cfg: dict, target_b: Optional[float] = None, receptor=None) -> dict:
    """Design helpers: line-of-sight height, and what it takes to bring the average B inside down to a target."""
    site = site_for(cfg)
    with site.lock:
        idx = _receptor_index(site, receptor)
        pt, name = _receptor_point(site, receptor)
        base = site.with_shield(enabled=True)
        if idx is None and base.geom.walls and not base.geom.covers_z(pt[2]):
            pt = (pt[0], pt[1], base.geom.z_center)
        pt, pname = _room_point(base, pt, name)
        scfg = base.shield_cfg
        st0 = _inside(base, idx)
        b0 = float(st0["b"]["avg0"]) if st0 is not None else float(site.point(*pt)["b0"])
        target = float(target_b) if target_b else round(max(0.01, 0.5 * b0), 3)
        attached = sh.PRESETS[scfg.preset]["attached"] or scfg.is_custom or scfg.is_wire
        out = {"hash": site.key, "receptor": _where(st0, pname), "basis": "inside" if st0 is not None else "point",
               "probe": pname, "point": [_num(v, 3) for v in pt], "b0": _num(b0),
               "target": target, "attached": attached, "current_height": scfg.height_m,
               "current": _row("Current design", base, idx, pt)}
        need = None
        if not attached:
            side = 1.0 if pt[0] >= site.centre_x else -1.0
            wall_x = side * scfg.distance_m
            need = sh.required_barrier_height(site.sources_at(pt[2]), wall_x, (pt[0], pt[1]))
        out["los_height"] = _num(need, 2)
        if b0 <= target:
            out["status"] = "already"
            return out
        # thinnest sheet
        hit_t = None
        for t in THICKNESSES_MM:
            if _b_inside(base.with_shield(thickness_m=t / 1000.0), idx, pt) <= target:
                hit_t = t
                break
        out["thickness_mm"] = hit_t
        # lowest height at the current thickness (free-standing presets only)
        hit_h = None
        if not attached:
            for h in (4, 6, 8, 10, 12, 15, 18, 22, 26, 30, 36, 42, 50):
                if _b_inside(base.with_shield(height_m=float(h)), idx, pt) <= target:
                    hit_h = h
                    break
        out["height_m"] = hit_h
        # best material at the current geometry and thickness
        best = None
        for m in sh.MATERIAL_ORDER:
            b_s = _b_inside(base.with_shield(material_id=m), idx, pt)
            if best is None or b_s < best[1]:
                best = (m, b_s)
        out["best_material"] = {"id": best[0], "label": sh.MATERIALS[best[0]].label,
                                "bS": _num(best[1])} if best else None
        out["status"] = "reachable" if (hit_t or hit_h) else "not_reachable"
        return out


# ---------------------------------------------------------------------------
# Scenario comparison
# ---------------------------------------------------------------------------
def compare_scenarios(items: List[dict]) -> dict:
    """items: [{name, config}]. Each is solved with its OWN settings."""
    curves, rows = [], []
    for it in items[:8]:
        cfg = normalise_config(it.get("config"))
        try:
            site = site_for(cfg)
        except lines_mod.LineError as exc:
            rows.append({"name": it.get("name", "?"), "error": str(exc)})
            continue
        with site.lock:
            sm = site.summary()
            prof = site.profile()
            se = site.shield_se() if site.shield_on else None
            head = shield_headline(site)
            curves.append({"name": it.get("name", "?"), "x": arr(prof["x"], 3), "b": arr(prof["b0"]),
                           "e": arr(prof["e0"]), "bS": arr(prof["bS"]) if site.shield_on else None})
            rows.append({
                "name": it.get("name", "?"), "lines": len(site.lines),
                "peak_b": _num(sm["peak_b"]), "peak_e": _num(sm["peak_e"]),
                "row_b": _num(sm["row_b"]), "overall": sm["overall"],
                "ground": earth.MODEL_INFO[site.ground_model]["short"], "freq": site.freq,
                "shield": (f"{site.geom.description}" if site.shield_on else "off"),
                "shield_model": site.shield_cfg.model if site.shield_on else None,
                "se_b": _num(se.se_b, 2) if se else None, "se_e": _num(se.se_e, 2) if se else None,
                # what the shield does where it matters: the average inside the protected space
                "shield_effect": head,
                "peak_b_shield": _num(sm["peak_b_shield"]) if site.shield_on else None,
                "standards": [r.standard.name for r in sm["results"]],
                "row_half": site.row_half,
            })
    return {"curves": curves, "rows": rows}


# ---------------------------------------------------------------------------
# Library (static reference data for the front end)
# ---------------------------------------------------------------------------
def library() -> dict:
    presets = lines_mod.tower_presets()
    stds = standards.get_standards()
    return {
        "schema": SCHEMA,
        "default_config": default_config(),
        "default_line": lines_mod.default_line(),
        "default_building": default_building(1),
        "tower_presets": [{
            "name": k, "description": p["description"], "radius_m": p.get("conductor_radius_m"),
            "row_width_m": p.get("row_width_m"),
            "is_double": len({c.circuit for c in p["conductors"]}) > 1,
            # each circuit as the tower defines it, and its phase order in the low-reactance arrangement
            "circuits": [dict(k, low_order=lines_mod.arrangement_orders(
                lines_mod.circuit_ids(p["conductors"]), "ABC-CBA", p.get("swap_circuits"))[k["id"]])
                for k in lines_mod.preset_circuits(p)],
            "voltage_kv": p["conductors"][0].voltage_kV, "current_a": p["conductors"][0].current_A,
            "bundle": len(p["conductors"][0].bundle_offsets) or 1,
            "conductors": [{"x": c.x, "y": c.y_base, "phase": c.phase, "circuit": c.circuit}
                           for c in p["conductors"]],
        } for k, p in presets.items()],
        "custom_layouts": lines_mod.CUSTOM_LAYOUTS,
        "default_circuit": lines_mod.default_circuit(),
        "reference_span_m": lines_mod.REFERENCE_SPAN_M,
        "default_custom": lines_mod.DEFAULT_CUSTOM,
        "voltage_classes": [v._asdict() for v in libraries.VOLTAGE_CLASSES],
        "current_presets": libraries.CURRENT_PRESETS,
        "loading_presets": libraries.LOADING_PRESETS,
        "soil_types": [s._asdict() for s in libraries.SOIL_TYPES],
        "ground_models": [{"id": k, **earth.MODEL_INFO[k]} for k in
                          (earth.PERFECT_CONDUCTOR, earth.FREE_SPACE, earth.COMPLEX_IMAGE)],
        "standards": [{
            "id": s.id, "name": s.name, "jurisdiction": s.jurisdiction, "year": s.year,
            "kind": s.kind, "population": s.population, "b50": s.b_limit(50), "e50": s.e_limit(50),
            "b60": s.b_limit(60), "e60": s.e_limit(60), "source": s.source, "url": s.url,
            "notes": s.notes, "needs_verification": s.needs_verification} for s in stds.values()],
        "default_standards": standards.DEFAULT_STANDARD_IDS,
        "building_types": [{"name": k, **v} for k, v in libraries.BUILDING_TYPES.items()],
        "building_shapes": libraries.BUILDING_SHAPES,
        "roof_types": libraries.ROOF_TYPES,
        "building_materials": [{
            "key": m.key, "label": m.label, "e_pct": m.e_reduction_pct, "e_range": m.e_reduction_range,
            "b_pct": m.b_reduction_pct, "b_range": m.b_reduction_range, "mechanism": m.mechanism,
            "source_ids": list(m.source_ids)}
            for m in (shielding.SHIELDING_MATERIALS[k] for k in
                      ("none", "concrete", "steel", "mesh", "vegetation"))],
        "shield_materials": [{
            "id": m.id, "label": m.label, "category": m.category, "sigma": m.sigma,
            "resistivity": (1.0 / m.sigma if m.sigma > 0 else None), "mu_r": m.mu_r,
            "eps_r": m.eps_r, "quality": m.quality, "applications": m.applications,
            "mechanisms": m.mechanisms, "limitations": m.limitations,
            "empirical_key": m.empirical_key, "ref_ids": list(m.ref_ids),
            "typical_thickness_mm": m.typical_thickness_mm,
            "skin_depth_50_mm": sh.skin_depth(m, 50.0) * 1000.0,
            "skin_depth_60_mm": sh.skin_depth(m, 60.0) * 1000.0}
            for m in (sh.MATERIALS[k] for k in sh.MATERIAL_ORDER)],
        "shield_presets": [{"id": k, **v} for k, v in sh.PRESETS.items()],
        "shield_sides": sh.SIDES,
        "shield_models": sh.MODELS,
        "references": references.LIBRARY,
        "reference_topics": references.TOPICS,
    }


# ---------------------------------------------------------------------------
# Starter templates
# ---------------------------------------------------------------------------
def _building(name, btype, distance, side="right", z=0.0, **over) -> dict:
    bt = libraries.BUILDING_TYPES[btype]
    b = {"name": name, "type": btype, "shape": "box", "roof": bt["roof"], "width": float(bt["width"]),
         "depth": float(bt["depth"]), "height": float(bt["height"]), "distance": float(distance),
         "side": side, "z_offset": float(z), "material": "none", "b_pct": None, "e_pct": None}
    b.update(over)
    return b


def templates(use_kept: bool = True) -> List[dict]:
    """Ready-made starting points shown on the Projects page."""
    presets = list(lines_mod.tower_presets())
    p132 = next((p for p in presets if p.startswith("132")), presets[0])
    p275 = next((p for p in presets if p.startswith("275")), presets[0])
    p500 = next((p for p in presets if p.startswith("500")), presets[-1])
    out = []

    c = default_config()
    out.append({"id": "blank", "name": "Blank corridor", "tag": "Start here",
                "description": "The default line and one building. Change anything.", "config": c})

    c = default_config()
    c["lines"] = [dict(lines_mod.default_line(), name="275 kV line", preset=p275, load_pct=100.0)]
    c["buildings"] = [_building("Server hall", "Data centre", 20, "right")]
    c["shield"].update({"enabled": True, "preset": "enclosure", "material_id": "mildsteel",
                        "thickness_mm": 6.0, "target_building": 0})
    out.append({"id": "enclosure", "name": "Shielded server hall", "tag": "Shielding",
                "description": "A data centre 20 m from a 275 kV line, with welded steel shielding "
                               "around the building: both side walls and the roof.",
                "config": c})

    c = default_config()
    c["lines"] = [dict(lines_mod.default_line(), name="275 kV line", preset=p275, load_pct=85.0)]
    c["buildings"] = [_building("Primary school", "School", 28, "right")]
    c["shield"].update({"enabled": True, "preset": "envelope", "material_id": "aluminium",
                        "thickness_mm": 3.0, "target_building": 0})
    c["standards"] = ["MY_ICNIRP_1998", "ICNIRP_2010", "IT_QUALITY"]
    out.append({"id": "school", "name": "School with a shielded envelope", "tag": "Shielding",
                "description": "A school 28 m from a 275 kV line, wrapped in bonded aluminium sheet "
                               "(walls, roof and floor) and checked against a 3 µT planning value.",
                "config": c})

    c = default_config()
    c["lines"] = [dict(lines_mod.default_line(), name="275 kV line", preset=p275, load_pct=90.0)]
    c["buildings"] = [_building("Substation control building", "Office block", 24, "right", width=30.0,
                                depth=16.0, height=9.0)]
    c["shield"].update({"enabled": True, "preset": "room", "material_id": "aluminium", "thickness_mm": 3.0,
                        "layers": 2, "layer2_material_id": "mildsteel", "layer_spacing_m": 0.1,
                        "room_width_m": 8.0, "room_depth_m": 6.0, "room_height_m": 3.2,
                        "room_offset_m": 3.0, "target_building": 0})
    out.append({"id": "room", "name": "Shielded equipment room", "tag": "Shielding",
                "description": "One room inside a control building lined on all six sides with "
                               "aluminium and a steel layer: the usual way to protect sensitive equipment.",
                "config": c})

    c = default_config()
    c["lines"] = [dict(lines_mod.default_line(), name="132 kV double circuit", preset=p132,
                       arrangement="ABC-CBA", load_pct=70.0)]
    c["corridor"].update({"row_half_width": 12.0, "span_m": 250.0})
    c["buildings"] = [_building("House 1", "Residential", 16, "right"),
                      _building("House 2", "Residential", 22, "left", z=30.0)]
    c["shield"].update({"enabled": True, "preset": "surround-wall", "material_id": "aluminium",
                        "thickness_mm": 2.0, "height_m": 9.0, "standoff_m": 2.0, "target_building": 0})
    c["standards"] = ["MY_ICNIRP_1998", "ICNIRP_2010", "CH_ONIR"]
    out.append({"id": "housing", "name": "Homes beside a 132 kV line", "tag": "Residential",
                "description": "Two houses close to the right-of-way of a double-circuit line, with a "
                               "conductive wall around the nearer one. Precautionary values included.",
                "config": c})

    c = default_config()
    c["lines"] = [dict(lines_mod.default_line(index=0, count=2), name="500 kV main", preset=p500,
                       x_offset=-20.0, load_pct=80.0),
                  dict(lines_mod.default_line(index=1, count=2), name="275 kV parallel", preset=p275,
                       x_offset=22.0, load_pct=60.0)]
    c["corridor"].update({"row_half_width": 40.0, "span_m": 400.0, "ground_model": earth.COMPLEX_IMAGE,
                          "earth_rho": 200.0, "soil_type": "sandyloam"})
    c["buildings"] = [_building("Data centre", "Data centre", 55, "right"),
                      _building("Hospital", "Hospital", 70, "left", z=-40.0)]
    c["standards"] = ["MY_ICNIRP_1998", "ICNIRP_2010", "IEEE_C95_6_2002"]
    out.append({"id": "corridor", "name": "Shared 500 + 275 kV corridor", "tag": "Multi-line",
                "description": "Two lines sharing a corridor over resistive soil with a data "
                               "centre and a hospital either side. Uses the complex-image earth.",
                "config": c})

    c = default_config()
    quad = lines_mod.tower_presets()[lines_mod.QUAD_PRESET]
    kinds = lines_mod.preset_circuits(quad)
    orders = lines_mod.arrangement_orders([k["id"] for k in kinds], "ABC-CBA", quad.get("swap_circuits"))
    c["lines"] = [dict(lines_mod.default_line(), name="275/132 kV tower", preset=lines_mod.QUAD_PRESET,
                       circuits=[{"on": k["id"] != 4, "voltage_kv": k["voltage_kv"], "current_a": k["current_a"],
                                  "load_pct": 80.0 if k["voltage_kv"] > 200 else 60.0,
                                  "phase_order": orders[k["id"]]} for k in kinds])]
    c["corridor"].update({"row_half_width": 20.0, "span_m": 350.0})
    c["buildings"] = [_building("Warehouse", "Warehouse", 30, "right")]
    out.append({"id": "quad", "name": "Four circuits on one tower", "tag": "Multi-circuit",
                "description": "A 275 kV double circuit above a 132 kV double circuit, each circuit with "
                               "its own voltage, current and loading, and one 132 kV circuit out of service.",
                "config": c})

    c = default_config()
    c["lines"] = [dict(lines_mod.default_line(), name="275 kV line", preset=p275, load_pct=85.0)]
    c["buildings"] = [_building("Office block", "Office block", 30, "right")]
    c["shield"].update({"enabled": True, "preset": "wall-between", "material_id": "aluminium",
                        "thickness_mm": 3.0, "distance_m": 20.0, "height_m": 12.0, "length_m": 80.0})
    out.append({"id": "barrier", "name": "Barrier wall instead of cladding", "tag": "Alternative",
                "description": "The other approach: a free-standing earthed wall between the line and "
                               "an office block. Compare it with shielding around the building.",
                "config": c})

    for t in out:
        t["config"] = normalise_config(t["config"])
    # The cards show a few numbers of each example. Working them out means solving all eight,
    # which a small server needs many seconds for, every time it wakes. So the numbers are kept
    # in a file beside this one (tools/make_examples.py writes it), and used when they belong to
    # exactly these examples in exactly this version; otherwise they are worked out here.
    key = templates_key(out)
    kept = _kept_summaries(key) if use_kept else None
    for t in out:
        if kept is not None and t["id"] in kept:
            t["summary"] = kept[t["id"]]
            continue
        try:
            s = solve(t["config"])
            t["summary"] = {"peak_b": s["peak_b"], "peak_e": s["peak_e"], "overall": s["overall"],
                            "lines": len(s["lines"]), "kv": sorted({ln["kv"] for ln in s["lines"]}),
                            "shield": s["shield"]["on"], "buildings": len(s["receptors"])}
        except Exception:
            t["summary"] = {}
    return out


TEMPLATES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates_cache.json")


def templates_key(items: List[dict]) -> str:
    """What the kept numbers belong to: this version and these exact inputs."""
    blob = json.dumps([config.VERSION] + [[t["id"], t["config"]] for t in items], sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _kept_summaries(key: str) -> Optional[dict]:
    try:
        with open(TEMPLATES_FILE, encoding="utf-8") as fh:
            kept = json.load(fh)
        return kept["summaries"] if kept.get("key") == key else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write_templates_file(path: Optional[str] = None) -> str:
    """Work the examples out afresh and keep their numbers (run by tools/make_examples.py)."""
    items = templates(use_kept=False)
    with open(path or TEMPLATES_FILE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"key": templates_key(items), "version": config.VERSION,
                   "summaries": {t["id"]: t["summary"] for t in items}}, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return path or TEMPLATES_FILE


# ---------------------------------------------------------------------------
# "What changed": this project under the old assumptions and the new ones
# ---------------------------------------------------------------------------
def what_changed(cfg: dict) -> dict:
    """
    Numbers for the Settings page: for the open project, what each modelling
    correction in this version does to the result.
    """
    site = site_for(cfg)
    items = []
    with site.lock:
        sm = site.summary()
        pb, pe = float(sm["peak_b"]), float(sm["peak_e"])

        # 1. Loading scales the current (earlier versions: rated current at any loading)
        c_old = copy.deepcopy(cfg)
        any_partial = False
        for ln, built in zip(c_old["lines"], site.lines):
            def full(k):                       # the rated current that gives full current at this loading
                return k.rated_current_a * 100.0 / k.load_pct
            partial = [k.on and k.load_pct > 0 and abs(k.load_pct - 100.0) > 1e-9 for k in built.circuits]
            if not any(partial):
                continue
            any_partial = True
            if len(built.circuits) > 1:        # written circuit by circuit, so mixed towers stay as they are
                ln["circuits"] = [{"on": k.on, "voltage_kv": k.voltage_kv, "load_pct": k.load_pct,
                                   "current_a": full(k) if p else k.rated_current_a,
                                   "phase_order": k.phase_order} for k, p in zip(built.circuits, partial)]
            else:
                ln["current_a"] = full(built.circuits[0])
        old_b = float(site_for(normalise_config(c_old)).summary()["peak_b"]) if any_partial else pb
        items.append({
            "id": "loading", "title": "Loading now scales the current",
            "before_label": "Earlier versions (rated current at any loading)", "after_label": "This version",
            "before": _num(old_b), "after": _num(pb), "unit": "µT", "quantity": "Peak B",
            "applies": any_partial,
            "text": "The Loading (%) control used to change only the thermal sag; conductors always "
                    "carried full rated current. The operating current is now rated x loading / 100. "
                    "At 100 % loading the magnetic field is exactly what earlier versions gave."})

        # 2. Conductor radius in the electric-field solver.
        # Earlier versions meant to use each preset's conductor radius, but the phase-swap step
        # rebuilt the conductors without it, so every line was solved with the 15 mm fallback
        # and bundles were treated as one thin wire.
        x = np.linspace(site.x_min, site.x_max, 401)
        old_conds = []
        for c in site.conductors:
            k = copy.copy(c)
            k.radius_m = 0.015
            old_conds.append(k)
        old_e = float(np.max(physics.compute_e_field_at_points(
            old_conds, x, np.full_like(x, site.meas_height), bundle_equivalent=False)))
        has_bundle = any(len(c.bundle_offsets or []) > 1 for ln in site.lines for c in ln.conductors)
        items.append({
            "id": "bundle", "title": "Conductor and bundle radius in the electric field",
            "before_label": "Earlier versions (15 mm wire, bundle ignored)",
            "after_label": "This version" + (" (bundle-equivalent radius)" if site.bundle_eq and has_bundle
                                             else " (tower's conductor radius)"),
            "before": _num(old_e), "after": _num(pe), "unit": "kV/m", "quantity": "Peak E",
            "applies": True,
            "text": "The charge a conductor carries at a given voltage depends on its radius. Earlier "
                    "versions lost each tower's conductor radius on the way to the solver and used "
                    "15 mm for every line, and treated a bundle as a single thin wire. The tower's own "
                    "radius is now used, and a bundle is represented by its geometric-mean equivalent "
                    "radius (standard practice), which raises the computed E field of bundled lines. "
                    "The magnetic field is unaffected."})

        # 3. Earth model
        c3 = copy.deepcopy(cfg); c3["corridor"]["ground_model"] = earth.PERFECT_CONDUCTOR
        pc = float(site_for(normalise_config(c3)).summary()["peak_b"])
        c4 = copy.deepcopy(cfg); c4["corridor"]["ground_model"] = earth.FREE_SPACE
        fs = float(site_for(normalise_config(c4)).summary()["peak_b"])
        items.append({
            "id": "earth", "title": "Earth-return model for the magnetic field",
            "before_label": "Perfectly conducting earth (image at -h)", "after_label": "No earth currents (free space)",
            "before": _num(pc), "after": _num(fs), "unit": "µT", "quantity": "Peak B",
            "current": _num(pb), "current_label": earth.MODEL_INFO[site.ground_model]["short"],
            "applies": True,
            "text": "At 50/60 Hz real soil lets the magnetic field penetrate hundreds of metres, so "
                    "the two classical assumptions bracket the answer. The complex-image (Deri) "
                    "model sits between them and depends on soil resistivity."})

        # 4. Shield model
        if cfg["shield"].get("enabled") and site.geom.walls:
            sm_models = shield_models(cfg)
            sm_rows = sm_models["rows"]
            phys = next(r for r in sm_rows if r["model"] == "physical")
            where = (f"Change in the average B {sm_models['receptor']}" if sm_models["basis"] == "inside"
                     else "Change in B at the reference point")
            sheet_pct = 100.0 * (1.0 - 10.0 ** (-float(phys["sheet_se_b"] or 0.0) / 20.0))
            items.append({
                "id": "shield", "title": "Finite-barrier shield solver",
                "before_label": "Infinite-sheet formula (sheet alone)",
                "after_label": "Boundary-element solution on the real geometry",
                "before": _num(-sheet_pct, 2), "after": _num(-float(phys["b_red_pct"] or 0.0), 2),
                "unit": "%", "quantity": where, "applies": True,
                "text": "A plane-wave sheet formula treats the barrier as an infinite plane. A real "
                        "wall is finite: the field diffracts over the top and around the ends, and "
                        "the induced currents must close within the sheet. The physical model solves "
                        "for those currents on the actual geometry, so its answer depends on height, "
                        "length, position and bonding as well as on the material."})
        else:
            items.append({
                "id": "shield", "title": "Finite-barrier shield solver",
                "before_label": "Infinite-sheet formula", "after_label": "Boundary-element solution",
                "before": None, "after": None, "unit": "%", "quantity": "Change in B inside the building",
                "applies": False,
                "text": "Earlier versions credited a shield with the attenuation of an infinite sheet. "
                        "The physical model now solves the induced currents on the finite barrier. "
                        "Switch a shield on to see both numbers for this project."})

        # 5. Quasi-3-D field along the span
        mid = site.profile(z=0.0)
        tow = site.profile(z=site.half_span)
        items.append({
            "id": "span", "title": "Field varies along the span",
            "before_label": "Mid-span (lowest conductors)", "after_label": "At the tower",
            "before": _num(float(np.max(mid["b0"]))), "after": _num(float(np.max(tow["b0"]))),
            "unit": "µT", "quantity": "Peak B at the measurement height", "applies": True,
            "text": "Earlier versions extruded the mid-span cross-section along the whole line. "
                    "Conductors are higher near the towers, so the ground-level field is lower "
                    "there. Compliance is still assessed at mid-span, the worst case."})
    return {"hash": site.key, "items": items}
