"""
shield_engine.py
================
Shield configuration, material library, geometry and the two SIMPLIFIED
shielding models (the Figma "Schelkunoff + shadow" model and Taki's original
literature-based percentage model). The physical finite-barrier solvers live in
shield_bem.py; site.py picks one according to `ShieldConfig.model`.

THREE MODELS, WHAT EACH IS
--------------------------
  "physical"    Thin-shell boundary-element solve of the actual barrier
                (shield_bem.py). Magnetic field: eddy currents and flux
                shunting in a finite plate beside the line, so flux that wraps
                round the edges is captured and the field can go UP as well as
                down. Electric field: the barrier as a grounded or floating
                conductor in the line's electrostatic problem. DEFAULT.
  "analytical"  Schelkunoff A + R + B as presented by Ott, applied to every
                point in the barrier's geometric shadow (the Figma model). For
                the magnetic field at 50/60 Hz this is the INFINITE-SHEET
                result: a theoretical upper bound, kept for comparison.
  "empirical"   Taki's original literature-based %-attenuation (shielding.py)
                applied in the shadow. Only for materials that model covers.

Nothing here changes a compliance determination. PASS/FAIL always uses the
unshielded peak field (see standards.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import shielding as _empirical

MU0 = 4e-7 * math.pi
EPS0 = 8.8541878128e-12
SIGMA_CU = 5.8e7  # S/m, annealed copper reference


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Material:
    id: str
    label: str
    category: str
    sigma: float                    # conductivity [S/m]
    mu_r: float                     # relative permeability
    quality: str                    # 'verified' | 'assumed' | 'user'
    applications: str = ""
    mechanisms: str = ""
    limitations: str = ""
    empirical_key: Optional[str] = None   # key into shielding.SHIELDING_MATERIALS
    ref_ids: Tuple[str, ...] = ()
    eps_r: float = 1.0
    typical_thickness_mm: float = 3.0

    @property
    def resistivity(self) -> float:
        return float("inf") if self.sigma <= 0 else 1.0 / self.sigma


def _m(id, label, category, sigma, mu_r, quality, applications, mechanisms, limitations,
       empirical_key=None, ref_ids=(), eps_r=1.0, typical=3.0):
    return Material(id, label, category, sigma, mu_r, quality, applications, mechanisms,
                    limitations, empirical_key, tuple(ref_ids), eps_r, typical)


MATERIALS: Dict[str, Material] = {m.id: m for m in [
    _m("copper", "Copper (annealed)", "Solid metal", 5.8e7, 0.999991, "verified",
       "Reference conductor; enclosures, plates over cables, ground planes.",
       "Eddy-current (induced-current) shielding. Excellent E-field screen when grounded.",
       "Non-magnetic: needs thickness and width comparable to the skin depth (9 mm at 50 Hz) "
       "and to the source distance to do much for a 50/60 Hz magnetic field.",
       ref_ids=("ott2009", "celozzi2008"), typical=3.0),
    _m("aluminium", "Aluminium (1100)", "Solid metal", 3.5e7, 1.000022, "verified",
       "Lightweight plates and enclosures; the usual choice for eddy-current plates.",
       "Eddy-current shielding; non-magnetic. Excellent E-field screen when grounded.",
       "Skin depth 12 mm at 50 Hz, so thin sheet is nearly transparent to B.",
       ref_ids=("ott2009", "celozzi2008"), typical=3.0),
    _m("mildsteel", "Mild steel (low-carbon)", "Ferromagnetic metal", 1.0e7, 200, "assumed",
       "Structural barriers, conduit, enclosures where B-shielding matters.",
       "Flux shunting (high permeability) plus eddy currents; useful at power frequency.",
       "Permeability depends on field strength, grade and annealing; 200 is a nominal "
       "low-field value. Saturation is not modelled.", "steel",
       ref_ids=("ott2009", "celozzi2008"), typical=3.0),
    _m("galvsteel", "Galvanised steel", "Ferromagnetic metal", 1.0e7, 180, "assumed",
       "Fences, corrugated barriers, roofing.",
       "Flux shunting plus eddy currents; zinc layer aids bonding.",
       "Permeability highly variable; seams reduce continuity.", "steel",
       ref_ids=("ott2009",), typical=1.0),
    _m("ss304", "Stainless steel 304", "Metal (austenitic)", 1.45e6, 1.02, "verified",
       "Corrosion-resistant panels and mesh.",
       "Weak eddy-current shielding; essentially non-magnetic when annealed.",
       "Low conductivity and no useful permeability: poor B shield at 50/60 Hz.",
       ref_ids=("ott2009",), typical=2.0),
    _m("mumetal", "Mu-metal (Ni-Fe)", "High-permeability alloy", 1.6e6, 20000, "assumed",
       "Low-frequency magnetic shielding of sensitive equipment.",
       "Very high flux shunting at low field; annealing critical.",
       "Saturates at low flux density and degrades after mechanical stress; cost limits it "
       "to small enclosures, not site barriers.", ref_ids=("ott2009", "celozzi2008"), typical=1.0),
    _m("gosteel", "Grain-oriented electrical steel", "Ferromagnetic metal", 2.1e6, 1500, "assumed",
       "Laminated flux-shunting screens for substations and cable routes.",
       "Flux shunting; low eddy-current contribution.",
       "Strongly anisotropic (rolling direction); the value is a nominal low-field figure.",
       ref_ids=("celozzi2008",), typical=0.35),
    _m("coppermesh", "Copper mesh", "Conductive mesh", 5.8e7, 1.0, "verified",
       "Ventilated barriers, Faraday screens, window screens.",
       "E-field screening when grounded; open area reduces eddy-current shielding.",
       "Magnetic performance is set by the metal fraction, not bulk conductivity.", "mesh",
       ref_ids=("schelkunoff1943", "ott2009"), typical=1.0),
    _m("cfrp", "Carbon-fibre composite (CFRP)", "Carbon composite", 1e4, 1.0, "assumed",
       "Structural panels with E-field screening.",
       "Conductive enough to screen E when grounded; negligible for B.",
       "Conductivity highly anisotropic and formulation-dependent.", typical=4.0),
    _m("cpc", "Conductive polymer composite", "Conductive polymer", 1e2, 1.0, "assumed",
       "Lightweight EMI enclosures, coatings.",
       "Screens E when grounded; transparent to 50/60 Hz B.",
       "Very low conductivity: no power-frequency magnetic shielding.", eps_r=3.0, typical=3.0),
    _m("nicoating", "Nickel conductive coating", "Conductive coating", 1e4, 100.0, "assumed",
       "Sprayed EMI coatings on plastic housings.",
       "Thin-film E-field screening; slight flux shunting.",
       "Films are tens of micrometres: no useful 50/60 Hz magnetic shielding.", typical=0.05),
    # --- Taki's original empirical classes, so nothing from the first app is lost ---
    _m("concrete", "Reinforced concrete wall", "Building material", 1e-2, 1.0, "assumed",
       "Walls and slabs with an embedded rebar grid.",
       "Moist concrete and rebar are conductive enough to screen the E field when earthed.",
       "Transparent to the 50/60 Hz magnetic field. Bulk conductivity varies by orders of "
       "magnitude with moisture; the rebar grid is not modelled separately.", "concrete",
       ref_ids=("who2007",), typical=200.0),
    _m("vegetation", "Vegetation / tree line", "Natural", 1e-2, 1.0, "assumed",
       "Tree lines and hedges.",
       "Living vegetation is earthed and conductive enough to perturb the E field.",
       "No effect on the magnetic field. Treated as a continuous screen, which over-states "
       "sparse foliage; use a coverage below 100 %.", "vegetation",
       ref_ids=("who2007",), typical=1000.0),
]}

MATERIAL_ORDER = ["aluminium", "copper", "mildsteel", "galvsteel", "gosteel", "mumetal", "ss304",
                  "coppermesh", "cfrp", "cpc", "nicoating", "concrete", "vegetation"]

CUSTOM_MATERIAL_ID = "custom"


def material_options() -> Dict[str, str]:
    return {k: MATERIALS[k].label for k in MATERIAL_ORDER}


def get_material(mat_id: str, custom: Optional[dict] = None) -> Material:
    if mat_id == CUSTOM_MATERIAL_ID:
        c = custom or {}
        return Material(
            id=CUSTOM_MATERIAL_ID, label=str(c.get("label") or "Custom material"),
            category="User-defined", sigma=max(0.0, float(c.get("sigma", 1e7) or 0.0)),
            mu_r=max(1e-6, float(c.get("mu_r", 1.0) or 1.0)), quality="user",
            applications="User-supplied properties.", mechanisms="As defined by the user.",
            limitations="Values supplied by the user are not checked against any source.")
    return MATERIALS.get(mat_id, MATERIALS["aluminium"])


# ---------------------------------------------------------------------------
# Presets and configuration
# ---------------------------------------------------------------------------
#: Shield arrangements. The shield normally goes AROUND THE BUILDING being protected
#: ("attached": its position and size follow the building). Measures between the line and
#: the building are the alternative. "wires": made of conductors, not sheet. Order = order shown.
PRESETS: Dict[str, dict] = {
    "enclosure":      {"label": "Around the building - walls and roof", "short": "Walls and roof",
                       "hint": "sheet on both side walls and the roof", "attached": True, "mesh": False},
    "envelope":       {"label": "Around the building - walls, roof and floor", "short": "Complete envelope",
                       "hint": "closed all round, floor included", "attached": True, "mesh": False},
    "walls":          {"label": "Around the building - walls only", "short": "Walls only",
                       "hint": "sheet on the walls, roof left open", "attached": True, "mesh": False},
    "room":           {"label": "Shielded room inside the building", "short": "Shielded room",
                       "hint": "one room lined on all six sides", "attached": True, "mesh": False},
    "surround-wall":  {"label": "Wall around the building", "short": "Perimeter wall",
                       "hint": "conductive wall a short distance off the building", "attached": True, "mesh": False},
    "roof":           {"label": "Shielded roof", "short": "Roof only",
                       "hint": "sheet over the roof", "attached": True, "mesh": False},
    "panel":          {"label": "Shielded facade facing the line", "short": "Facade facing the line",
                       "hint": "sheet on the wall nearest the line", "attached": True, "mesh": False},
    "floor":          {"label": "Shielded floor", "short": "Floor only",
                       "hint": "sheet in the floor slab", "attached": True, "mesh": False},
    "wall-between":   {"label": "Barrier wall between line and building", "short": "Barrier wall",
                       "hint": "free-standing wall along the line", "attached": False, "mesh": False},
    "double-barrier": {"label": "Double barrier wall", "short": "Double barrier wall",
                       "hint": "two walls 4 m apart", "attached": False, "mesh": False},
    "mesh-barrier":   {"label": "Mesh barrier wall", "short": "Mesh barrier wall",
                       "hint": "free-standing conductive mesh", "attached": False, "mesh": True},
    "passive-loop":   {"label": "Passive loop along the line", "short": "Passive loop",
                       "hint": "two bonded conductors strung beside the line", "attached": False, "mesh": False,
                       "wires": True},
    "screen-wires":   {"label": "Earthed screening wires", "short": "Screening wires",
                       "hint": "row of earthed wires; mainly for the electric field", "attached": False,
                       "mesh": False, "wires": True},
    "custom":         {"label": "Custom layout", "short": "Custom layout",
                       "hint": "plates you place yourself, anywhere in the section", "attached": False,
                       "mesh": False, "custom": True},
}
MAX_CUSTOM_PLATES = 16
#: Studies of each arrangement (ids in references.LIBRARY), shown beside the result.
_SHELL_REFS = ["hasselgren1995", "krahenbuhl1993", "celozzi2008", "cigre373"]
_SHEET_REFS = ["hasselgren1995", "cigre373", "ott2009"]
PRESET_REFS: Dict[str, List[str]] = {
    "enclosure": _SHELL_REFS, "envelope": _SHELL_REFS, "room": _SHELL_REFS, "walls": _SHEET_REFS,
    "surround-wall": _SHEET_REFS, "roof": _SHEET_REFS, "panel": _SHEET_REFS, "floor": _SHEET_REFS,
    "wall-between": _SHEET_REFS, "double-barrier": _SHEET_REFS,
    "mesh-barrier": ["celozzi2008", "ott2009", "cigre373"],
    "passive-loop": ["memari1996", "pettersson1996", "walling1993", "yamazaki2000", "cruz2002", "bravo2019",
                     "cigre373"],
    "screen-wires": ["epri-redbook", "cigre373"],
    "custom": _SHEET_REFS,
}
for _k, _p in PRESETS.items():
    _p.setdefault("wires", False)
    _p.setdefault("custom", False)
    _p["refs"] = PRESET_REFS.get(_k, [])
DEFAULT_PRESET = "enclosure"
#: Presets that close round the protected space in plan, so the 3-D view draws their end walls too.
SURROUNDING = ("enclosure", "envelope", "walls", "surround-wall", "room")
WIRE_PRESETS = tuple(k for k, v in PRESETS.items() if v["wires"])

SIDES = {"right": "Right of the line (+x)", "left": "Left of the line (-x)", "both": "Both sides"}

MODELS = {
    "physical": "Physical (finite-barrier solver)",
    "analytical": "Analytical (Schelkunoff A + R + B, infinite sheet)",
    "empirical": "Empirical (Taki literature %)",
}
# Older scenario files call this "basis".
BASES = {k: MODELS[k] for k in ("analytical", "empirical")}

FLOATING_GAP_M = 0.10      # an unearthed barrier stands on insulation this far above the soil
FLOOR_M = 0.20             # height of a floor sheet above the ground
PANEL_M = 2.5              # nominal panel size when a barrier is built from separate panels
SEAM_M = 0.005             # unbonded seam width


@dataclass
class ShieldConfig:
    enabled: bool = False
    preset: str = "wall-between"
    material_id: str = "aluminium"
    model: str = "physical"
    thickness_m: float = 0.003
    layers: int = 1
    layer_spacing_m: float = 0.10
    coverage_pct: float = 100.0
    mesh: bool = False
    aperture_m: float = 0.005       # mesh hole size
    mesh_pitch_m: float = 0.010     # mesh hole spacing
    grounded: bool = True
    continuous: bool = True         # seams bonded / welded
    distance_m: float = 20.0        # barrier distance from the line centreline
    height_m: float = 10.0
    length_m: float = 60.0          # extent along the line (z)
    side: str = "right"
    target_building: int = 0        # for attached presets
    standoff_m: float = 2.0         # perimeter wall: gap between wall and building
    # sheets round the building can stand off it instead of being fixed to its surfaces
    gap_m: float = 0.0              # walls / facade: gap between sheet and wall (roof-only: overhang)
    roof_gap_m: float = 0.0         # roof sheet: height above the roof
    floor_level_m: float = 0.2      # floor-only: height of the shielded floor above ground
    # custom layout: plates placed by the user, (x1, y1, x2, y2) in the cross-section
    custom_plates: Tuple[Tuple[float, float, float, float], ...] = ()
    # free-standing barriers, conductors and custom layouts: centre along the line (0 = mid-span).
    # Sheets fixed round a building follow the building instead.
    z_center_m: float = 0.0
    # shielded room (inside the target building)
    room_width_m: float = 8.0       # across the line (x)
    room_height_m: float = 3.2
    room_depth_m: float = 6.0       # along the line (z)
    room_offset_m: float = 2.0      # from the wall that faces the line
    room_floor_m: float = 0.2       # floor level above ground
    # conductors: passive loops and screening wires
    loop_spacing_m: float = 6.0     # distance between the two conductors of a loop
    loop_vertical: bool = True      # one conductor above the other (else side by side)
    loop_compensation_pct: float = 0.0   # series capacitor: share of the loop reactance cancelled
    wire_mm2: float = 400.0         # conductor cross-section
    wire_count: int = 5             # screening wires in the row
    screen_width_m: float = 20.0    # width of the row
    # two-material construction: the 2nd, 4th ... layer uses this material
    layer2_material_id: Optional[str] = None
    emp_b_pct: Optional[float] = None
    emp_e_pct: Optional[float] = None
    custom_material: Optional[dict] = None

    # ``basis`` is the pre-v4 name for ``model``.
    @property
    def basis(self) -> str:
        return self.model

    @property
    def is_mesh(self) -> bool:
        return bool(self.mesh or PRESETS.get(self.preset, {}).get("mesh", False))

    @property
    def material(self) -> Material:
        return get_material(self.material_id, self.custom_material)

    @property
    def is_wire(self) -> bool:
        return bool(PRESETS.get(self.preset, {}).get("wires", False))

    @property
    def is_custom(self) -> bool:
        return bool(PRESETS.get(self.preset, {}).get("custom", False))

    @property
    def wire_radius_m(self) -> float:
        return math.sqrt(max(self.wire_mm2, 1.0) * 1e-6 / math.pi)

    @property
    def layer2_material(self) -> Optional[Material]:
        if not self.layer2_material_id or self.layer2_material_id == self.material_id or self.layers < 2:
            return None
        return get_material(self.layer2_material_id, self.custom_material)

    @property
    def fill_factor(self) -> float:
        """Metal fraction of a mesh along the current direction (1 for solid sheet)."""
        if not self.is_mesh or self.mesh_pitch_m <= 0:
            return 1.0
        return float(min(1.0, max(0.02, 1.0 - self.aperture_m / self.mesh_pitch_m)))

    def key(self) -> tuple:
        cm = tuple(sorted((self.custom_material or {}).items())) if self.custom_material else ()
        return (self.enabled, self.preset, self.material_id, self.model, round(self.thickness_m, 7),
                self.layers, round(self.layer_spacing_m, 4), round(self.coverage_pct, 3),
                self.is_mesh, round(self.aperture_m, 6), round(self.mesh_pitch_m, 6),
                self.grounded, self.continuous, round(self.distance_m, 4),
                round(self.height_m, 4), round(self.length_m, 4), self.side,
                self.target_building, round(self.standoff_m, 3), self.emp_b_pct, self.emp_e_pct, cm,
                round(self.room_width_m, 3), round(self.room_height_m, 3), round(self.room_depth_m, 3),
                round(self.room_offset_m, 3), round(self.room_floor_m, 3), round(self.loop_spacing_m, 3),
                self.loop_vertical, round(self.loop_compensation_pct, 3), round(self.wire_mm2, 3),
                self.wire_count, round(self.screen_width_m, 3), self.layer2_material_id,
                round(self.gap_m, 3), round(self.roof_gap_m, 3), round(self.floor_level_m, 3),
                self.custom_plates, round(self.z_center_m, 3))


def config_from_dict(d: Optional[dict]) -> ShieldConfig:
    """Build a ShieldConfig from the project JSON ('shield' block). Tolerant of old names."""
    d = dict(d or {})
    model = d.get("model") or d.get("basis") or "physical"
    if model not in MODELS:
        model = "physical"
    preset = d.get("preset", "wall-between")      # files from before v4 had no other default
    if preset not in PRESETS:
        preset = DEFAULT_PRESET

    def num(key, default, lo=None, hi=None):
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

    def opt(key):
        v = d.get(key)
        try:
            return None if v is None else float(v)
        except (TypeError, ValueError):
            return None

    plates = []
    for seg in (d.get("custom_plates") or [])[:MAX_CUSTOM_PLATES]:
        try:
            x1, y1, x2, y2 = (float(v) for v in seg)
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
            continue
        x1, x2 = max(-500.0, min(500.0, x1)), max(-500.0, min(500.0, x2))
        y1, y2 = max(0.0, min(200.0, y1)), max(0.0, min(200.0, y2))
        plates.append((round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3)))

    return ShieldConfig(
        enabled=bool(d.get("enabled", False)), preset=preset,
        material_id=str(d.get("material_id", "aluminium")), model=model,
        thickness_m=num("thickness_mm", 3.0, 0.001, 2000.0) / 1000.0,
        layers=int(num("layers", 1, 1, 4)),
        layer_spacing_m=num("layer_spacing_m", 0.10, 0.01, 5.0),
        coverage_pct=num("coverage_pct", 100.0, 10.0, 100.0),
        mesh=bool(d.get("mesh", False)),
        aperture_m=num("aperture_mm", 5.0, 0.1, 500.0) / 1000.0,
        mesh_pitch_m=num("pitch_mm", 10.0, 0.2, 1000.0) / 1000.0,
        grounded=bool(d.get("grounded", True)), continuous=bool(d.get("bonded", d.get("continuous", True))),
        distance_m=num("distance_m", 20.0, 0.0, 500.0), height_m=num("height_m", 10.0, 0.5, 80.0),
        length_m=num("length_m", 60.0, 2.0, 2000.0),
        side=d.get("side", "right") if d.get("side") in SIDES else "right",
        target_building=int(num("target_building", 0, 0, 50)),
        standoff_m=num("standoff_m", 2.0, 0.3, 30.0),
        gap_m=num("gap_m", 0.0, 0.0, 30.0), roof_gap_m=num("roof_gap_m", 0.0, 0.0, 30.0),
        floor_level_m=num("floor_level_m", FLOOR_M, FLOOR_M, 200.0),
        custom_plates=tuple(plates),
        # "custom_z_m" is the name this setting had while only custom layouts used it
        z_center_m=num("z_center_m" if d.get("z_center_m") is not None else "custom_z_m", 0.0, -1000.0, 1000.0),
        room_width_m=num("room_width_m", 8.0, 1.5, 200.0), room_height_m=num("room_height_m", 3.2, 1.8, 60.0),
        room_depth_m=num("room_depth_m", 6.0, 1.5, 400.0), room_offset_m=num("room_offset_m", 2.0, 0.0, 200.0),
        room_floor_m=num("room_floor_m", 0.2, 0.15, 200.0),
        loop_spacing_m=num("loop_spacing_m", 6.0, 0.3, 80.0), loop_vertical=bool(d.get("loop_vertical", True)),
        loop_compensation_pct=num("loop_compensation_pct", 0.0, 0.0, 95.0),
        wire_mm2=num("wire_mm2", 400.0, 10.0, 5000.0), wire_count=int(num("wire_count", 5, 2, 24)),
        screen_width_m=num("screen_width_m", 20.0, 1.0, 300.0),
        layer2_material_id=(str(d["layer2_material_id"]) if d.get("layer2_material_id") in MATERIALS else None),
        emp_b_pct=opt("emp_b_pct"), emp_e_pct=opt("emp_e_pct"),
        custom_material=d.get("custom_material") if isinstance(d.get("custom_material"), dict) else None,
    )


# ---------------------------------------------------------------------------
# Buildings (geometry helpers shared with the twin)
# ---------------------------------------------------------------------------
def building_sign(b: dict) -> float:
    return -1.0 if b.get("side") == "left" else 1.0


def building_x(b: dict) -> Tuple[float, float]:
    """(x_near, x_far): the wall facing the line, and the far wall. Signed."""
    s = building_sign(b)
    near = s * float(b.get("distance", b.get("distance_from_centerline", 25.0)))
    return near, near + s * float(b.get("width", 20.0))


def building_bbox(b: dict):
    """(x_min, x_max, 0, height, z_min, z_max)."""
    near, far = building_x(b)
    z0 = float(b.get("z_offset", 0.0)) - float(b.get("depth", 20.0)) / 2.0
    z1 = float(b.get("z_offset", 0.0)) + float(b.get("depth", 20.0)) / 2.0
    return min(near, far), max(near, far), 0.0, float(b.get("height", 10.0)), z0, z1


def building_probe_point(b: dict) -> Tuple[float, float, float]:
    """
    Receptor point for a building: 1 m inside the wall that faces the line, at
    half height, at the building's centre along the line. (Earlier versions
    sampled exactly ON the facade, which coincides with a shield panel or
    enclosure fixed to that wall, where "inside" and "outside" are not defined.)
    """
    near, _ = building_x(b)
    h = float(b.get("height", 10.0))
    inset = min(1.0, float(b.get("width", 20.0)) / 4.0)
    return near + building_sign(b) * inset, min(h, max(1.5, h * 0.5)), float(b.get("z_offset", 0.0))


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
Wall = Tuple[float, float, float, float]   # x1, y1, x2, y2 in the x-y cross-section


@dataclass
class Plate:
    """One electrically continuous conductor: a polyline in the cross-section."""
    points: List[Tuple[float, float]]
    group: int              # panels in the same group are bonded together
    grounded: bool          # held at earth potential (E-field problem)
    material_id: Optional[str] = None     # None = the shield's main material
    wire_area_m2: float = 0.0             # > 0: this plate stands for a round conductor of that area
    series_l: float = 0.0                 # compensated loop: inductance per metre cancelled by a series capacitor [H/m]

    @property
    def length(self) -> float:
        return float(sum(math.hypot(b[0] - a[0], b[1] - a[1])
                         for a, b in zip(self.points[:-1], self.points[1:])))


@dataclass
class Geometry:
    walls: List[Wall]                 # outline segments, for drawing and the shadow test
    z_center: float
    z_half: float
    source_distance_m: float
    description: str
    plates: List[Plate] = field(default_factory=list)   # what the physical solver meshes
    note: str = ""
    wires: List[Tuple[float, float]] = field(default_factory=list)   # conductor positions (loops, screens)
    zone: Optional[Tuple[float, float, float, float, float, float]] = None   # protected room: x0,x1,y0,y1,z0,z1

    def covers_z(self, z: float) -> bool:
        return bool(self.walls) and abs(z - self.z_center) <= self.z_half + 1e-9


def _outline(cfg: ShieldConfig, buildings: Sequence[dict], source_x: float):
    """Polylines for the preset (one per connected conductor), plus z extent and description."""
    p = PRESETS.get(cfg.preset, PRESETS["wall-between"])
    y0 = 0.0 if cfg.grounded else FLOATING_GAP_M
    lines: List[List[Tuple[float, float]]] = []
    ring = False                       # separate walls joined into one loop out of plane
    if p["attached"]:
        if not buildings:
            return [], 0.0, 0.0, 1.0, "No building to attach the shield to.", False
        b = buildings[min(max(cfg.target_building, 0), len(buildings) - 1)]
        near, far = building_x(b)
        s = building_sign(b)
        h = float(b.get("height", 10.0))
        zc = float(b.get("z_offset", 0.0))
        zh = float(b.get("depth", 20.0)) / 2.0
        name = b.get("name", "the building")
        # Stand-off: the sheet may sit off the walls and above the roof. Towards the line it
        # stops 1 m short of the centreline; along the line it extends past the ends by the same gap.
        gap = min(max(cfg.gap_m, 0.0), max(0.0, abs(near - source_x) - 1.0))
        rise = max(cfg.roof_gap_m, 0.0)
        xn, xf, top = near - gap * s, far + gap * s, h + rise
        off = (f", {gap:g} m off the walls" if gap > 0 else "") + (f", {rise:g} m above the roof" if rise > 0 else "")
        if cfg.preset == "enclosure":
            lines = [[(xn, y0), (xn, top), (xf, top), (xf, y0)]]
            zh += gap
            desc = f"Shield around {name} (walls and roof{off})"
        elif cfg.preset == "envelope":
            yf = FLOOR_M                                # floor sheet, just above the ground
            lines = [[(xn, yf), (xn, top), (xf, top), (xf, yf), (xn, yf)]]
            zh += gap
            desc = f"Shield around {name} (walls, roof and floor{off})"
        elif cfg.preset == "walls":
            # Sheet on the walls, roof open. The two walls seen in the section join round the
            # ends of the building, so they are one circuit (ring).
            lines = [[(xn, y0), (xn, h)], [(xf, y0), (xf, h)]]
            zh += gap
            ring = True
            desc = f"Shield around {name} (walls only" + (f", {gap:g} m off the walls" if gap > 0 else "") + ")"
        elif cfg.preset == "room":
            x0, x1, y0r, y1r, z0r, z1r = room_box(cfg, b)
            lines = [[(x0, y0r), (x0, y1r), (x1, y1r), (x1, y0r), (x0, y0r)]]
            zc, zh = (z0r + z1r) / 2.0, (z1r - z0r) / 2.0
            desc = f"Shielded room in {name}"
        elif cfg.preset == "roof":
            lines = [[(xn, top), (xf, top)]]
            zh += gap
            desc = (f"Shielded roof on {name}" if rise <= 0 else f"Shield canopy {rise:g} m above {name}") \
                + (f", overhanging {gap:g} m" if gap > 0 else "")
        elif cfg.preset == "floor":
            yf = min(max(cfg.floor_level_m, FLOOR_M), max(FLOOR_M, h - 0.5))
            lines = [[(near, yf), (far, yf)]]
            desc = f"Shielded floor in {name}" + (f", {yf:g} m above ground" if yf > FLOOR_M + 1e-6 else "")
        elif cfg.preset == "panel":
            lines = [[(xn, y0), (xn, max(y0 + 0.5, min(cfg.height_m, h)))]]
            desc = f"Shielded facade on {name}, facing the line" + (f", {gap:g} m off the wall" if gap > 0 else "")
        else:                                           # surround-wall
            gap = cfg.standoff_m
            zh += gap
            hh = max(y0 + 0.5, cfg.height_m)
            lines = [[(near - gap * s, y0), (near - gap * s, hh)], [(far + gap * s, y0), (far + gap * s, hh)]]
            ring = True
            desc = f"Wall around {name}"
        dist = max(1.0, abs(near - source_x) - (gap if cfg.preset in ("enclosure", "envelope", "walls", "roof", "panel") else 0.0))
        return lines, zc, zh, dist, desc, ring

    if cfg.is_custom:
        # Plates exactly where the user put them. Bonded plates share one circuit (ring).
        ymin = 0.0 if cfg.grounded else FLOATING_GAP_M
        for x1, y1, x2, y2 in cfg.custom_plates:
            a, c = (x1, max(y1, ymin)), (x2, max(y2, ymin))
            if math.hypot(c[0] - a[0], c[1] - a[1]) >= 0.2:
                lines.append([a, c])
        if not lines:
            return [], cfg.z_center_m, cfg.length_m / 2.0, 1.0, "Custom layout with no plates yet.", False
        dist = max(1.0, min(math.hypot((a[0] + c[0]) / 2.0 - source_x, 0.0) for a, c in lines))
        desc = f"Custom layout ({len(lines)} plate{'s' if len(lines) != 1 else ''})"
        return lines, cfg.z_center_m, cfg.length_m / 2.0, dist, desc, True

    hh = max(y0 + 0.5, cfg.height_m)
    xs = []
    if cfg.side in ("right", "both"):
        xs.append(cfg.distance_m)
    if cfg.side in ("left", "both"):
        xs.append(-cfg.distance_m)
    for sx in xs:
        lines.append([(sx, y0), (sx, hh)])
        if cfg.preset == "double-barrier":
            x2 = sx + math.copysign(4.0, sx)
            lines.append([(x2, y0), (x2, hh)])
    dist = max(1.0, min(abs(x - source_x) for x in xs)) if xs else 1.0
    return lines, cfg.z_center_m, cfg.length_m / 2.0, dist, p["label"], False


def room_box(cfg: ShieldConfig, b: dict):
    """(x0, x1, y0, y1, z0, z1) of the shielded room, kept inside its building."""
    near, far = building_x(b)
    s = building_sign(b)
    width, depth, h = float(b.get("width", 20.0)), float(b.get("depth", 20.0)), float(b.get("height", 10.0))
    rw = min(cfg.room_width_m, max(1.5, width - 0.6))
    off = min(max(cfg.room_offset_m, 0.3), max(0.3, width - rw - 0.3))
    xa = near + s * off
    xb = xa + s * rw
    rh = min(cfg.room_height_m, max(1.8, h - FLOOR_M - 0.2))
    y0 = min(max(cfg.room_floor_m, FLOOR_M), max(FLOOR_M, h - rh - 0.2))
    rd = min(cfg.room_depth_m, max(1.5, depth - 0.6))
    zc = float(b.get("z_offset", 0.0))
    return min(xa, xb), max(xa, xb), y0, y0 + rh, zc - rd / 2.0, zc + rd / 2.0


def _wire_layout(cfg: ShieldConfig, buildings: Sequence[dict], source_x: float):
    """Conductor positions for the wire presets: ([[(x, y), ...] per bonded set], zc, zh, dist, desc)."""
    r = cfg.wire_radius_m
    lo = 4.0 * r + 0.3
    sides = [1.0] if cfg.side == "right" else [-1.0] if cfg.side == "left" else [1.0, -1.0]
    sets = []
    if cfg.preset == "passive-loop":
        d = cfg.loop_spacing_m
        if cfg.distance_m < 0.5:                       # centred under the line: one loop, not two
            sides = sides[:1]
        for sg in sides:
            x = sg * cfg.distance_m
            if cfg.loop_vertical:
                sets.append([(x, max(lo, cfg.height_m)), (x, max(lo, cfg.height_m) + d)])
            else:
                sets.append([(x - d / 2.0, max(lo, cfg.height_m)), (x + d / 2.0, max(lo, cfg.height_m))])
        desc = "Passive loop along the line" + (
            f", {cfg.loop_compensation_pct:.0f}% series-compensated" if cfg.loop_compensation_pct > 0 else "")
    else:                                              # screen-wires
        n = max(2, int(cfg.wire_count))
        for sg in sides:
            xs = [sg * (cfg.distance_m + cfg.screen_width_m * i / (n - 1)) for i in range(n)]
            sets.append([(x, max(lo, cfg.height_m)) for x in xs])
        desc = f"{n} earthed screening wires" if cfg.grounded else f"{n} screening wires (not earthed)"
    dist = max(1.0, min(abs(p[0] - source_x) for st in sets for p in st))
    return sets, cfg.z_center_m, cfg.length_m / 2.0, dist, desc


def _offset_polyline(pts, k, spacing, source_x):
    """k-th extra layer: moved `k*spacing` away from the source (x) or downward (roofs)."""
    if k == 0:
        return list(pts)
    d = k * spacing
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if len(pts) > 2:                                   # enclosure / envelope: inset the whole outline
        closed = len(pts) > 4 and pts[0] == pts[-1]
        xa, xb = pts[0][0], pts[2][0]
        sgn = 1.0 if xb > xa else -1.0
        top = max(ys) - d
        bot = min(ys) + (d if closed else 0.0)
        if abs(xb - xa) <= 2 * d + 0.5 or top <= bot + 0.5:
            return []
        out = [(xa + sgn * d, bot), (xa + sgn * d, top), (xb - sgn * d, top), (xb - sgn * d, bot)]
        return out + [out[0]] if closed else out
    if abs(xs[0] - xs[1]) < 1e-9:                      # vertical wall
        sgn = 1.0 if xs[0] >= source_x else -1.0
        return [(x + sgn * d, y) for x, y in pts]
    if min(ys) - d <= 0.05:                            # horizontal plate too close to the ground
        return []
    return [(x, y - d) for x, y in pts]


def _panelise(pts, cfg: ShieldConfig):
    """Split a polyline into panels with gaps (coverage) or seams (unbonded)."""
    cov = min(100.0, max(1.0, cfg.coverage_pct)) / 100.0
    if cov >= 0.9999 and cfg.continuous:
        return [list(pts)]
    panels = []
    for a, b in zip(pts[:-1], pts[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L <= 1e-9:
            continue
        n = max(1, int(round(L / PANEL_M)))
        gap = (1.0 - cov) * L / n
        if cov >= 0.9999:
            gap = min(SEAM_M, 0.2 * L / n)
        plen = L / n - gap
        tx, ty = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        for i in range(n):
            s0 = i * (plen + gap)
            s1 = s0 + plen
            panels.append([(a[0] + tx * s0, a[1] + ty * s0), (a[0] + tx * s1, a[1] + ty * s1)])
    return panels


def resolve_geometry(cfg: ShieldConfig, buildings: Sequence[dict],
                     source_x: float = 0.0) -> Geometry:
    """Turn a preset + building list into walls (for drawing) and plates (for the solver)."""
    if cfg.is_wire:
        return _wire_geometry(cfg, buildings, source_x)
    outlines, zc, zh, dist, desc, ring = _outline(cfg, buildings, source_x)
    if not outlines:
        return Geometry([], zc, zh, dist, desc)
    zone = None
    if cfg.preset == "room" and buildings:
        zone = room_box(cfg, buildings[min(max(cfg.target_building, 0), len(buildings) - 1)])
    second = cfg.layer2_material

    walls: List[Wall] = []
    plates: List[Plate] = []
    group = 0
    layers = max(1, int(cfg.layers))
    for k in range(layers):
        ring_group = group
        for pts0 in outlines:
            pts = _offset_polyline(pts0, k, cfg.layer_spacing_m, source_x)
            if len(pts) < 2:
                continue
            for a, b in zip(pts[:-1], pts[1:]):
                walls.append((a[0], a[1], b[0], b[1]))
            first = True
            for panel in _panelise(pts, cfg):
                if cfg.continuous:
                    g = ring_group if ring else group
                    grounded = cfg.grounded
                else:
                    g = group
                    group += 1
                    grounded = cfg.grounded and first
                plates.append(Plate(panel, g, grounded,
                                    material_id=second.id if (second is not None and k % 2 == 1) else None))
                first = False
            if cfg.continuous and not ring:
                group += 1
        if ring and cfg.continuous:
            group += 1
    if second is not None:
        desc += f" ({cfg.material.label.split(' (')[0]} + {second.label.split(' (')[0]})"
    return Geometry(walls, zc, zh, dist, desc, plates, zone=zone)


def _wire_geometry(cfg: ShieldConfig, buildings: Sequence[dict], source_x: float) -> Geometry:
    """
    Loops and screens made of round conductors. Each conductor is represented
    for the solver by a narrow strip of width 4r (the strip with the same
    external inductance and capacitance as a cylinder of radius r) carrying the
    conductor's real cross-section. Conductors of one set are bonded together
    at their ends, so their currents sum to zero: that closed path is the loop.
    """
    sets, zc, zh, dist, desc = _wire_layout(cfg, buildings, source_x)
    if not sets:
        return Geometry([], zc, zh, dist, desc)
    r = cfg.wire_radius_m
    half = 2.0 * r
    walls, plates, wires = [], [], []
    group = 0
    for st in sets:
        l_series = 0.0
        if len(st) == 2 and cfg.loop_compensation_pct > 0 and cfg.continuous:
            d = math.hypot(st[0][0] - st[1][0], st[0][1] - st[1][1])
            # share of one leg's inductance (two-wire loop, per metre) cancelled by the series capacitor
            l_series = cfg.loop_compensation_pct / 100.0 * (MU0 / (2.0 * math.pi)) * math.log(max(d, 4 * r) / r)
        for (x, y) in st:
            walls.append((x, y - half, x, y + half))
            wires.append((x, y))
            plates.append(Plate([(x, y - half), (x, y + half)], group, cfg.grounded,
                                wire_area_m2=cfg.wire_mm2 * 1e-6, series_l=l_series))
            if not cfg.continuous:
                group += 1
        if cfg.continuous:
            group += 1
    return Geometry(walls, zc, zh, dist, desc, plates, wires=wires)


# ---------------------------------------------------------------------------
# Simplified models: Schelkunoff / empirical shielding effectiveness
# ---------------------------------------------------------------------------
@dataclass
class SEResult:
    se_e: float
    se_b: float
    skin_depth_m: float
    absorption: float
    reflection_e: float
    reflection_h: float
    multi_refl: float
    ceiling: float
    limited_by_e: str     # 'material' | 'leakage' | 'grounding' | 'empirical' | 'geometry'
    limited_by_b: str
    basis_used: str       # 'physical' | 'analytical' | 'empirical'
    note: str = ""
    # physical model only: where the two headline numbers were read
    ref_point: Optional[Tuple[float, float]] = None


def skin_depth(mat: Material, f_hz: float) -> float:
    if mat.sigma <= 0 or f_hz <= 0:
        return float("inf")
    return math.sqrt(1.0 / (math.pi * f_hz * MU0 * mat.mu_r * mat.sigma))


def leakage_ceiling(cfg: ShieldConfig, mesh: Optional[bool] = None) -> float:
    """Geometry-imposed SE limit [dB] used by the simplified models."""
    mesh = cfg.is_mesh if mesh is None else mesh
    cov = min(99.999, max(0.0, cfg.coverage_pct)) / 100.0
    se = 120.0 if cfg.coverage_pct >= 100.0 else -20.0 * math.log10(1.0 - cov)
    if mesh and cfg.aperture_m > 0 and cfg.mesh_pitch_m > 0:
        open_frac = min(0.95, (cfg.aperture_m / cfg.mesh_pitch_m) ** 2)
        se = min(se, -20.0 * math.log10(max(0.001, open_frac)))
    if not cfg.continuous:
        se = min(se, 20.0)
    return se


def _pct_to_db(pct: float) -> float:
    pct = min(max(pct, 0.0), 99.9)
    return -20.0 * math.log10(1.0 - pct / 100.0)


def compute_se(cfg: ShieldConfig, freq_hz: float, source_distance_m: float,
               model: Optional[str] = None) -> SEResult:
    """
    Shielding effectiveness of the SIMPLIFIED models ('analytical' or
    'empirical'). For cfg.model == 'physical' this returns the analytical
    numbers, which site.py then replaces with values read from the solved field.
    """
    second = cfg.layer2_material
    if second is not None:
        # two materials: add the layers' effectiveness in dB (reflection between layers ignored)
        n2 = cfg.layers // 2
        a = compute_se(with_changes(cfg, layers=cfg.layers - n2, layer2_material_id=None), freq_hz,
                       source_distance_m, model)
        b = compute_se(with_changes(cfg, layers=n2, material_id=second.id, layer2_material_id=None),
                       freq_hz, source_distance_m, model)
        ceil = leakage_ceiling(cfg)
        return SEResult(min(a.se_e + b.se_e, ceil if cfg.grounded else min(ceil, 10.0)),
                        min(a.se_b + b.se_b, ceil), a.skin_depth_m, a.absorption + b.absorption,
                        a.reflection_e, a.reflection_h, a.multi_refl, ceil, a.limited_by_e,
                        a.limited_by_b, a.basis_used, a.note or b.note)
    mat = cfg.material
    ceil = leakage_ceiling(cfg)
    ceil_e = ceil if cfg.grounded else min(ceil, 10.0)
    basis = model or cfg.model
    if basis == "physical":
        basis = "analytical"
    note = ""
    if basis == "empirical" and mat.empirical_key is None:
        basis = "analytical"
        note = (f"{mat.label} has no entry in Taki's literature model; the analytical "
                "model was used instead.")

    if basis == "empirical":
        em = _empirical.get_material(mat.empirical_key)
        b_pct = em.b_reduction_pct if cfg.emp_b_pct is None else cfg.emp_b_pct
        e_pct = em.e_reduction_pct if cfg.emp_e_pct is None else cfg.emp_e_pct
        se_b = min(_pct_to_db(b_pct), ceil)
        se_e = min(_pct_to_db(e_pct), ceil_e)
        return SEResult(se_e, se_b, skin_depth(mat, freq_hz), 0.0, 0.0, 0.0, 0.0, ceil,
                        "empirical", "empirical", "empirical",
                        note or "Literature-based %-attenuation, converted to dB.")

    f = max(float(freq_hz), 1e-6)
    sig_r = max(mat.sigma, 1e-30) / SIGMA_CU
    r = max(0.1, source_distance_m)
    delta = skin_depth(mat, f)
    t_eff = cfg.thickness_m * max(1, cfg.layers)
    A = 0.0 if not math.isfinite(delta) else 8.686 * (t_eff / delta)
    R_E = 322.0 + 10.0 * math.log10(sig_r / (mat.mu_r * f ** 3 * r ** 2))
    R_H = 14.6 + 10.0 * math.log10((f * r ** 2 * sig_r) / mat.mu_r)
    if A < 10 and math.isfinite(delta) and t_eff > 0:
        B = 20.0 * math.log10(max(1e-12, abs(1.0 - math.exp(-2.0 * t_eff / delta))))
    else:
        B = 0.0
    se_e_mat = max(0.0, R_E + A)
    se_b_mat = max(0.0, R_H + A + B)
    se_e = min(se_e_mat, ceil_e)
    se_b = min(se_b_mat, ceil)
    lim_e = "material" if se_e_mat <= ceil_e else ("leakage" if cfg.grounded else "grounding")
    lim_b = "material" if se_b_mat <= ceil else "leakage"
    return SEResult(se_e, se_b, delta, A, max(0.0, R_E), max(0.0, R_H), B, ceil,
                    lim_e, lim_b, "analytical", note)


# ---------------------------------------------------------------------------
# Simplified models: spatial application (geometric shadow)
# ---------------------------------------------------------------------------
def _orient(ax, ay, bx, by, cx, cy):
    return np.sign((bx - ax) * (cy - ay) - (by - ay) * (cx - ax))


def blocked_mask(src: Tuple[float, float], X: np.ndarray, Y: np.ndarray,
                 walls: Sequence[Wall]) -> np.ndarray:
    """True where the straight ray from `src` to (X, Y) crosses any wall."""
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    blocked = np.zeros(X.shape, dtype=bool)
    sx, sy = src
    for (x1, y1, x2, y2) in walls:
        o1 = _orient(sx, sy, X, Y, x1, y1)
        o2 = _orient(sx, sy, X, Y, x2, y2)
        o3 = _orient(x1, y1, x2, y2, sx, sy)
        o4 = _orient(x1, y1, x2, y2, X, Y)
        blocked |= (o1 != o2) & (o3 != o4)
    return blocked


def edge_distance(X: np.ndarray, Y: np.ndarray, walls: Sequence[Wall]) -> np.ndarray:
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    d = np.full(X.shape, np.inf)
    for (x1, y1, x2, y2) in walls:
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy or 1e-9
        t = np.clip(((X - x1) * dx + (Y - y1) * dy) / l2, 0.0, 1.0)
        d = np.minimum(d, np.hypot(X - (x1 + t * dx), Y - (y1 + t * dy)))
    return d


def shield_factors(geom: Geometry, se: SEResult, src: Tuple[float, float],
                   X: np.ndarray, Y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Multiplicative (fE, fB) for the simplified models: attenuate the shadow only."""
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    ones = np.ones(X.shape)
    if not geom.walls:
        return ones, ones.copy()
    blocked = blocked_mask(src, X, Y, geom.walls)
    fE = np.where(blocked, 10 ** (-se.se_e / 20.0), 1.0)
    fB = np.where(blocked, 10 ** (-se.se_b / 20.0), 1.0)
    ed = edge_distance(X, Y, geom.walls)
    near = (~blocked) & (ed < 1.5)
    amp = 1.0 + 0.08 * (1.0 - ed / 1.5)
    fE = np.where(near, amp, fE)
    fB = np.where(near, amp, fB)
    return fE, fB


