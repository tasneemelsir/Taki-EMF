"""
shielding.py
============
Power-frequency (50/60 Hz) EMF shielding-effect model for the "Taki"
EMF Dashboard.

IMPORTANT PHYSICS CONTEXT
--------------------------------------------------------------------
At power frequency (50/60 Hz), electric-field (E) and magnetic-field
(B) shielding behave very differently, and this module treats them
separately:

  * E-field shielding is comparatively EASY: any nearby grounded
    conductive mass (rebar, metal siding, a wire mesh) sits at a
    fixed potential and terminates field lines, so even an
    imperfect/ungrounded conductive grid gives a large reduction.
    This is classical electrostatic (Faraday-cage) shielding and it
    works at any frequency.

  * B-field shielding is comparatively HARD at 50/60 Hz: attenuation
    requires either (a) high magnetic permeability material that
    draws flux through itself (steel, mu-metal - NOT copper or
    aluminium, which are excellent RF shields but nearly transparent
    to 50/60 Hz fields), or (b) a continuous, low-impedance closed
    conductive loop in which the field induces an opposing
    (cancelling) current - the "passive loop" mitigation technique
    used along transmission-line rights-of-way.

This module implements a simplified, literature-grounded EMPIRICAL
attenuation model (a single %-reduction applied to the simulated
field), not a full electromagnetic shielding solve (that would
require a 3D FEM/BEM eddy-current solver). It is intended as an
engineering-education / options-comparison tool, consistent with the
rest of Taki's "engineering-reference estimate" scope - not a
certified shielding-effectiveness calculation.

Sources for the default percentages (see references.py for the full
citation list):
  - Steel vs aluminium / permeability requirement at 50-60 Hz:
    Eagle Magnetic (2026); Snubber.ai engineering explainer (2026).
  - "Metals for EMF Shielding" material comparison: EMF Safe Living.
  - Passive/compensated loop shielding achieving ~60-80% B-field and
    ~20-40% E-field reduction along a transmission ROW:
    US Patent 5,360,998, "Magnetic field minimization in power
    transmission".
  - Reinforced-concrete rebar grids as an incomplete, often-ungrounded
    Faraday shield: general shielding-effectiveness literature on
    rebar/concrete structures (e.g. IEICE ISAP 2014 proceedings;
    "Shielding effectiveness of concrete buildings" studies) -
    those studies are at radio frequencies, so the B-field figure
    here is extrapolated conservatively using the low-frequency
    permeability principle above, not taken directly from them.
  - Vegetation: no established shielding mechanism at power
    frequency (not conductive, not magnetic) - included for
    completeness/comparison, with a near-zero default.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class ShieldingMaterial:
    key: str
    label: str
    icon: str
    e_reduction_pct: float          # default / typical E-field reduction (%)
    e_reduction_range: Tuple[float, float]
    b_reduction_pct: float          # default / typical B-field reduction (%)
    b_reduction_range: Tuple[float, float]
    mechanism: str                  # short "why" explanation
    source_ids: Tuple[str, ...]     # keys into references.REFERENCES


SHIELDING_MATERIALS: Dict[str, ShieldingMaterial] = {
    "none": ShieldingMaterial(
        key="none", label="No Shielding (Unshielded Baseline)", icon="⬜",
        e_reduction_pct=0.0, e_reduction_range=(0.0, 0.0),
        b_reduction_pct=0.0, b_reduction_range=(0.0, 0.0),
        mechanism="Baseline — open-air exposure with no intervening structure.",
        source_ids=(),
    ),
    "concrete": ShieldingMaterial(
        key="concrete", label="Reinforced-Concrete Wall", icon="🧱",
        e_reduction_pct=65.0, e_reduction_range=(40.0, 85.0),
        b_reduction_pct=8.0, b_reduction_range=(3.0, 15.0),
        mechanism=(
            "The embedded rebar grid acts as an incomplete, usually-ungrounded "
            "conductive mesh: it attenuates the E field meaningfully (any nearby "
            "conductive mass does) but its thin steel cross-section and wide "
            "spacing give little eddy-current or permeability benefit at "
            "50/60 Hz, so B-field reduction is minor."
        ),
        source_ids=("rebar_concrete_shielding", "eagle_magnetic_lf_hf"),
    ),
    "steel": ShieldingMaterial(
        key="steel", label="Metal Siding / Structural Steel", icon="🏭",
        e_reduction_pct=96.0, e_reduction_range=(90.0, 99.0),
        b_reduction_pct=45.0, b_reduction_range=(25.0, 65.0),
        mechanism=(
            "A continuous steel envelope is a near-complete Faraday shield for "
            "the E field. Steel's ferromagnetic permeability also gives it "
            "materially better B-field attenuation than aluminium or copper at "
            "50/60 Hz, though a single wall (not a fully closed enclosure) caps "
            "the achievable reduction well below a sealed steel room."
        ),
        source_ids=("steel_vs_aluminum_60hz", "emf_metals_guide"),
    ),
    "mesh": ShieldingMaterial(
        key="mesh", label="Grounded Conductive Mesh (Faraday / Passive Loop)", icon="🕸️",
        e_reduction_pct=30.0, e_reduction_range=(15.0, 40.0),
        b_reduction_pct=70.0, b_reduction_range=(55.0, 80.0),
        mechanism=(
            "A purpose-built, continuous grounded loop (unlike a passive wall) "
            "has the incident 50/60 Hz field induce an opposing current in the "
            "loop, which directly cancels a large share of the magnetic field — "
            "the standard 'passive loop' mitigation technique used along "
            "transmission-line rights-of-way. E-field reduction is more modest "
            "than a solid metal skin because the mesh is open, not continuous."
        ),
        source_ids=("compensated_shielding_patent",),
    ),
    "vegetation": ShieldingMaterial(
        key="vegetation", label="Vegetation / Tree Line", icon="🌳",
        e_reduction_pct=3.0, e_reduction_range=(0.0, 8.0),
        b_reduction_pct=1.0, b_reduction_range=(0.0, 3.0),
        mechanism=(
            "Trees and vegetation are neither electrically conductive at scale "
            "nor magnetically permeable, so there is no established physical "
            "shielding mechanism for power-frequency E or B fields. Included "
            "for completeness/comparison — any perceived benefit is a visual "
            "screen, not a measured field reduction."
        ),
        source_ids=("emf_shielding_overview",),
    ),
}


def get_material(key: str) -> ShieldingMaterial:
    return SHIELDING_MATERIALS.get(key, SHIELDING_MATERIALS["none"])


def material_options() -> Dict[str, str]:
    """{key: 'icon label'} for building selectboxes, in a stable display order."""
    order = ["none", "concrete", "steel", "mesh", "vegetation"]
    return {k: f"{SHIELDING_MATERIALS[k].icon} {SHIELDING_MATERIALS[k].label}" for k in order}


def apply_shielding(b_value_uT: float, e_value_kVm: float, material_key: str,
                     e_pct_override: Optional[float] = None,
                     b_pct_override: Optional[float] = None) -> Tuple[float, float]:
    """
    Apply a material's empirical %-attenuation to an (unshielded) B and E
    field reading, returning the shielded (b, e) pair.

    e_pct_override / b_pct_override let the UI offer a slider within the
    material's documented range instead of always using the default.
    """
    mat = get_material(material_key)
    e_pct = mat.e_reduction_pct if e_pct_override is None else e_pct_override
    b_pct = mat.b_reduction_pct if b_pct_override is None else b_pct_override
    e_pct = min(max(e_pct, 0.0), 100.0)
    b_pct = min(max(b_pct, 0.0), 100.0)
    b_shielded = b_value_uT * (1.0 - b_pct / 100.0)
    e_shielded = e_value_kVm * (1.0 - e_pct / 100.0)
    return b_shielded, e_shielded


def shielding_comparison_row(building_name: str, material_key: str,
                              b_unshielded: float, e_unshielded: float,
                              e_pct_override: Optional[float] = None,
                              b_pct_override: Optional[float] = None) -> dict:
    """
    Build one summary row (for tables / report / AI-prompt context)
    describing a building's field exposure with and without its
    assigned shielding material.
    """
    mat = get_material(material_key)
    b_shielded, e_shielded = apply_shielding(
        b_unshielded, e_unshielded, material_key, e_pct_override, b_pct_override,
    )
    b_pct = mat.b_reduction_pct if b_pct_override is None else b_pct_override
    e_pct = mat.e_reduction_pct if e_pct_override is None else e_pct_override
    return {
        "building": building_name,
        "material": mat.label,
        "material_key": material_key,
        "b_unshielded_uT": b_unshielded,
        "b_shielded_uT": b_shielded,
        "b_reduction_pct": b_pct,
        "e_unshielded_kVm": e_unshielded,
        "e_shielded_kVm": e_shielded,
        "e_reduction_pct": e_pct,
    }
