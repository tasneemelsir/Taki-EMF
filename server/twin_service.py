"""
twin_service.py
===============
Packages the solved site for the interactive 3-D digital twin. Python remains
the single source of truth for every number: the browser draws and
interpolates what it is given, and asks for an exact value when a point is
pinned.

The field is "quasi-3-D": at each position z along the span the 2-D solution
for the conductor heights AT THAT z is used, so the ground map is strongest at
mid-span (lowest conductors) and weakens towards the towers. Earlier versions
extruded the mid-span section along the whole span.
"""

from __future__ import annotations

import numpy as np

from engine import libraries, shield_engine as sh
from engine.site import Site

from . import service
from .service import _num, b64

STAGE_PHASE = {"A": "#E5533D", "B": "#F2B705", "C": "#3D8BFD"}
GROUND_NX = 241
GROUND_NZ = 25
SECTION_NX = 161
SECTION_NY = 81
VOL_NX, VOL_NY, VOL_NZ = 96, 40, 17


def _extent(site: Site):
    x0 = min(site.x_min, -60.0)
    x1 = max(site.x_max, 60.0)
    return float(x0), float(x1)


def _limits(site: Site):
    res = site.summary()["results"]
    b = [r.b.limit for r in res if r.b.limit is not None]
    e = [r.e.limit for r in res if r.e.limit is not None]
    name_b = next((r.standard.name for r in res if r.b.limit is not None and r.b.limit == min(b)), None) if b else None
    return (min(b) if b else None), (min(e) if e else None), name_b


def scene(cfg: dict) -> dict:
    site = service.site_for(cfg)
    with site.lock:
        x0, x1 = _extent(site)
        span = site.half_span
        # ---- ground map at the measurement height, slice by slice along the span ----
        zs = np.linspace(-span, span, GROUND_NZ)
        gB0 = np.zeros((GROUND_NZ, GROUND_NX), "f4"); gBS = gB0.copy()
        gE0 = gB0.copy(); gES = gB0.copy()
        for j, z in enumerate(zs):
            p = site.profile(x0, x1, GROUND_NX, site.meas_height, float(z), assume_shield=True)
            gB0[j], gBS[j], gE0[j], gES[j] = p["b0"], p["bS"], p["e0"], p["eS"]

        b_lim, e_lim, std_name = _limits(site)
        rec = site.receptors()
        buildings = []
        for b, r in zip(site.buildings, rec):
            bt = libraries.building_type(b["type"])
            near, far = sh.building_x(b)
            buildings.append({
                "name": b["name"], "type": b["type"], "shape": b["shape"], "roof": b["roof"],
                "x_near": near, "x_far": far, "x0": min(near, far), "w": b["width"], "d": b["depth"],
                "h": b["height"], "z": b["z_offset"], "side": b["side"],
                "floor_h": b.get("floor_h") or bt["floor_h"], "glazing": bt["glazing"], "plant": bt["plant"],
                "color": bt["colour"], "rooftop": bt["rooftop"], "sensitivity": bt["sensitivity"],
                "probe": r["probe"],
                # at the probe point (1 m inside the wall facing the line)...
                "b0": _num(r["b_unshielded_uT"]), "bS": _num(r["b_barrier_uT"]),
                "e0": _num(r["e_unshielded_kVm"]), "eS": _num(r["e_barrier_kVm"]),
                # ...and averaged over the inside, which is what the labels and every other page show
                "b_in0": _num(r["b_in_avg_uT"]), "b_inS": _num(r["b_in_avg_shield_uT"]),
                "e_in0": _num(r["e_in_avg_kVm"]), "e_inS": _num(r["e_in_avg_shield_kVm"]),
            })
        shd = service.shield_json(site)

        # default section plane: through the first building if it is inside the barrier, else mid-span
        zc = 0.0
        if site.shield_on:
            zc = float(np.clip(site.geom.z_center, -span + 5, span - 5))
        elif buildings:
            zc = float(np.clip(buildings[0]["z"], -span + 5, span - 5))
        top = max((c["y_att"] for ln in service.lines_json(site) for c in ln["conductors"]), default=30.0)
        return {
            "hash": site.key, "span": span, "row": site.row_half, "meas_height": site.meas_height,
            "freq": site.freq, "ground_short": service.earth.MODEL_INFO[site.ground_model]["short"],
            "x0": x0, "x1": x1, "y_top": float(max(site.y_max, top + 10.0)),
            "lines": service.lines_json(site), "buildings": buildings, "shield": shd,
            "limits": {"b": _num(b_lim), "e": _num(e_lim), "name": std_name},
            "phase_colors": STAGE_PHASE, "zc_default": zc,
            "peak_b": _num(site.summary()["peak_b"]), "peak_e": _num(site.summary()["peak_e"]),
            "ground": {"nx": GROUND_NX, "nz": GROUND_NZ, "z": [float(v) for v in zs],
                       "B0": b64(gB0), "BS": b64(gBS), "E0": b64(gE0), "ES": b64(gES)},
        }