def corridor_factors(geom: Geometry, se: SEResult, sources: Sequence[Tuple[float, float]],
                     X: np.ndarray, Y: np.ndarray,
                     weights_b: Optional[Sequence[np.ndarray]] = None,
                     weights_e: Optional[Sequence[np.ndarray]] = None
                     ) -> Tuple[np.ndarray, np.ndarray]:
    """
    Multi-circuit shadow model. `sources` are each circuit's (x, y) centroid;
    weights are each circuit's share of the field at every point. A point
    shadowed from only SOME circuits is attenuated only for their share.
    """
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    if len(sources) == 1 or weights_b is None or weights_e is None:
        src = sources[0] if len(sources) == 1 else (
            float(np.mean([s[0] for s in sources])), float(np.mean([s[1] for s in sources])))
        return shield_factors(geom, se, src, X, Y)

    def blend(weights, pick):
        num = np.zeros(X.shape); den = np.zeros(X.shape)
        for s, w in zip(sources, weights):
            f = shield_factors(geom, se, s, X, Y)[pick]
            num += w * f; den += w
        safe = np.where(den > 0, den, 1.0)
        return np.where(den > 0, num / safe, 1.0)

    return blend(weights_e, 0), blend(weights_b, 1)


def required_barrier_height(sources: Sequence[Tuple[float, float]], wall_x: float,
                            receptor: Tuple[float, float]) -> Optional[float]:
    """
    Minimum height [m] of a vertical barrier at x = wall_x so that the straight
    ray from EVERY source to `receptor` is blocked. None if the barrier is not
    between the sources and the receptor. Pure line-of-sight geometry.
    """
    rx, ry = receptor
    need = 0.0
    between = False
    for sx, sy in sources:
        if (wall_x - sx) * (rx - wall_x) <= 0:
            continue
        between = True
        t = (wall_x - sx) / (rx - sx)
        need = max(need, sy + (ry - sy) * t)
    return need if between else None


# ---------------------------------------------------------------------------
# Small helpers used by the UI / reports
# ---------------------------------------------------------------------------
def se_db(f0, fs):
    f0 = float(f0); fs = float(fs)
    return 0.0 if f0 <= 1e-12 else 20.0 * math.log10(f0 / max(1e-12, fs))


def atten_pct(f0, fs):
    f0 = float(f0); fs = float(fs)
    return 0.0 if f0 <= 1e-12 else 100.0 * (1.0 - fs / f0)


def db_to_pct(se_db_value: float) -> float:
    return 100.0 * (1.0 - 10 ** (-se_db_value / 20.0))


def with_changes(cfg: ShieldConfig, **changes) -> ShieldConfig:
    return replace(cfg, **changes)
