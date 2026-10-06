"""
validation.py
=============
Comparison of Taki's calculated profile against reference or measured points,
plus analytical self-checks of the field solvers.

Metrics (unchanged from the previous version):
  RMSE   root-mean-square error
  NRMSE  RMSE normalised by the range of the reference data
  MAPE   mean absolute percentage error, EXCLUDING near-zero reference points
         (and counting how many were excluded)

New in v4: `self_checks()` runs first-principles verifications of the solvers
(single wire, RMS-resultant definition, earth image, electric-field gauss
check, shield solver against the exact infinite-slab solution) and reports
each as a number, so "verified" is a result rather than a claim.
"""

from __future__ import annotations

import csv
import io
import math
from typing import Dict, List, Optional, Tuple

import numpy as np

_DIST_NAMES = ("distance", "dist", "x", "lateraldistance", "distancem", "xm")
_FIELD_NAMES = ("bfield", "b", "magneticfield", "field", "measuredfield", "but", "bfieldut", "but")


def parse_field_meter_csv(text) -> Dict[str, np.ndarray]:
    """
    Parse field-meter data given as CSV text (or bytes).

    Expected columns (case-insensitive, flexible naming): Distance [m] and
    B_Field [µT]. A file with no header and two numeric columns is also
    accepted. Returns {"Distance": array, "B_Field": array} sorted by distance.
    Raises ValueError with a readable message on any problem.
    """
    if isinstance(text, (bytes, bytearray)):
        try:
            text = bytes(text).decode("utf-8-sig")
        except UnicodeDecodeError:
            text = bytes(text).decode("latin-1")
    if hasattr(text, "read"):
        if hasattr(text, "seek"):
            text.seek(0)
        raw = text.read()
        text = raw.decode("utf-8-sig") if isinstance(raw, (bytes, bytearray)) else raw
    text = (text or "").strip()
    if not text:
        raise ValueError("The file is empty.")
    try:
        dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;\t ")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        raise ValueError("The file has no rows.")

    def norm(s):
        return "".join(ch for ch in s.lower() if ch.isalnum())

    def num(s):
        try:
            v = float(str(s).strip().replace(",", "."))
            return v if math.isfinite(v) else None
        except ValueError:
            return None

    header = [norm(c) for c in rows[0]]
    d_col = next((i for i, h in enumerate(header) if h in _DIST_NAMES), None)
    f_col = next((i for i, h in enumerate(header) if h in _FIELD_NAMES), None)
    body = rows[1:]
    if d_col is None or f_col is None:
        if len(rows[0]) >= 2 and num(rows[0][0]) is not None and num(rows[0][1]) is not None:
            d_col, f_col, body = 0, 1, rows        # headerless two-column data
        else:
            raise ValueError("The CSV needs a 'Distance' column and a 'B_Field' column "
                             f"(found: {', '.join(rows[0])}).")
    pts = []
    for r in body:
        if len(r) <= max(d_col, f_col):
            continue
        d, b = num(r[d_col]), num(r[f_col])
        if d is not None and b is not None:
            pts.append((d, b))
    if not pts:
        raise ValueError("No numeric Distance / B_Field rows were found.")
    pts.sort()
    return {"Distance": np.array([p[0] for p in pts]), "B_Field": np.array([p[1] for p in pts])}


def interpolate_simulated_curve(sim_distance, sim_field, measured_distance) -> np.ndarray:
    sim_distance = np.asarray(sim_distance, float)
    order = np.argsort(sim_distance)
    return np.interp(measured_distance, sim_distance[order], np.asarray(sim_field, float)[order])


def compute_rmse(simulated, measured) -> float:
    simulated = np.asarray(simulated, float); measured = np.asarray(measured, float)
    if simulated.size == 0:
        return float("nan")
    return float(np.sqrt(np.mean((simulated - measured) ** 2)))


