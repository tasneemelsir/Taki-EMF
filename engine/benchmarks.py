"""
benchmarks.py
=============
Reference-data library for the "Taki" EMF Dashboard.

------------------------------------------------------------------------
WHAT REPLACED WHAT, AND WHY
------------------------------------------------------------------------
Earlier versions of Taki offered "Standard Benchmark" curves built by an
internal helper:

    def gaussian_like(peak, width, offset=0.0): ...

Those were synthetic bell curves with no provenance, presented in the UI
under a label implying authoritative reference data. Validating against
them established nothing: they were not derived from any solver, any
measurement campaign, or any published source. For a tool whose output
feeds research and consultancy deliverables, that is worse than having no
benchmark at all, because it produces a validation figure that looks
meaningful and is not.

This module replaces them with real, cited reference data carrying full
provenance.

------------------------------------------------------------------------
THE DISTINCTION THAT MATTERS MOST
------------------------------------------------------------------------
Reference data comes in two kinds that test completely different things,
and merging them would misrepresent both:

  SIMULATED  -> published output of another numerical solver.
                Comparing Taki against it is CODE-TO-CODE VERIFICATION:
                "does Taki's implementation agree with an established
                tool on identical geometry?"  It says nothing about
                whether the underlying model matches physical reality.

  MEASURED   -> published field-meter readings from a real site.
                Comparing Taki against it is MODEL VALIDATION:
                "does the model reflect what actually happens?"  It is
                confounded by instrument accuracy, unknown loading at
                the time of measurement, ground conditions, and nearby
                sources the model does not include.

  USER       -> the user's own survey data for a specific site.

A tool that reports "validated against N datasets" while quietly mixing
these is making a claim it has not earned. They are kept structurally
separate here, and the UI is expected to keep them visually separate too.

------------------------------------------------------------------------
LICENSING POSTURE
------------------------------------------------------------------------
Only data that is explicitly free to redistribute ships inside Taki. The
bundled Fikry et al. (2022) dataset qualifies: the article is CC-BY 4.0
and the underlying dataset carries a CC0 1.0 public domain dedication.

For paywalled or all-rights-reserved sources, Taki ships the CITATION
ONLY, plus a CSV template the user can populate by digitising the
published figure themselves. Those appear as `Reference` entries with
`data_available = False`. This keeps the library legally clean while
still pointing the user at the right literature.
"""

import csv
import io
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Data-type vocabulary
SIMULATED = "simulated"
MEASURED = "measured"
USER = "user"

DATA_TYPE_LABELS = {
    SIMULATED: "Simulated (code-to-code verification)",
    MEASURED: "Measured (model validation)",
    USER: "User-supplied survey data",
}

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_data")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class ReferencePoint:
    """
    A single published field value.

    `distance_known` exists because some sources report a value at a
    named location ("at the ROW boundary") without stating the distance
    that location corresponds to. Such a point is still meaningful, but
    it CANNOT be placed on a distance axis or compared against a lateral
    profile — so it is carried with distance_m = None and excluded from
    profile comparison rather than silently assigned a guessed distance.
    """
    location: str
    distance_m: Optional[float]
    distance_known: bool
    b_field_uT: Optional[float] = None
    e_field_kVm: Optional[float] = None

    @property
    def comparable(self) -> bool:
        return self.distance_known and self.distance_m is not None


@dataclass
class ReferenceDataset:
    """One published configuration and its reference points."""
    id: str
    label: str
    line_type: str
    conditions: Dict[str, object]
    points: List[ReferencePoint]
    source_id: str = ""

    @property
    def comparable_points(self) -> List[ReferencePoint]:
        return [p for p in self.points if p.comparable]

    @property
    def excluded_points(self) -> List[ReferencePoint]:
        return [p for p in self.points if not p.comparable]


@dataclass
class Reference:
    """One published source document and everything it contributes."""
    id: str
    title: str
    data_type: str
    citation: Dict[str, object]
    method: Dict[str, object] = field(default_factory=dict)
    provenance_notes: List[str] = field(default_factory=list)
    datasets: List[ReferenceDataset] = field(default_factory=list)
    tower_geometries: Dict[str, object] = field(default_factory=dict)
    data_available: bool = True

    @property
    def short_citation(self) -> str:
        c = self.citation
        bits = [str(c.get("authors", "")), f"({c.get('year', 'n.d.')})"]
        if c.get("container"):
            bits.append(str(c["container"]))
        if c.get("volume"):
            vol = str(c["volume"])
            if c.get("article_number"):
                vol += f":{c['article_number']}"
            bits.append(vol)
        return " ".join(b for b in bits if b)

    @property
    def full_citation(self) -> str:
        c = self.citation
        parts = [
            f"{c.get('authors', 'Unknown')}. \"{c.get('title', self.title)}\"",
        ]
        if c.get("version"):
            parts.append(f"[{c['version']}]")
        tail = c.get("container", "")
        if c.get("volume"):
            tail += f" {c['volume']}"
        if c.get("article_number"):
            tail += f":{c['article_number']}"
        if c.get("year"):
            tail += f" ({c['year']})"
        if tail.strip():
            parts.append(tail.strip())
        if c.get("doi"):
            parts.append(f"doi:{c['doi']}")
        return ". ".join(p for p in parts if p) + "."

    @property
    def is_verification(self) -> bool:
        """True when comparing against this is code-to-code verification."""
        return self.data_type == SIMULATED


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _parse_document(doc: dict) -> Reference:
    datasets = []
    for ds in doc.get("datasets", []):
        points = [
            ReferencePoint(
                location=p["location"],
                distance_m=p.get("distance_m"),
                distance_known=bool(p.get("distance_known", p.get("distance_m") is not None)),
                b_field_uT=p.get("b_field_uT"),
                e_field_kVm=p.get("e_field_kVm"),
            )
            for p in ds.get("points", [])
        ]
        conditions = {
            k: v for k, v in ds.items()
            if k not in ("id", "points", "line_type", "line_type_label")
        }
        label_bits = [ds.get("line_type_label", ds.get("line_type", ds["id"]))]
        if ds.get("phasing"):
            label_bits.append(str(ds["phasing"]))
        if "ground_conducting" in ds:
            label_bits.append(
                "conducting ground" if ds["ground_conducting"] else "non-conducting ground"
            )
        datasets.append(ReferenceDataset(
            id=ds["id"],
            label=" — ".join(label_bits),
            line_type=ds.get("line_type", ""),
            conditions=conditions,
            points=points,
            source_id=doc["id"],
        ))

    return Reference(
        id=doc["id"],
        title=doc.get("title", doc["id"]),
        data_type=doc.get("data_type", SIMULATED),
        citation=doc.get("citation", {}),
        method=doc.get("method", {}),
        provenance_notes=doc.get("provenance_notes", []),
        datasets=datasets,
        tower_geometries=doc.get("tower_geometries", {}),
        data_available=doc.get("data_available", True),
    )


