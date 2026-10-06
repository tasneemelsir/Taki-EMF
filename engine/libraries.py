"""
libraries.py
============
Reference libraries brought over from the Figma prototype: nominal voltage
classes with indicative currents, soil resistivity classes, and loading
context. Values are indicative engineering figures - override them with
project data where it exists.
"""

from collections import namedtuple

VoltageClass = namedtuple("VoltageClass", "kv label current_a radius_m bundle region")

# Nominal system voltages (IEC 60038 / ANSI C84.1) with indicative per-phase thermal
# current ratings. Malaysian (TNB) classes: 11/33 kV distribution, 66/132 kV
# sub-transmission, 275 kV transmission, 500 kV grid.
VOLTAGE_CLASSES = [
    VoltageClass(11,   "11 kV (TNB distribution)",       400,  0.0080, 1, "Malaysia (TNB)"),
    VoltageClass(33,   "33 kV (TNB distribution)",       600,  0.0093, 1, "Malaysia (TNB)"),
    VoltageClass(66,   "66 kV (sub-transmission)",       600,  0.0105, 1, "Malaysia (TNB) / IEC"),
    VoltageClass(110,  "110 kV",                         700,  0.0117, 1, "IEC"),
    VoltageClass(132,  "132 kV (TNB sub-transmission)",  800,  0.0126, 1, "Malaysia (TNB) / IEC/UK"),
    VoltageClass(138,  "138 kV",                         800,  0.0126, 1, "ANSI"),
    VoltageClass(220,  "220 kV",                         1200, 0.0153, 2, "IEC"),
    VoltageClass(230,  "230 kV",                         1200, 0.0159, 2, "ANSI"),
    VoltageClass(275,  "275 kV (TNB transmission)",      1400, 0.0159, 2, "Malaysia (TNB) / IEC/UK"),
    VoltageClass(330,  "330 kV",                         1600, 0.0234, 2, "IEC/AU"),
    VoltageClass(345,  "345 kV",                         1800, 0.0234, 2, "ANSI"),
    VoltageClass(400,  "400 kV (EHV)",                   2000, 0.0234, 2, "IEC"),
    VoltageClass(500,  "500 kV (TNB grid / EHV)",        2500, 0.0304, 3, "Malaysia (TNB) / IEC/ANSI"),
    VoltageClass(765,  "765 kV (EHV)",                   3000, 0.0304, 4, "ANSI/IEC"),
    VoltageClass(1100, "1100 kV (UHV)",                  4000, 0.0350, 4, "UHV"),
]

CURRENT_PRESETS = [400, 600, 800, 1000, 1200, 1400, 1600, 2000, 2500, 3000, 4000]

SoilType = namedtuple("SoilType", "id name resistivity range")

# Typical geophysical resistivity ranges (IEEE Std 80 style values).
SOIL_TYPES = [
    SoilType("seawater",  "Sea water",               0.2,   "0.1–1"),
    SoilType("swamp",     "Swampy / marshy ground",  30.0,  "10–100"),
    SoilType("clay",      "Wet clay / loam",         50.0,  "20–100"),
    SoilType("farmland",  "Farmland / moist soil",   100.0, "50–150"),
    SoilType("sandyloam", "Sandy loam",              200.0, "100–300"),
    SoilType("sand",      "Wet sand",                500.0, "200–1000"),
    SoilType("gravel",    "Gravel / dry soil",       1000.0, "500–2000"),
    SoilType("rock",      "Rock / dry sand",         3000.0, "1000–5000"),
    SoilType("granite",   "Granite / bedrock",       10000.0, "5000–50000"),
]


def loading_context(pct: float) -> str:
    """Plain-language meaning of a loading percentage (TNB planning context)."""
    if pct <= 40:
        return "light / off-peak"
    if pct <= 75:
        return "TNB normal planning"
    if pct <= 100:
        return "peak / rated"
    return "contingency (N-1)"


# ---------------------------------------------------------------------------
# Buildings: occupancy types (from Taki) merged with the Figma type library
# (default dimensions, roof form and rooftop equipment). The architectural
# model is for the 3-D view; field calculations use the simple footprint.
# ---------------------------------------------------------------------------
BUILDING_TYPES = {
    "Residential": dict(
        floor_h=3.0, glazing=0.42, plant=0, colour="#D3CBC0", roof="pitched",
        width=12, depth=10, height=9, sensitivity="high",
        occupancy="Continuous occupancy - most sensitive",
        notes="Multi-storey dwelling with windows, a door and balconies.",
        rooftop=["Chimney"]),
    "Office block": dict(
        floor_h=3.6, glazing=0.62, plant=2, colour="#BFC6CB", roof="flat",
        width=24, depth=20, height=30, sensitivity="medium",
        occupancy="Working-hours occupancy",
        notes="Curtain-wall facade with large glazing and rooftop plant.",
        rooftop=["HVAC", "Antenna"]),
    "School": dict(
        floor_h=3.4, glazing=0.5, plant=1, colour="#D8CFC2", roof="flat",
        width=40, depth=18, height=12, sensitivity="high",
        occupancy="Sensitive receptor - children",
        notes="Long multi-section block with regular window bays.",
        rooftop=["Vents"]),
    "Hospital": dict(
        floor_h=3.6, glazing=0.5, plant=2, colour="#D9DBDA", roof="stepped",
        width=34, depth=26, height=24, sensitivity="high",
        occupancy="Sensitive receptor - patients and equipment",
        notes="Institutional block with a stepped roof, rooftop plant and helipad zone.",
        rooftop=["Plant", "Helipad"]),
    "Data centre": dict(
        floor_h=4.5, glazing=0.25, plant=3, colour="#C8CCCF", roof="flat",
        width=46, depth=34, height=14, sensitivity="equipment",
        occupancy="Industrial / limited occupancy; sensitive equipment",
        notes="Low industrial hall with extensive cooling equipment.",
        rooftop=["Chillers", "Cooling towers", "Louvres"]),
    "Warehouse": dict(
        floor_h=8.0, glazing=0.1, plant=1, colour="#C4C8C6", roof="pitched",
        width=50, depth=40, height=11, sensitivity="low",
        occupancy="Low occupancy",
        notes="Large-span shed with loading doors and a low roof profile.",
        rooftop=["Skylights"]),
}

BUILDING_SHAPES = {
    "box": "Box",
    "lshape": "L-shape",
    "cylinder": "Cylinder",
    "multistory": "Multi-storey (stacked floors)",
}

ROOF_TYPES = {"flat": "Flat", "pitched": "Pitched", "stepped": "Stepped"}

LOADING_PRESETS = [25, 40, 50, 60, 75, 80, 90, 100, 120]


def building_type(name: str) -> dict:
    return BUILDING_TYPES.get(name, BUILDING_TYPES["Warehouse"])