def section(cfg: dict, z: float) -> dict:
    """x-y field section at position z along the span (exact conductor heights at z)."""
    site = service.site_for(cfg)
    with site.lock:
        x0, x1 = _extent(site)
        y1 = float(max(site.y_max, 40.0))
        g = site.grid(x0, x1, SECTION_NX, 0.3, y1, SECTION_NY, float(z))
        return {"hash": site.key, "z": float(z), "x0": x0, "x1": x1, "y0": 0.3, "y1": y1,
                "nx": SECTION_NX, "ny": SECTION_NY, "shield_here": site.shield_at(float(z)),
                "B0": b64(g["b0"]), "BS": b64(g["bS"]), "E0": b64(g["e0"]), "ES": b64(g["eS"])}


def volume(cfg: dict) -> dict:
    """
    Coarse 3-D field volume for the volumetric "field glow" and the 3-D
    iso-surface. Values are log-encoded to 8 bits per sample (the picture
    needs dynamic range, not precision; exact numbers come from /points).
    Layout: z slices (symmetric half only is solved), each ny rows by nx columns.
    """
    site = service.site_for(cfg)
    with site.lock:
        x0, x1 = _extent(site)
        y0, y1 = 0.0, float(max(site.y_max, 40.0))
        span = site.half_span
        zs = np.linspace(-span, span, VOL_NZ)
        x = np.linspace(x0, x1, VOL_NX)
        y = np.linspace(y0 + 0.3, y1, VOL_NY)
        Xg, Yg = np.meshgrid(x, y)
        out = {k: np.zeros((VOL_NZ, VOL_NY, VOL_NX), "f4") for k in ("b0", "bS", "e0", "eS")}
        cache = {}
        for j, z in enumerate(zs):
            key = round(abs(float(z)), 2)        # the sag profile is symmetric about mid-span
            if key not in cache:
                # the barrier is assumed present at every z; the viewer masks it to its length
                cache[key] = site.fields(Xg, Yg, float(z), assume_shield=True)
            for k in out:
                out[k][j] = cache[key][k]

        def enc(a, lo, hi):
            t = np.log10(np.maximum(a, lo) / lo) / np.log10(hi / lo)
            return service.base64.b64encode(np.clip(t * 255.0, 0, 255).astype("u1").tobytes()).decode("ascii")

        b_hi = float(max(np.max(out["b0"]), 1e-6)); b_lo = b_hi / 1e4
        e_hi = float(max(np.max(out["e0"]), 1e-9)); e_lo = e_hi / 1e4
        return {"hash": site.key, "nx": VOL_NX, "ny": VOL_NY, "nz": VOL_NZ,
                "x0": x0, "x1": x1, "y0": float(y[0]), "y1": y1, "z0": -span, "z1": span,
                "b_lo": b_lo, "b_hi": b_hi, "e_lo": e_lo, "e_hi": e_hi,
                "B0": enc(out["b0"], b_lo, b_hi), "BS": enc(out["bS"], b_lo, b_hi),
                "E0": enc(out["e0"], e_lo, e_hi), "ES": enc(out["eS"], e_lo, e_hi)}
