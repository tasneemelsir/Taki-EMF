"""
lines.py
========
Turns a line definition (a tower preset or a custom geometry, plus loading,
phasing and overrides) into the conductor set the field solvers use.

TWO THINGS THIS MODULE FIXES
----------------------------
1. LOADING NOW SCALES THE CURRENT. In every earlier version of Taki the
   "Loading (%)" control only changed the thermal sag; the conductors always
   carried their full rated current, so a line at 20 % loading produced the same
   magnetic field as at 100 % (apart from a small height change). The operating
   current is now  I = I_rated x loading / 100.  At 100 % loading the magnetic
   field is identical to earlier versions (tests/test_physics.py checks this
   against the original module, to 12 significant figures).

2. HEIGHT VARIES ALONG THE SPAN. Each conductor has an attachment height at the
   tower and a (lower) mid-span height. The solvers can be asked for the
   conductor set at any position z along the span, which is how the digital
   twin shows the field falling off towards the towers instead of extruding one
   cross-section. Compliance is always evaluated at mid-span (z = 0), where the
   conductors are lowest and the ground-level field is highest.

3. EACH CIRCUIT OF A MULTI-CIRCUIT TOWER CAN BE SET ON ITS OWN. A line definition
   may carry a "circuits" list: one entry per circuit with its own voltage,
   rated current, loading, phase order and an in-service switch. A circuit that
   is out of service is de-energised and earthed: no current, zero potential,
   but its conductors stay in the electric-field problem: earthed wires beside
   live ones raise the field a little close to the line and lower it further out.
   Without the list every circuit uses the line's values, as before.

4. SAG CAN FOLLOW THE SPAN. With `sag_scale` = (span / 300 m)^2 the design sag
   and the thermal sag grow with the square of the span while the attachment
   heights at the towers stay where they are, so a longer span hangs lower at
   mid-span. With sag_scale = 1 (the default) nothing changes.

Coordinates: x lateral (line centre = 0), y up, z along the line (0 = mid-span).
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import physics
from .physics import Conductor

#: Design sag used for the built-in presets: attachment height above the
#: no-load mid-span height. Custom lines set their own.
DEFAULT_DESIGN_SAG_M = 6.0

#: The span the design sag is quoted for. "Sag follows span" scales from here.
REFERENCE_SPAN_M = 300.0

#: A tower with two voltage levels, after the geometry published by Fikry et al. (2022), Table 2.
QUAD_PRESET = "275/132kV Quadruple Circuit Lattice"

PHASE_ORDERS = ("ABC", "CBA")
_REVERSE = {"A": "C", "B": "B", "C": "A"}

CUSTOM = "custom"

CUSTOM_LAYOUTS = {
    "horizontal": "Horizontal (flat, single circuit)",
    "delta": "Delta (single circuit)",
    "vertical": "Vertical (single circuit)",
    "double-vertical": "Vertical double circuit",
}

DEFAULT_CUSTOM = {
    "layout": "horizontal",
    "attach_height_m": 28.0,     # attachment height of the top phase at the tower
    "design_sag_m": 8.0,         # attachment -> no-load mid-span drop
    "phase_spacing_m": 7.0,      # horizontal spacing between adjacent phases
    "vertical_spacing_m": 5.0,   # vertical spacing between phases (delta / vertical layouts)
    "circuit_spacing_m": 10.0,   # distance between the two circuits (double circuit)
    "bundle_n": 2,
    "bundle_spacing_m": 0.4,
    "radius_mm": 15.9,           # sub-conductor radius
    "current_a": 1400.0,
    "voltage_kv": 275.0,
    "row_width_m": 30.0,
    "tower_style": "lattice",    # "lattice" | "monopole" (drawing only)
}


def bundle_offsets(n: int, spacing_m: float) -> List[Tuple[float, float]]:
    """Sub-conductor offsets for an n-bundle with adjacent spacing `spacing_m`."""
    n = int(n)
    if n <= 1:
        return []
    if n == 2:
        return [(-spacing_m / 2.0, 0.0), (spacing_m / 2.0, 0.0)]
    radius = spacing_m / (2.0 * math.sin(math.pi / n))
    start = math.pi / 2.0 if n % 2 else math.pi / n      # triangle point-up, square flat
    return [(round(radius * math.cos(start + 2 * math.pi * k / n), 6),
             round(radius * math.sin(start + 2 * math.pi * k / n), 6)) for k in range(n)]


def custom_preset(c: Optional[dict]) -> dict:
    """Build a preset-shaped dict from custom geometry parameters."""
    p = dict(DEFAULT_CUSTOM)
    p.update({k: v for k, v in (c or {}).items() if v is not None})
    layout = p["layout"] if p["layout"] in CUSTOM_LAYOUTS else "horizontal"
    sag = max(0.0, float(p["design_sag_m"]))
    h = max(3.0, float(p["attach_height_m"]) - sag)      # no-load mid-span height of the top phase
    s = max(0.5, float(p["phase_spacing_m"]))
    v = max(0.5, float(p["vertical_spacing_m"]))
    cs = max(1.0, float(p["circuit_spacing_m"]))
    offs = bundle_offsets(int(p["bundle_n"]), float(p["bundle_spacing_m"]))
    i_a, v_kv = float(p["current_a"]), float(p["voltage_kv"])

    def cond(x, y, phase, circuit=1):
        return Conductor(x=x, y_base=max(1.0, y), phase=phase, circuit=circuit, current_A=i_a,
                         voltage_kV=v_kv, bundle_offsets=list(offs))

    if layout == "horizontal":
        conds = [cond(-s, h, "A"), cond(0.0, h, "B"), cond(s, h, "C")]
        desc = "Custom horizontal single circuit"
    elif layout == "delta":
        conds = [cond(-s, h - v, "A"), cond(0.0, h, "B"), cond(s, h - v, "C")]
        desc = "Custom delta single circuit"
    elif layout == "vertical":
        conds = [cond(0.0, h, "A"), cond(0.0, h - v, "B"), cond(0.0, h - 2 * v, "C")]
        desc = "Custom vertical single circuit"
    else:
        conds = [cond(-cs / 2, h, "A", 1), cond(-cs / 2, h - v, "B", 1), cond(-cs / 2, h - 2 * v, "C", 1),
                 cond(cs / 2, h, "A", 2), cond(cs / 2, h - v, "B", 2), cond(cs / 2, h - 2 * v, "C", 2)]
        desc = "Custom vertical double circuit"
    n = max(1, int(p["bundle_n"]))
    return {
        "description": f"{desc}, {n}-conductor bundle" if n > 1 else f"{desc}, single conductor",
        "conductor_radius_m": max(1e-4, float(p["radius_mm"]) / 1000.0),
        "row_width_m": float(p["row_width_m"]),
        "design_sag_m": sag,
        "conductors": conds,
        "custom": True,
        "layout": layout,
        "tower": "monopole" if p.get("tower_style") == "monopole" else "lattice",
    }


def tower_presets() -> Dict[str, dict]:
    """
    Built-in presets: the three of the original Taki (unchanged) plus a
    quadruple-circuit tower with two voltage levels. Each gets a design sag.
    """
    presets = physics.get_tower_presets()
    presets[QUAD_PRESET] = _quad_preset()
    for p in presets.values():
        p.setdefault("design_sag_m", DEFAULT_DESIGN_SAG_M)
    return presets


def _quad_preset() -> dict:
    """
    275 kV double circuit above a 132 kV double circuit on one lattice tower.
    Conductor positions and currents are those published by Fikry et al. (2022,
    F1000Research 10:1136, Table 2), used here as mid-span heights. The source
    gives no conductor size, so the bundling is an assumption (twin bundle at
    275 kV, single conductor at 132 kV), which matters for the electric field only.
    """
    twin = [(-0.2, 0.0), (0.2, 0.0)]
    upper = (43.13, 37.58, 32.03)
    lower = (24.31, 20.43, 16.55)
    conds = []
    for circuit, x, heights, amps, kv, bundle in (
            (1, -6.0, upper, 1232.0, 275.0, twin), (2, 6.0, upper, 1232.0, 275.0, twin),
            (3, -5.2, lower, 729.0, 132.0, []), (4, 5.2, lower, 729.0, 132.0, [])):
        for phase, y in zip("ABC", heights):
            conds.append(Conductor(x=x, y_base=y, phase=phase, circuit=circuit, current_A=amps,
                                   voltage_kV=kv, bundle_offsets=list(bundle)))
    return {
        "description": "Quadruple circuit lattice tower: two 275 kV circuits above two 132 kV "
                       "circuits, vertical phases. Geometry and currents after Fikry et al. (2022); "
                       "bundling assumed. Set each circuit separately to change it.",
        "conductor_radius_m": 0.0143,
        "row_width_m": 40.0,
        "conductors": conds,
        # the low-reactance arrangement of the source reverses the upper right and lower left circuits
        "swap_circuits": (2, 3),
        "tower": "lattice",
    }


def tower_of(cfg: dict, presets: Optional[Dict[str, dict]] = None) -> Optional[dict]:
    """The tower (built-in preset or custom geometry) a line definition refers to, or None."""
    name = cfg.get("preset") or cfg.get("preset_name")
    if name == CUSTOM:
        return custom_preset(cfg.get("custom"))
    return (presets if presets is not None else tower_presets()).get(name)


def circuit_ids(conductors: List[Conductor]) -> List[int]:
    return sorted({int(c.circuit) for c in conductors})


def circuit_labels(conductors: List[Conductor]) -> Dict[int, str]:
    """A short name for each circuit from where it sits on the tower: "left", "upper right"..."""
    ids = circuit_ids(conductors)
    if len(ids) < 2:
        return {i: "" for i in ids}
    xs = {i: float(np.mean([c.x for c in conductors if c.circuit == i])) for i in ids}
    ys = {i: float(np.mean([c.y_base for c in conductors if c.circuit == i])) for i in ids}
    xc = float(np.mean(list(xs.values())))
    levels = len({round(v, 1) for v in ys.values()}) > 1 and len(ids) > 2
    ymid = (max(ys.values()) + min(ys.values())) / 2.0
    out = {}
    for i in ids:
        side = "left" if xs[i] < xc - 1e-6 else "right" if xs[i] > xc + 1e-6 else "centre"
        out[i] = (("upper " if ys[i] >= ymid else "lower ") if levels else "") + side
    return out


def preset_circuits(preset: dict) -> List[dict]:
    """What each circuit of a preset carries before any override (for the UI)."""
    conds = preset["conductors"]
    labels = circuit_labels(conds)
    out = []
    for i in circuit_ids(conds):
        first = next(c for c in conds if c.circuit == i)
        out.append({"id": i, "label": labels[i], "voltage_kv": float(first.voltage_kV),
                    "current_a": float(first.current_A)})
    return out


def default_line(preset_name: Optional[str] = None, index: int = 0, count: int = 1) -> dict:
    names = list(tower_presets().keys())
    return {
        "name": f"Line {index + 1}",
        "preset": preset_name or names[0],
        "custom": dict(DEFAULT_CUSTOM),
        "x_offset": float(int((index - (count - 1) / 2.0) * 30)),
        "load_pct": 100.0,
        "arrangement": "ABC-CBA",
        "phase_offset_deg": 0.0,
        "current_a": 0.0,       # 0 = use the preset / custom value
        "voltage_kv": 0.0,
        "height_adjust_m": 0.0,  # raise (+) or lower (-) every conductor: taller or shorter towers
        "circuits": [],          # [] = every circuit uses the values above; else one entry per circuit
    }


def default_circuit(load_pct: float = 100.0, phase_order: str = "ABC") -> dict:
    """One entry of a line's "circuits" list. 0 = use the line's (or the tower's) value."""
    return {"on": True, "voltage_kv": 0.0, "current_a": 0.0, "load_pct": float(load_pct),
            "phase_order": phase_order if phase_order in PHASE_ORDERS else "ABC"}


def clean_circuits(raw, n_circuits: int, load_pct: float = 100.0,
                   orders: Optional[List[str]] = None) -> List[dict]:
    """
    Sanitise a "circuits" list for a tower with `n_circuits` circuits. Returns []
    when the tower has one circuit or nothing usable was given (= same settings
    for every circuit).
    """
    if n_circuits < 2 or not isinstance(raw, list) or not raw:
        return []
    orders = orders or ["ABC"] * n_circuits
    out = []
    for k in range(n_circuits):
        d = raw[k] if k < len(raw) and isinstance(raw[k], dict) else {}
        base = default_circuit(load_pct, orders[k] if k < len(orders) else "ABC")

        def num(key, lo, hi):
            try:
                v = float(d.get(key, base[key]))
            except (TypeError, ValueError):
                v = float(base[key])
            return min(hi, max(lo, v)) if math.isfinite(v) else float(base[key])

        out.append({"on": bool(d.get("on", True)), "voltage_kv": num("voltage_kv", 0.0, 1500.0),
                    "current_a": num("current_a", 0.0, 20000.0), "load_pct": num("load_pct", 0.0, 200.0),
                    "phase_order": d.get("phase_order") if d.get("phase_order") in PHASE_ORDERS
                    else base["phase_order"]})
    return out


def arrangement_orders(ids: List[int], arrangement: str, swap: Optional[Tuple[int, ...]] = None) -> Dict[int, str]:
    """Phase order of each circuit for a line-level arrangement ("ABC-ABC" or "ABC-CBA")."""
    if swap is None:
        swap = tuple(i for i in ids if i % 2 == 0)
    return {i: ("CBA" if (arrangement == "ABC-CBA" and i in swap) else "ABC") for i in ids}


def indicative_ground_clearance_m(voltage_kv: float) -> float:
    """
    An indicative minimum height of a live conductor above ground: 5.6 m plus
    10 mm for each kV to earth above 22 kV (the rule of the US National
    Electrical Safety Code for conductors over roads). National and utility
    standards differ by a metre or so either way; the line owner's governs.
    """
    return 5.6 + 0.010 * max(0.0, float(voltage_kv) / math.sqrt(3.0) - 22.0)


@dataclass
class Circuit:
    """One three-phase circuit of a line, as resolved."""
    id: int
    label: str                 # "left", "upper right", ... ("" on a single-circuit tower)
    on: bool                   # False = out of service: de-energised and earthed
    voltage_kv: float          # nominal line-to-line voltage (kept when the circuit is off)
    rated_current_a: float
    load_pct: float
    operating_current_a: float  # 0 when the circuit is off
    thermal_sag_m: float
    phase_order: str           # "ABC" as built, or "CBA" reversed


@dataclass
class Line:
    """One resolved transmission line: conductors at mid-span plus tower metadata."""
    name: str
    preset_name: str
    description: str
    conductors: List[Conductor]             # y_sagged = mid-span height under load
    attach_heights: List[float]             # per conductor, at the tower
    tower: str                              # "lattice" | "monopole"
    x_offset: float
    load_pct: float
    rated_current_a: float
    operating_current_a: float
    voltage_kv: float
    arrangement: str
    phase_offset_deg: float
    thermal_sag_m: float
    design_sag_m: float
    is_double: bool
    radius_m: float
    row_width_m: float
    circuits: List[Circuit] = field(default_factory=list)
    separate: bool = False                  # circuits were set one by one
    energised: List[bool] = field(default_factory=list)   # per conductor
    sag_scale: float = 1.0

    @property
    def x_centre(self) -> float:
        xs = [c.x for c in self.conductors]
        return float(sum(xs) / len(xs)) if xs else self.x_offset

    @property
    def min_height_m(self) -> float:
        """Lowest point of any sub-conductor at mid-span, under load."""
        low = [c.y_sagged + min([o[1] for o in (c.bundle_offsets or [])] + [0.0]) for c in self.conductors]
        return float(min(low)) if low else 0.0

    @property
    def required_clearance_m(self) -> float:
        return indicative_ground_clearance_m(max([k.voltage_kv for k in self.circuits] or [self.voltage_kv]))

    def at_z(self, z: float, half_span: float) -> List[Conductor]:
        """Conductor set at position z along the span (parabolic sag profile)."""
        if half_span <= 0 or z == 0:
            return self.conductors
        u = min(1.0, abs(z) / half_span)
        out = []
        for c, ya in zip(self.conductors, self.attach_heights):
            n = copy.copy(c)
            n.bundle_offsets = list(c.bundle_offsets)
            n.y_sagged = c.y_sagged + (ya - c.y_sagged) * u * u
            out.append(n)
        return out


class LineError(ValueError):
    pass


def build_line(cfg: dict, max_thermal_sag_m: float = 1.5, index: int = 0,
               presets: Optional[Dict[str, dict]] = None, sag_scale: float = 1.0) -> Line:
    """Resolve one line definition. Raises LineError for an unknown preset."""
    presets = presets if presets is not None else tower_presets()
    name = cfg.get("preset") or cfg.get("preset_name")
    if name == CUSTOM:
        preset = custom_preset(cfg.get("custom"))
    elif name in presets:
        preset = presets[name]
    else:
        raise LineError(f"Unknown tower preset '{name}'.")

    conds = copy.deepcopy(preset["conductors"])
    radius = float(preset.get("conductor_radius_m", 0.015))
    load = max(0.0, float(cfg.get("load_pct", cfg.get("load", 100.0))))
    i_over = float(cfg.get("current_a", cfg.get("current_override", 0)) or 0)
    v_over = float(cfg.get("voltage_kv", cfg.get("voltage_override", 0)) or 0)
    adjust = float(cfg.get("height_adjust_m", 0.0) or 0.0)
    if adjust:
        lowest = min(c.y_base for c in conds)
        adjust = max(adjust, 4.0 - lowest)             # keep the lowest conductor at least 4 m up
        for c in conds:
            c.y_base = c.y_base + adjust
    k_sag = max(0.0, float(sag_scale))
    design_ref = float(preset.get("design_sag_m", DEFAULT_DESIGN_SAG_M))
    design_sag = design_ref * k_sag
    phase_off = float(cfg.get("phase_offset_deg", cfg.get("phase_offset", 0.0)) or 0.0)

    ids = circuit_ids(conds)
    labels = circuit_labels(conds)
    is_double = len(ids) > 1
    arrangement = cfg.get("arrangement", "ABC-CBA") if is_double else "ABC-ABC"
    if arrangement not in ("ABC-ABC", "ABC-CBA"):
        arrangement = "ABC-CBA"
    orders = arrangement_orders(ids, arrangement, preset.get("swap_circuits"))
    specs = clean_circuits(cfg.get("circuits"), len(ids), load, [orders[i] for i in ids])
    separate = bool(specs)

    circuits: List[Circuit] = []
    for k, cid in enumerate(ids):
        first = next(c for c in conds if c.circuit == cid)
        spec = specs[k] if separate else None
        rated = float(first.current_A)
        volts = float(first.voltage_kV)
        if i_over > 0:
            rated = i_over
        if v_over > 0:
            volts = v_over
        c_load, on, order = load, True, orders[cid]
        if spec is not None:
            if spec["current_a"] > 0:
                rated = spec["current_a"]
            if spec["voltage_kv"] > 0:
                volts = spec["voltage_kv"]
            c_load, on, order = spec["load_pct"], spec["on"], spec["phase_order"]
        eff_load = c_load if on else 0.0
        circuits.append(Circuit(
            id=cid, label=labels[cid], on=on, voltage_kv=volts, rated_current_a=rated, load_pct=c_load,
            operating_current_a=rated * eff_load / 100.0, phase_order=order,
            thermal_sag_m=physics.compute_sag_offset(eff_load, max_thermal_sag_m) * k_sag))
    by_id = {k.id: k for k in circuits}

    out: List[Conductor] = []
    attach: List[float] = []
    energised: List[bool] = []
    x_off = float(cfg.get("x_offset", 0.0) or 0.0)
    for c in conds:
        k = by_id[int(c.circuit)]
        ya = c.y_base + design_ref                     # at the tower: does not move with the span
        y_noload = c.y_base if k_sag == 1.0 else ya - design_sag
        n = Conductor(x=c.x + x_off, y_base=y_noload, phase=_REVERSE[c.phase] if k.phase_order == "CBA" else c.phase,
                      circuit=c.circuit, current_A=k.operating_current_a, voltage_kV=k.voltage_kv if k.on else 0.0,
                      bundle_offsets=list(c.bundle_offsets), radius_m=radius, phase_offset_deg=phase_off)
        n.y_sagged = max(y_noload - k.thermal_sag_m, 0.5)   # never let it reach the ground
        out.append(n)
        attach.append(max(ya, n.y_sagged + 0.5))
        energised.append(bool(k.on))

    live = [k for k in circuits if k.on] or circuits
    top = max(live, key=lambda k: k.operating_current_a)
    return Line(
        name=str(cfg.get("name") or f"Line {index + 1}"),
        preset_name="Custom geometry" if name == CUSTOM else name,
        description=preset.get("description", ""),
        conductors=out, attach_heights=attach,
        tower=preset.get("tower") or ("lattice" if is_double or "Lattice" in str(name)
                                      or "Quadruple" in str(name) else "monopole"),
        x_offset=x_off, load_pct=top.load_pct if separate else load,
        rated_current_a=top.rated_current_a, operating_current_a=top.operating_current_a,
        voltage_kv=max(k.voltage_kv for k in live), arrangement=arrangement,
        phase_offset_deg=phase_off,
        thermal_sag_m=max(k.thermal_sag_m for k in circuits),
        design_sag_m=design_sag, is_double=is_double, radius_m=radius,
        row_width_m=float(preset.get("row_width_m", 30.0)),
        circuits=circuits, separate=separate, energised=energised, sag_scale=k_sag,
    )


def sag_scale_for(span_m: float, follows_span: bool) -> float:
    """(span / 300 m)^2 when the sag follows the span, else 1."""
    if not follows_span:
        return 1.0
    return (max(1.0, float(span_m)) / REFERENCE_SPAN_M) ** 2


def spacing_threshold_m(voltage_kv: float) -> float:
    """Closer than this, two conductors of different lines are implausibly near each other."""
    return 0.5 + 0.009 * float(voltage_kv)


def spacing_warnings(lines: List[Line]) -> List[str]:
    """
    Warn when conductors of two lines sit implausibly close. Uses the true
    conductor-to-conductor distance in the cross-section at mid-span, so lines
    at different heights are not flagged just because one is above the other.
    """
    out = []
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            best = None
            for a in lines[i].conductors:
                for b in lines[j].conductors:
                    d = math.hypot(a.x - b.x, a.y_sagged - b.y_sagged)
                    if best is None or d < best:
                        best = d
            if best is None:
                continue
            need = spacing_threshold_m(max(lines[i].voltage_kv, lines[j].voltage_kv))
            if best < 0.05:
                out.append(f"{lines[i].name} and {lines[j].name} have conductors in the same place. "
                           "Move one of them: change its centreline offset or its height.")
            elif best < need:
                out.append(f"{lines[i].name} and {lines[j].name} come within {best:.1f} m of each other "
                           f"(conductor to conductor, at mid-span). At this voltage that is closer than "
                           f"conductors are normally run (about {need:.1f} m or more): check the centreline "
                           "offsets and heights.")
    return out


def clearance_warnings(lines: List[Line]) -> List[str]:
    """Warn when a line hangs lower at mid-span than an indicative ground clearance."""
    out = []
    for ln in lines:
        low, need = ln.min_height_m, ln.required_clearance_m
        if low < need - 1e-9:
            kv = max([k.voltage_kv for k in ln.circuits] or [ln.voltage_kv])
            out.append(f"{ln.name} hangs {low:.1f} m above ground at mid-span. An indicative minimum for "
                       f"{kv:g} kV is {need:.1f} m: raise the conductors, shorten the span or reduce the sag.")
    return out