def compute_mape(simulated, measured, zero_threshold: float = 1e-3):
    """MAPE excluding near-zero reference points. Returns (mape_percent, n_used, n_excluded)."""
    simulated = np.asarray(simulated, float); measured = np.asarray(measured, float)
    if simulated.size == 0:
        return float("nan"), 0, 0
    usable = np.abs(measured) >= zero_threshold
    n_used = int(usable.sum())
    n_excluded = int(measured.size - n_used)
    if n_used == 0:
        return float("nan"), 0, n_excluded
    err = np.abs((simulated[usable] - measured[usable]) / measured[usable])
    return float(np.mean(err) * 100.0), n_used, n_excluded


def compute_nrmse(simulated, measured) -> float:
    measured = np.asarray(measured, float)
    if measured.size == 0:
        return float("nan")
    spread = float(np.max(measured) - np.min(measured))
    if spread <= 0:
        return float("nan")
    return compute_rmse(simulated, measured) / spread * 100.0


def check_domain_coverage(sim_distance, measured_distance):
    sim_distance = np.asarray(sim_distance, float)
    measured_distance = np.asarray(measured_distance, float)
    lo, hi = float(np.min(sim_distance)), float(np.max(sim_distance))
    outside = (measured_distance < lo) | (measured_distance > hi)
    return int(outside.sum()), lo, hi


def compare_simulation_to_measured(sim_distance, sim_field, measured: Dict[str, np.ndarray]) -> dict:
    """Full comparison. `measured` is {"Distance": array, "B_Field": array}."""
    md = np.asarray(measured["Distance"], float)
    mf = np.asarray(measured["B_Field"], float)
    sim_at = interpolate_simulated_curve(sim_distance, sim_field, md)
    mape, n_used, n_excl = compute_mape(sim_at, mf)
    n_out, lo, hi = check_domain_coverage(sim_distance, md)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratios = np.where(mf != 0, sim_at / mf, np.nan)
    return {
        "rmse": compute_rmse(sim_at, mf), "nrmse_percent": compute_nrmse(sim_at, mf),
        "mape": mape, "mape_n_used": n_used, "mape_n_excluded": n_excl,
        "n_outside_domain": n_out, "domain_min": lo, "domain_max": hi,
        "simulated": sim_at, "measured": mf, "distance": md, "ratio": ratios,
        "mean_ratio": float(np.nanmean(ratios)) if np.isfinite(ratios).any() else float("nan"),
        "n_points": int(mf.size),
    }


# ---------------------------------------------------------------------------
# First-principles self-checks
# ---------------------------------------------------------------------------
def _slab_exact(I, xs, t, sigma, mur, f, xo, yo):
    """Exact |B| behind an infinite slab at x = xs for a line current at the origin [T]."""
    mu0 = 4e-7 * math.pi
    w = 2 * math.pi * f
    k = np.logspace(-7, 3, 120001)
    g = np.sqrt(k ** 2 + 1j * w * mu0 * mur * sigma)
    a = mur * k / g
    gt = g * t
    T = 2 * np.exp(-gt) / ((1 + np.exp(-2 * gt)) + 0.5 * (a + 1 / a) * (1 - np.exp(-2 * gt)))
    e = np.exp(-k * (xo - t))
    trap = getattr(np, "trapezoid", None) or np.trapz
    bx = mu0 * I / (2 * math.pi) * trap(-T * e * np.sin(k * yo), k)
    by = mu0 * I / (2 * math.pi) * trap(T * e * np.cos(k * yo), k)
    return math.sqrt(abs(bx) ** 2 + abs(by) ** 2)