def load_references(data_dir: Optional[str] = None) -> Dict[str, Reference]:
    """
    Load every reference document from the benchmark data directory.

    Malformed or unreadable files are skipped rather than raising, so one
    bad file cannot take down the whole Validation tab. Returns a dict
    keyed by reference id.
    """
    directory = data_dir or _DATA_DIR
    out: Dict[str, Reference] = {}
    if not os.path.isdir(directory):
        return out
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
            ref = _parse_document(doc)
            out[ref.id] = ref
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            continue
    return out


def all_datasets(references: Optional[Dict[str, Reference]] = None) -> List[ReferenceDataset]:
    """Flat list of every dataset across every loaded reference."""
    refs = references if references is not None else load_references()
    out = []
    for ref in refs.values():
        out.extend(ref.datasets)
    return out


def datasets_by_type(references: Optional[Dict[str, Reference]] = None
                     ) -> Dict[str, List[ReferenceDataset]]:
    """
    Datasets grouped by data type, so the UI can keep verification and
    validation visually separate rather than presenting one merged list.
    """
    refs = references if references is not None else load_references()
    grouped: Dict[str, List[ReferenceDataset]] = {SIMULATED: [], MEASURED: []}
    for ref in refs.values():
        grouped.setdefault(ref.data_type, []).extend(ref.datasets)
    return grouped


# ---------------------------------------------------------------------------
# Geometry reconstruction
# ---------------------------------------------------------------------------
def build_conductors_from_reference(ref: Reference, line_type: str,
                                    phasing: str = "untransposed") -> Optional[List]:
    """
    Reconstruct the published tower geometry as physics.Conductor objects,
    so Taki can be run on EXACTLY the configuration the source used rather
    than on an approximation of it.

    This is what makes the comparison like-for-like. Without it, any
    disagreement between Taki and the reference is uninterpretable — it
    could be a real implementation difference, or it could just be that
    the two runs used different conductor heights.

    Returns None when the source did not publish geometry for this line
    type, which the caller should surface rather than substituting a
    guess.
    """
    from . import physics

    geom = ref.tower_geometries.get(line_type)
    if not geom or not geom.get("available"):
        return None

    key = "phase_transposed" if phasing == "transposed" else "phase_untransposed"
    conductors = []
    for c in geom["conductors"]:
        raw_phase = str(c[key])
        # Published labels look like "A1"/"b2": letter = phase, digit =
        # circuit, case distinguishes the two voltage levels on quadruple
        # towers. Only the phase letter and circuit number matter here.
        letter = raw_phase[0].upper()
        circuit = int(raw_phase[1]) if len(raw_phase) > 1 and raw_phase[1].isdigit() else 1
        if raw_phase[0].islower():
            circuit += 2  # lower-voltage circuits on a quadruple tower
        conductors.append(physics.Conductor(
            x=float(c["x_m"]),
            y_base=float(c["y_m"]),
            phase=letter,
            circuit=circuit,
            current_A=float(c["current_A"]),
            voltage_kV=float(c["voltage_kV"]),
        ))
    return conductors


def geometry_availability(ref: Reference) -> Dict[str, bool]:
    """Which line types in this reference have published geometry."""
    return {
        lt: bool(g.get("available"))
        for lt, g in ref.tower_geometries.items()
    }


# ---------------------------------------------------------------------------
# CSV template for user-digitised data
# ---------------------------------------------------------------------------
def digitising_template_csv(reference_label: str = "") -> bytes:
    """
    A pre-formatted CSV the user can fill in when digitising a figure from
    a paywalled paper, matching the column names Taki's uploader accepts.
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Distance", "B_Field", "Source", "Notes"])
    w.writerow([0, "", reference_label, "Distance in m from centreline; B_Field in uT"])
    w.writerow([10, "", "", ""])
    w.writerow([20, "", "", ""])
    w.writerow([30, "", "", ""])
    return buf.getvalue().encode("utf-8")
