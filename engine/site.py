"""
site.py
=======
The whole site in one object: every line, the ground model, the frequency, the
buildings and the shield. `Site` answers "what is the field here, with and
without the shield?" for profiles, grids and arbitrary points, at any position
z along the span.

Replaces solvers.py from the Streamlit version (same role, no Streamlit).
Compliance is evaluated on the UNSHIELDED field at mid-span - always.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import earth, lines as lines_mod, physics, shield_bem, shield_engine as sh, shielding, standards
from .lines import Line

GROUND_MODELS = (earth.PERFECT_CONDUCTOR, earth.FREE_SPACE, earth.COMPLEX_IMAGE)


def _f(d: dict, key: str, default: float, lo: Optional[float] = None,
       hi: Optional[float] = None) -> float:
    try:
        v = float(d.get(key, default))
    except (TypeError, ValueError):
        v = float(default)
    if not math.isfinite(v):
        v = float(default)
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def normalise_building(b: dict, index: int = 0) -> dict:
    """Clean one building dict (accepts the older Streamlit field names)."""
    b = dict(b or {})
    out = {
        "name": str(b.get("name") or f"Building {index + 1}")[:60],
        "type": b.get("type") or b.get("building_type") or "Residential",
        "shape": b.get("shape") or "box",
        "roof": b.get("roof") or "flat",
        "width": _f(b, "width", 20.0, 2.0, 300.0),
        "depth": _f(b, "depth", 20.0, 2.0, 300.0),
        "height": _f(b, "height", 10.0, 2.0, 200.0),
        "distance": _f(b, "distance", b.get("distance_from_centerline", 25.0), 0.0, 500.0),
        "side": "left" if b.get("side") == "left" else "right",
        "z_offset": _f(b, "z_offset", 0.0, -1000.0, 1000.0),
        "material": b.get("material") or b.get("shielding_material") or "none",
        "b_pct": b.get("b_pct", b.get("b_pct_override")),
        "e_pct": b.get("e_pct", b.get("e_pct_override")),
        # storey height for the 3-D model only (None = typical for the building type)
        "floor_h": b.get("floor_h"),
    }
    if out["material"] not in shielding.SHIELDING_MATERIALS:
        out["material"] = "none"
    for k in ("b_pct", "e_pct", "floor_h"):
        try:
            out[k] = None if out[k] is None else float(out[k])
        except (TypeError, ValueError):
            out[k] = None
    if out["floor_h"] is not None:
        out["floor_h"] = min(12.0, max(2.4, out["floor_h"]))
    return out


class Site:
    """Resolved project configuration plus cached field solutions."""

    def __init__(self, cfg: dict):
        cor = dict(cfg.get("corridor") or {})
        self.freq = _f(cor, "freq_hz", 50.0, 1.0, 1000.0)
        gm = cor.get("ground_model", earth.DEFAULT_MODEL)
        self.ground_model = gm if gm in GROUND_MODELS else earth.DEFAULT_MODEL
        self.earth_rho = _f(cor, "earth_rho", 100.0, 0.01, 1e6)
        self.bundle_eq = bool(cor.get("bundle_eq", True))
        self.meas_height = _f(cor, "meas_height", 1.0, 0.1, 10.0)
        self.row_half = _f(cor, "row_half_width", 12.0, 1.0, 500.0)
        self.max_sag = _f(cor, "max_sag_m", 1.5, 0.0, 10.0)
        self.half_span = _f(cor, "span_m", 300.0, 40.0, 1500.0) / 2.0
        #: with "sag follows span" the design and thermal sag scale with (span / 300 m)^2
        self.sag_follows_span = bool(cor.get("sag_follows_span", False))
        self.sag_scale = lines_mod.sag_scale_for(2.0 * self.half_span, self.sag_follows_span)

        presets = lines_mod.tower_presets()
        raw_lines = list(cfg.get("lines") or [lines_mod.default_line()])[:6]
        self.line_cfgs = raw_lines
        self.lines: List[Line] = [lines_mod.build_line(lc, self.max_sag, i, presets, self.sag_scale)
                                  for i, lc in enumerate(raw_lines)]
        self.buildings = [normalise_building(b, i)
                          for i, b in enumerate(list(cfg.get("buildings") or [])[:8])]
        self.standard_ids = [standards.resolve_id(s) for s in
                             (cfg.get("standards") or standards.DEFAULT_STANDARD_IDS)]
        self.shield_cfg = sh.config_from_dict(cfg.get("shield"))

        self.conductors = [c for ln in self.lines for c in ln.conductors]
        xs = [ln.x_centre for ln in self.lines] or [0.0]
        self.centre_x = float(np.mean(xs))
        self.geom = sh.resolve_geometry(self.shield_cfg, self.buildings, self.centre_x)
        self.shield_on = bool(self.shield_cfg.enabled and self.geom.walls)
        self.se_simple = sh.compute_se(self.shield_cfg, self.freq, self.geom.source_distance_m)
        self.warnings = lines_mod.spacing_warnings(self.lines) + lines_mod.clearance_warnings(self.lines)

        num = dict(cfg.get("numerics") or {})
        max_off = max((abs(ln.x_offset) for ln in self.lines), default=0.0)
        right = max([50.0, max_off + 50.0] + [sh.building_bbox(b)[1] + 15.0 for b in self.buildings])
        left = max([50.0, max_off + 50.0] + [-sh.building_bbox(b)[0] + 15.0 for b in self.buildings])
        if self.shield_on:
            wx = [w[0] for w in self.geom.walls] + [w[2] for w in self.geom.walls]
            right = max(right, max(wx) + 15.0)
            left = max(left, -min(wx) + 15.0)
        hw = num.get("x_half_width")
        if hw:
            left = right = _f(num, "x_half_width", 60.0, 20.0, 1000.0)
        self.x_min, self.x_max = -float(math.ceil(left / 5.0) * 5.0), float(math.ceil(right / 5.0) * 5.0)
        top = max((c.y_sagged for c in self.conductors), default=20.0)
        auto_y = max(40.0, math.ceil((top + 8.0) / 5.0) * 5.0)
        self.y_max = _f(num, "y_max", auto_y, 10.0, 200.0) if num.get("y_max") else auto_y
        self.grid_nx = int(_f(num, "grid_nx", 141, 40, 281))
        self.grid_ny = int(_f(num, "grid_ny", 81, 24, 161))

        self._mesh = None
        self._sol: Dict[float, tuple] = {}
        self._prof: Dict[tuple, dict] = {}
        self._grid: Dict[tuple, dict] = {}
        self._summary = None
        self._memo: Dict[tuple, object] = {}     # results of the heavier studies, kept with the site

    # ------------------------------------------------------------------ lines
    def conductors_at(self, z: float = 0.0, line: Optional[int] = None):
        z = self._zkey(z)
        if line is not None:
            return self.lines[line].at_z(z, self.half_span)
        return [c for ln in self.lines for c in ln.at_z(z, self.half_span)]

    def _zkey(self, z: float) -> float:
        return round(min(abs(float(z)), self.half_span), 2)

    def sources_at(self, z: float = 0.0):
        out = []
        for i in range(len(self.lines)):
            g = self.conductors_at(z, i)
            out.append((float(np.mean([c.x for c in g])), float(np.mean([c.y_sagged for c in g]))))
        return out

    # ----------------------------------------------------------------- shield
    def shield_at(self, z: float) -> bool:
        return self.shield_on and self.geom.covers_z(z)

    @property
    def physical(self) -> bool:
        # loops and screening wires only exist in the physical model
        return self.shield_cfg.model == "physical" or self.shield_cfg.is_wire

    def solution(self, z: float = 0.0):
        """(MagneticSolution | None, ElectricSolution | None) for the cross-section at z."""
        key = self._zkey(z)
        if key not in self._sol:
            if self._mesh is None:
                self._mesh = shield_bem.build_mesh(self.geom.plates)
            conds = self.conductors_at(key)
            mag = shield_bem.solve_magnetic(self.geom, self.shield_cfg, conds, self.ground_model,
                                            self.earth_rho, self.freq, self._mesh)
            ele = shield_bem.solve_electric(self.geom, self.shield_cfg, conds, self.freq,
                                            self.bundle_eq, self._mesh)
            self._sol[key] = (mag, ele)
        return self._sol[key]

    # ------------------------------------------------------------- raw fields
    def base_fields(self, X, Y, z: float = 0.0, conductors=None):
        conds = conductors if conductors is not None else self.conductors_at(z)
        b = physics.compute_b_field_at_points(conds, X, Y, self.ground_model, self.earth_rho,
                                              self.freq)
        e = physics.compute_e_field_at_points(conds, X, Y, bundle_equivalent=self.bundle_eq)
        return b, e

    def fields(self, X, Y, z: float = 0.0, want=("B", "E"), assume_shield=None) -> dict:
        """
        b0, e0 (no shield) and bS, eS (with shield) at points (X, Y) in the section at z.
        assume_shield=True treats the barrier as present at this z even outside its
        length (the 3-D view masks by length itself, to keep the ends sharp).
        """
        X = np.asarray(X, float); Y = np.asarray(Y, float)
        conds = self.conductors_at(z)
        out = {}
        shield_here = self.shield_at(z) if assume_shield is None else (self.shield_on and assume_shield)
        if "B" in want:
            out["b0"] = physics.compute_b_field_at_points(conds, X, Y, self.ground_model,
                                                          self.earth_rho, self.freq)
        if "E" in want:
            out["e0"] = physics.compute_e_field_at_points(conds, X, Y,
                                                          bundle_equivalent=self.bundle_eq)
        if not shield_here:
            if "B" in want:
                out["bS"] = out["b0"].copy()
            if "E" in want:
                out["eS"] = out["e0"].copy()
            return out
        if self.physical:
            mag, ele = self.solution(z)
            if "B" in want:
                out["bS"] = mag.b_rms_uT(X, Y) if mag is not None else out["b0"].copy()
            if "E" in want:
                out["eS"] = ele.e_rms_kVm(X, Y) if ele is not None else out["e0"].copy()
            return out
        # simplified models: attenuate the geometric shadow
        wb = we = None
        if len(self.lines) > 1:
            wb, we = [], []
            for i in range(len(self.lines)):
                g = self.conductors_at(z, i)
                wb.append(physics.compute_b_field_at_points(g, X, Y, self.ground_model,
                                                            self.earth_rho, self.freq))
                we.append(physics.compute_e_field_at_points(g, X, Y,
                                                            bundle_equivalent=self.bundle_eq))
        fE, fB = sh.corridor_factors(self.geom, self.se_simple, self.sources_at(z), X, Y, wb, we)
        if "B" in want:
            out["bS"] = out["b0"] * fB
        if "E" in want:
            out["eS"] = out["e0"] * fE
        return out

    # --------------------------------------------------------------- profiles
    def profile(self, x_min=None, x_max=None, n: int = 401, height=None, z: float = 0.0,
                assume_shield=None) -> dict:
        x_min = self.x_min if x_min is None else float(x_min)
        x_max = self.x_max if x_max is None else float(x_max)
        height = self.meas_height if height is None else float(height)
        on = self.shield_at(z) if assume_shield is None else bool(self.shield_on and assume_shield)
        key = (round(x_min, 3), round(x_max, 3), int(n), round(height, 3), self._zkey(z), on)
        if key not in self._prof:
            x = np.linspace(x_min, x_max, int(n))
            r = self.fields(x, np.full_like(x, height), z, assume_shield=on)
            r["x"] = x
            self._prof[key] = r
        return self._prof[key]

    def grid(self, x_min=None, x_max=None, nx=None, y_min=0.3, y_max=None, ny=None,
             z: float = 0.0, assume_shield=None) -> dict:
        x_min = self.x_min if x_min is None else float(x_min)
        x_max = self.x_max if x_max is None else float(x_max)
        y_max = self.y_max if y_max is None else float(y_max)
        nx = self.grid_nx if nx is None else int(nx)
        ny = self.grid_ny if ny is None else int(ny)
        on = self.shield_at(z) if assume_shield is None else bool(self.shield_on and assume_shield)
        key = (round(x_min, 3), round(x_max, 3), nx, round(y_min, 3), round(y_max, 3), ny,
               self._zkey(z), on)
        if key not in self._grid:
            x = np.linspace(x_min, x_max, nx)
            y = np.linspace(y_min, y_max, ny)
            Xg, Yg = np.meshgrid(x, y)
            r = self.fields(Xg, Yg, z, assume_shield=on)
            r["x"], r["y"] = x, y
            if len(self._grid) > 40:
                self._grid.pop(next(iter(self._grid)))
            self._grid[key] = r
        return self._grid[key]

    def at_points(self, pts: Sequence[Tuple[float, float, float]]) -> List[dict]:
        """Exact field at arbitrary (x, y, z) points."""
        out: List[Optional[dict]] = [None] * len(pts)
        by_z: Dict[tuple, list] = {}
        for i, (x, y, z) in enumerate(pts):
            by_z.setdefault((self._zkey(z), self.shield_at(z)), []).append(i)
        for (zk, _on), idx in by_z.items():
            z_real = float(pts[idx[0]][2])
            xs = np.array([pts[i][0] for i in idx], float)
            ys = np.array([max(0.0, pts[i][1]) for i in idx], float)
            r = self.fields(xs, ys, z_real)
            for j, i in enumerate(idx):
                out[i] = {k: float(r[k][j]) for k in ("b0", "e0", "bS", "eS")}
        return out  # type: ignore[return-value]

    def point(self, x: float, y: float, z: float = 0.0) -> dict:
        return self.at_points([(x, y, z)])[0]

    # ---------------------------------------------------------------- summary
    def shield_reference_point(self) -> Optional[Tuple[float, float, float]]:
        """Where the headline shielding numbers are read."""
        if not self.shield_on:
            return None
        cfg = self.shield_cfg
        if self.geom.zone is not None:                       # shielded room: its centre
            x0, x1, y0, y1, z0, z1 = self.geom.zone
            return ((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0)
        if (sh.PRESETS[cfg.preset]["attached"] or cfg.is_wire or cfg.is_custom) and self.buildings:
            b = self.buildings[min(cfg.target_building, len(self.buildings) - 1)]
            x, y, z = sh.building_probe_point(b)
            s = sh.building_sign(b)
            if cfg.preset in ("roof", "floor"):
                return (x + s * (b["width"] / 2.0 - 1.0), min(b["height"] * 0.5, max(1.5, self.meas_height)), z)
            if cfg.is_wire and not self.geom.covers_z(z):
                z = self.geom.z_center
            return (x, y, z)
        w = self.geom.walls[0]
        s = 1.0 if w[0] >= self.centre_x else -1.0
        outer = max(self.geom.walls, key=lambda q: s * q[0])
        back = max(2.0, min(10.0, cfg.height_m / 2.0))
        return (outer[0] + s * back, self.meas_height, self.geom.z_center)

    def shield_se(self) -> sh.SEResult:
        """Headline SE. For the physical model, read from the solved field at the reference point."""
        se = self.se_simple
        if not (self.shield_on and self.physical):
            return se
        ref = self.shield_reference_point()
        r = self.point(*ref)
        note = ("Read from the solved field at the reference point "
                f"(x = {ref[0]:.1f} m, y = {ref[1]:.1f} m). A negative value means the field "
                "is higher there with the shield than without it.")
        return sh.SEResult(sh.se_db(r["e0"], r["eS"]), sh.se_db(r["b0"], r["bS"]),
                           se.skin_depth_m, se.absorption, se.reflection_e, se.reflection_h,
                           se.multi_refl, se.ceiling, "geometry", "geometry", "physical", note,
                           (ref[0], ref[1]))

    def summary(self) -> dict:
        if self._summary is not None:
            return self._summary
        prof = self.profile()
        b0, e0, bS, eS, x = prof["b0"], prof["e0"], prof["bS"], prof["eS"], prof["x"]
        ib, ie = int(np.argmax(b0)), int(np.argmax(e0))
        peak_b, peak_e = float(b0[ib]), float(e0[ie])
        results = standards.evaluate(peak_b, peak_e, self.standard_ids, self.freq)
        gov, gov_q = standards.governing(results)
        row = np.abs(x) >= self.row_half
        self._summary = {
            "peak_b": peak_b, "peak_e": peak_e,
            "peak_b_x": float(x[ib]), "peak_e_x": float(x[ie]),
            "peak_b_shield": float(np.max(bS)), "peak_e_shield": float(np.max(eS)),
            "row_b": float(np.max(b0[row])) if row.any() else None,
            "row_e": float(np.max(e0[row])) if row.any() else None,
            "results": results, "overall": standards.overall_status(results),
            "governing": gov, "governing_q": gov_q,
            "binding": standards.binding_standard(results),
        }
        return self._summary

    # -------------------------------------------------------------- receptors
    def receptors(self) -> List[dict]:
        """Each building's exposure: unshielded, empirical material, and the barrier."""
        out = []
        pts = [sh.building_probe_point(b) for b in self.buildings]
        vals = self.at_points(pts) if pts else []
        for b, p, v in zip(self.buildings, pts, vals):
            row = shielding.shielding_comparison_row(b["name"], b["material"], v["b0"], v["e0"],
                                                     e_pct_override=b.get("e_pct"),
                                                     b_pct_override=b.get("b_pct"))
            in_len = self.shield_at(p[2])
            row.update({
                "shape": b["shape"], "building_type": b["type"], "probe": list(p),
                "barrier_on": bool(in_len),
                "b_barrier_uT": v["bS"], "e_barrier_kVm": v["eS"],
                "barrier_b_reduction_pct": sh.atten_pct(v["b0"], v["bS"]),
                "barrier_e_reduction_pct": sh.atten_pct(v["e0"], v["eS"]),
                "inside_row": abs(p[0]) < self.row_half,
            })
            row.update(self._interior(b))
            out.append(row)
        return out

    def protected_zone(self):
        """
        (label, x0, x1, y0, y1, z) of the space the shield is there to protect:
        the shielded room, otherwise the target building, in the cross-section
        through the building's own position along the line. None without buildings.
        """
        if self.geom.zone is not None and self.buildings:
            b = self.buildings[min(self.shield_cfg.target_building, len(self.buildings) - 1)]
            x0, x1, y0, y1, z0, z1 = self.geom.zone
            return (f"the shielded room in {b['name']}", x0, x1, y0, y1, (z0 + z1) / 2.0)
        if not self.buildings:
            return None
        b = self.buildings[min(self.shield_cfg.target_building, len(self.buildings) - 1)]
        x0, x1, _, h, _, _ = sh.building_bbox(b)
        return (b["name"], x0, x1, 0.0, h, float(b["z_offset"]))

    def covers_building(self, index: int) -> bool:
        """Whether the shield reaches the building along the line (free-standing ones may not)."""
        if not self.shield_on or not self.buildings:
            return False
        b = self.buildings[min(max(index, 0), len(self.buildings) - 1)]
        return self.geom.covers_z(float(b["z_offset"]))

    #: Interior statistics are taken on this many points across and up the space.
    AREA_GRID = (17, 9)

    def area_stats(self, x0: float, x1: float, y0: float, y1: float, z: float, margin: float = 1.0) -> dict:
        """
        Area-average and worst-point field over a rectangle of the cross-section
        at z, kept `margin` clear of its edges, without and with the shield:
        {"b": {avg0, avgS, max0, maxS, reduction_pct}, "e": {...}}. The average is
        a trapezoidal integral, so points on the edge of the region count half.
        (Up to v4.1 it was a plain mean of 45 points, which over-weighted the
        edges - where a shield raises the field - by a few percentage points.)
        """
        m = min(margin, (x1 - x0) / 4.0, (y1 - y0) / 4.0)
        nx, ny = self.AREA_GRID
        xs = np.linspace(x0 + m, x1 - m, nx)
        ys = np.linspace(y0 + m, max(y0 + m, y1 - m), ny)
        X, Y = np.meshgrid(xs, ys)
        wx = np.ones(nx); wx[[0, -1]] = 0.5
        wy = np.ones(ny); wy[[0, -1]] = 0.5
        W = np.outer(wy, wx)
        W /= W.sum()
        r = self.fields(X, Y, z)
        out = {}
        for q in ("b", "e"):
            v0, vs = r[q + "0"], r[q + "S"]
            a0, a1 = float(np.sum(v0 * W)), float(np.sum(vs * W))
            out[q] = {"avg0": a0, "avgS": a1, "max0": float(np.max(v0)), "maxS": float(np.max(vs)),
                      "reduction_pct": float(sh.atten_pct(a0, a1))}
        return out

    def zone_stats(self) -> Optional[dict]:
        """Average and worst-point field over the protected space, without and with the shield."""
        zone = self.protected_zone()
        if zone is None:
            return None
        label, x0, x1, y0, y1, z = zone
        out = {"label": label, "box": [x0, x1, y0, y1], "z": z}
        out.update(self.area_stats(x0, x1, y0, y1, z, 0.5 if self.geom.zone is not None else 1.0))
        return out

    def building_stats(self, index: int) -> Optional[dict]:
        """zone_stats() for any building: the field over its inside, 1 m clear of walls, floor and roof."""
        if not self.buildings:
            return None
        b = self.buildings[min(max(index, 0), len(self.buildings) - 1)]
        x0, x1, _, h, _, _ = sh.building_bbox(b)
        z = float(b["z_offset"])
        out = {"label": b["name"], "box": [x0, x1, 0.0, h], "z": z}
        out.update(self.area_stats(x0, x1, 0.0, h, z))
        return out

    def _interior(self, b: dict) -> dict:
        """
        Field over the inside of a building (1 m clear of the walls, floor and
        roof, in the cross-section through its centre): the area average and the
        worst point, without and with the shield. One probe point can sit in a
        hot or a quiet spot; this is the fairer summary of what the occupants see.
        """
        x0, x1, _, h, _, _ = sh.building_bbox(b)
        st = self.area_stats(x0, x1, 0.0, h, float(b["z_offset"]))
        out = {}
        for q, unit in (("b", "uT"), ("e", "kVm")):
            v = st[q]
            out[f"{q}_in_avg_{unit}"] = v["avg0"]
            out[f"{q}_in_max_{unit}"] = v["max0"]
            out[f"{q}_in_avg_shield_{unit}"] = v["avgS"]
            out[f"{q}_in_max_shield_{unit}"] = v["maxS"]
            out[f"{q}_in_reduction_pct"] = v["reduction_pct"]
        return out

    # ------------------------------------------------------- what-if variants
    def with_shield(self, **changes) -> "Site":
        """Same site with a different shield (used by the comparison sweeps)."""
        twin = Site.__new__(Site)
        twin.__dict__.update(self.__dict__)
        twin.shield_cfg = sh.with_changes(self.shield_cfg, **changes)
        twin.geom = sh.resolve_geometry(twin.shield_cfg, twin.buildings, twin.centre_x)
        twin.shield_on = bool(twin.shield_cfg.enabled and twin.geom.walls)
        twin.se_simple = sh.compute_se(twin.shield_cfg, twin.freq, twin.geom.source_distance_m)
        twin._mesh, twin._sol, twin._prof, twin._grid, twin._summary, twin._memo = None, {}, {}, {}, None, {}
        return twin

    def with_ground(self, ground_model: str) -> "Site":
        twin = Site.__new__(Site)
        twin.__dict__.update(self.__dict__)
        twin.ground_model = ground_model
        twin._mesh, twin._sol, twin._prof, twin._grid, twin._summary, twin._memo = None, {}, {}, {}, None, {}
        return twin

    def earth_note(self) -> str:
        return earth.describe(self.ground_model, self.earth_rho)