def self_checks() -> List[dict]:
    """
    Run analytical verifications of the solvers. Each entry:
    {id, title, detail, expected, got, unit, error_pct, tolerance_pct, passed, kind}.
    """
    from . import earth, physics, shield_bem as bem, shield_engine as sh
    mu0 = 4e-7 * math.pi
    out = []

    def add(id, title, detail, expected, got, unit, tol, kind="verification"):
        err = abs(got - expected) / abs(expected) * 100.0 if expected else abs(got - expected) * 100.0
        out.append({"id": id, "title": title, "detail": detail, "expected": float(expected),
                    "got": float(got), "unit": unit, "error_pct": float(err),
                    "tolerance_pct": tol, "passed": bool(err <= tol), "kind": kind})

    # 1. single wire, free space
    c = physics.Conductor(x=0, y_base=20, phase="A", current_A=1000, voltage_kV=0)
    got = float(physics.compute_b_field_at_points([c], np.array([15.0]), np.array([1.0]),
                                                  earth.FREE_SPACE)[0])
    add("single_wire", "Single wire in free space",
        "B = mu0 I / (2 pi r) for 1000 A at r = 24.2 m.",
        mu0 * 1000 / (2 * math.pi * math.hypot(15, 19)) * 1e6, got, "µT", 1e-6)

    # 2. RMS resultant equals the time-domain definition
    pres = physics.get_tower_presets()["132kV Double Circuit Lattice"]["conductors"]
    x = np.array([7.5]); y = np.array([1.0])
    got = float(physics.compute_b_field_at_points(pres, x, y, earth.FREE_SPACE)[0])
    t = np.linspace(0, 0.02, 4001)[:-1]
    bx = np.zeros_like(t); by = np.zeros_like(t)
    for cc in pres:
        th = physics.conductor_angle_rad(cc)
        i_t = math.sqrt(2) * cc.current_A * np.cos(2 * math.pi * 50 * t + th)
        dx, dy = x[0] - cc.x, y[0] - cc.y_sagged
        r2 = dx * dx + dy * dy
        bx += mu0 * i_t / (2 * math.pi) * (-dy) / r2
        by += mu0 * i_t / (2 * math.pi) * dx / r2
    add("rms_resultant", "RMS resultant matches the time-domain definition",
        "sqrt(mean(|B(t)|^2)) over one cycle, from sinusoidal phase currents of the stated RMS "
        "value, against Taki's sqrt(|Bx|^2 + |By|^2). Confirms Taki reports an RMS field for RMS "
        "currents (the convention used by ICNIRP reference levels).",
        float(np.sqrt(np.mean(bx ** 2 + by ** 2)) * 1e6), got, "µT", 1e-6)

    # 3. perfect-conductor image: normal B vanishes at the ground plane
    _, bxg, byg = bem.source_abh(pres, np.array([9.0]), np.array([0.0]), earth.PERFECT_CONDUCTOR,
                                 100.0, 50.0)
    add("earth_image", "Perfectly conducting earth: no flux through the ground plane",
        "Vertical B at ground level relative to horizontal B (should be zero).",
        0.0, float(abs(byg[0]) / max(abs(bxg[0]), 1e-30)), "ratio", 1e-6)

    # 4. electric field: Gauss / potential check - potential on a conductor surface equals V
    q = physics.solve_conductor_charges(pres)
    c0 = pres[0]
    k = 1.0 / (2 * math.pi * 8.8541878128e-12)
    r_eq = physics.bundle_equivalent_radius(c0, 0.015)
    phi = 0j
    for cc, qq in zip(pres, q):
        if cc is c0:
            phi += k * qq * math.log(2 * cc.y_sagged / r_eq)
        else:
            d = math.hypot(c0.x - cc.x, c0.y_sagged - cc.y_sagged)
            di = math.hypot(c0.x - cc.x, c0.y_sagged + cc.y_sagged)
            phi += k * qq * math.log(di / d)
    add("e_potential", "Electric field: conductor potential reproduced",
        "Potential on phase A from the solved charges against its applied phase voltage.",
        c0.voltage_kV / math.sqrt(3), float(abs(phi) / 1000.0), "kV", 1e-6)

    # 5. shield solver vs the exact infinite-slab solution
    for sid, name, sigma, mur, tt in (("slab_al", "aluminium 3 mm", 3.5e7, 1.0, 0.003),
                                      ("slab_steel", "steel 3 mm (mu_r 200)", 1.0e7, 200.0, 0.003),
                                      ("slab_mu", "pure magnetic sheet (mu_r 1000, 2 mm)", 0.0, 1000.0, 0.002)):
        cw = physics.Conductor(x=0.0, y_base=100.0, phase="A", current_A=1000.0, voltage_kV=0)
        cfg = sh.ShieldConfig(enabled=True, material_id="custom",
                              custom_material={"sigma": sigma, "mu_r": mur}, thickness_m=tt)
        plate = sh.Plate([(2.0, 30.0), (2.0, 170.0)], 0, True)
        geom = sh.Geometry([(2.0, 30.0, 2.0, 170.0)], 0, 1e9, 2.0, "check", [plate])
        mesh = bem.build_mesh([plate], ds_target=0.35, max_elements=600)
        sol = bem.solve_magnetic(geom, cfg, [cw], earth.FREE_SPACE, 100.0, 50.0, mesh,
                                 closed_return=True)
        bxs, bys = sol.b_total(np.array([4.0]), np.array([100.0]))
        got = math.sqrt(abs(bxs[0]) ** 2 + abs(bys[0]) ** 2) * 1e6
        add(sid, f"Shield solver vs exact infinite slab - {name}",
            "Line current 2 m from a 140 m-wide plate with a closed return; field 2 m behind it "
            "against the exact Fourier solution for an infinite slab.",
            _slab_exact(1000.0, 2.0, tt, sigma, mur, 50.0, 4.0, 0.0) * 1e6, got, "µT", 5.0)

    # 6. closed shells (the "around the building" case) vs the thin cylindrical shell formulas.
    # A far-away line current gives a nearly uniform field across the cylinder.
    a_r, n_seg = 3.0, 40
    ring = [(a_r * math.cos(2 * math.pi * i / n_seg), 50.0 + a_r * math.sin(2 * math.pi * i / n_seg))
            for i in range(n_seg + 1)]
    ring[-1] = ring[0]
    far = physics.Conductor(x=-4000.0, y_base=50.0, phase="A", current_A=2.0e7, voltage_kV=0)
    b_free = physics.compute_b_field_at_points([far], np.array([0.0]), np.array([50.0]),
                                               earth.FREE_SPACE, 100.0, 50.0)[0]
    for sid, name, sigma, mur, tt, exact in (
            ("shell_al", "aluminium shell, 3 mm", 3.5e7, 1.0, 0.003,
             1.0 / abs(1.0 + 1j * 2 * math.pi * 50.0 * sh.MU0 * 3.5e7 * 0.003 * a_r / 2.0)),
            ("shell_mu", "magnetic shell (mu_r 2000, 2 mm)", 0.0, 2000.0, 0.002,
             1.0 / (1.0 + (2000.0 - 1.0) * 0.002 / (2.0 * a_r)))):
        cfg = sh.ShieldConfig(enabled=True, material_id="custom",
                              custom_material={"sigma": sigma, "mu_r": mur}, thickness_m=tt)
        plate = sh.Plate(ring, 0, True)
        geom = sh.Geometry([], 0, 1e9, 4000.0, "check", [plate])
        mesh = bem.build_mesh([plate], ds_target=0.08, max_elements=900)
        sol = bem.solve_magnetic(geom, cfg, [far], earth.FREE_SPACE, 100.0, 50.0, mesh)
        got = float(sol.b_rms_uT(np.array([0.0]), np.array([50.0]))[0])
        add(sid, f"Closed shell vs thin-cylinder formula - {name}",
            f"Uniform 50 Hz field across a closed cylindrical shell of radius {a_r:g} m with no net "
            "current (as for a shield wrapped round a room or a building); field at the centre "
            "against the analytical thin-shell result.",
            float(b_free * exact), got, "µT", 5.0)
    # 7. passive loop: induced current against circuit theory, I = jw*dA / (R + jw(L - L_c)).
    src = physics.Conductor(x=0.0, y_base=60.0, phase="A", current_A=1000.0, voltage_kV=0)
    w = 2 * math.pi * 50.0
    for sid, comp in (("loop", 0.0), ("loop_comp", 70.0)):
        cfg = sh.ShieldConfig(enabled=True, preset="passive-loop", material_id="aluminium", side="right",
                              distance_m=9.0, height_m=50.0, loop_spacing_m=10.0, loop_vertical=False,
                              wire_mm2=400.0, loop_compensation_pct=comp, length_m=1e6)
        geom = sh.resolve_geometry(cfg, [], 0.0)
        sol = bem.solve_magnetic(geom, cfg, [src], earth.FREE_SPACE, 100.0, 50.0, bem.build_mesh(geom.plates))
        (xa, ya), (xb, yb) = geom.wires
        r_w = cfg.wire_radius_m
        d_a, d_b = math.hypot(xa, ya - 60.0), math.hypot(xb, yb - 60.0)
        d_a_flux = mu0 * 1000.0 / (2 * math.pi) * math.log(d_b / d_a)          # flux linked per metre
        l_ext = mu0 / math.pi * math.log(math.hypot(xa - xb, ya - yb) / r_w)
        l_loop = l_ext + mu0 / (4 * math.pi)                                   # + internal, solid round wires
        r_loop = 2.0 / (cfg.material.sigma * cfg.wire_mm2 * 1e-6)
        expected = w * d_a_flux / abs(r_loop + 1j * w * (l_loop - comp / 100.0 * l_ext))
        add(sid, "Passive loop vs circuit theory" + (f" - {comp:g}% series-compensated" if comp else ""),
            "Current induced in a two-conductor loop (400 mm2 aluminium, 10 m apart) by a 1000 A line "
            "current, against the loop equation with the two-wire inductance and the conductors' "
            "resistance" + (", with a series capacitor cancelling 70% of the reactance." if comp else "."),
            expected, float(abs(sol.plate_currents()[0])), "A", 3.0)

    # 8. field lines are drawn as contours of the vector potential A. That is only right if the
    # curl of that potential is the field the solver reports, shield currents and magnetisation included.
    line = physics.Conductor(x=0.0, y_base=20.0, phase="A", current_A=1000.0, voltage_kV=0)
    for sid, name, sigma, mur, tt in (("lines_al", "aluminium sheet, 3 mm", 3.5e7, 1.0, 0.003),
                                      ("lines_steel", "steel sheet, 6 mm (mu_r 200)", 1.0e7, 200.0, 0.006)):
        cfg = sh.ShieldConfig(enabled=True, material_id="custom",
                              custom_material={"sigma": sigma, "mu_r": mur}, thickness_m=tt)
        plate = sh.Plate([(10.0, 0.3), (10.0, 12.0)], 0, True)
        geom = sh.Geometry([(10.0, 0.3, 10.0, 12.0)], 0, 1e9, 10.0, "check", [plate])
        sol = bem.solve_magnetic(geom, cfg, [line], earth.PERFECT_CONDUCTOR, 100.0, 50.0,
                                 bem.build_mesh([plate]))
        px, py, h = np.array([13.0]), np.array([4.0]), 1e-3
        bxs, bys = sol.b_total(px, py)
        cx = (sol.a_total(px, py + h) - sol.a_total(px, py - h)) / (2 * h)       # Bx =  dA/dy
        cy = -(sol.a_total(px + h, py) - sol.a_total(px - h, py)) / (2 * h)      # By = -dA/dx
        add(sid, f"Field lines: the potential they are drawn from gives back the solved field - {name}",
            "A 1000 A line over conducting earth with a 12 m sheet standing 10 m from it. The magnetic "
            "field 3 m behind the sheet, taken as the curl of the vector potential whose contours are "
            "drawn as field lines, against the field the shield solver reports there.",
            math.sqrt(abs(bxs[0]) ** 2 + abs(bys[0]) ** 2) * 1e6,
            math.sqrt(abs(cx[0]) ** 2 + abs(cy[0]) ** 2) * 1e6, "µT", 0.5)
    return out
