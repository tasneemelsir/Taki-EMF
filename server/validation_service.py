"""
validation_service.py
=====================
Verification and validation for the web app:

  * first-principles self-checks of the solvers (engine/validation.self_checks),
  * code-to-code comparison against the bundled published dataset,
  * comparison against the user's own field-meter survey (CSV).

Simulated and measured references are kept separate because they establish
different things (does the code agree with another code / does the model agree
with reality).
"""

from __future__ import annotations

import functools
import json
import math
import os
from typing import Dict, List, Optional

import numpy as np

from engine import benchmarks, earth, physics, validation

from . import service
from .service import _num, arr

_DATA_DIR = benchmarks._DATA_DIR


@functools.lru_cache(maxsize=1)
def _refs():
    return benchmarks.load_references()


@functools.lru_cache(maxsize=1)
def _raw_docs() -> Dict[str, dict]:
    out = {}
    if os.path.isdir(_DATA_DIR):
        for name in sorted(os.listdir(_DATA_DIR)):
            if name.endswith(".json"):
                try:
                    with open(os.path.join(_DATA_DIR, name), encoding="utf-8") as fh:
                        doc = json.load(fh)
                    out[doc["id"]] = doc
                except (OSError, ValueError, KeyError):
                    continue
    return out


@functools.lru_cache(maxsize=1)
def checks() -> List[dict]:
    return validation.self_checks()


def catalogue() -> dict:
    """Datasets, their provenance, the known comparison caveats and the citation-only library."""
    refs = _refs()
    raw = _raw_docs()
    sources = []
    for ref in refs.values():
        if not ref.datasets:
            continue
        geom = benchmarks.geometry_availability(ref)
        sources.append({
            "id": ref.id, "title": ref.title, "data_type": ref.data_type,
            "data_type_label": benchmarks.DATA_TYPE_LABELS.get(ref.data_type, ""),
            "citation": ref.full_citation, "short": ref.short_citation,
            "doi": ref.citation.get("doi", ""), "url": ref.citation.get("url", ""),
            "license": ref.citation.get("data_license", ""),
            "method": ref.method, "provenance": ref.provenance_notes,
            "caveats": raw.get(ref.id, {}).get("comparison_caveats", []),
            "datasets": [{
                "id": ds.id, "label": ds.label, "line_type": ds.line_type,
                "phasing": ds.conditions.get("phasing", "untransposed"),
                "ground_conducting": ds.conditions.get("ground_conducting"),
                "geometry_available": bool(geom.get(ds.line_type, False)),
                "points": [{"location": p.location, "distance_m": p.distance_m,
                            "comparable": p.comparable, "b_uT": p.b_field_uT, "e_kVm": p.e_field_kVm}
                           for p in ds.points],
            } for ds in ref.datasets],
        })
    bib = raw.get("citation_only_library", {}).get("bibliography", [])
    return {"sources": sources, "bibliography": bib}


def template_csv() -> bytes:
    return benchmarks.digitising_template_csv()


def _find_dataset(dataset_id: str):
    for ref in _refs().values():
        for ds in ref.datasets:
            if ds.id == dataset_id:
                return ref, ds
    return None, None


def compare(cfg: dict, dataset_id: Optional[str] = None, csv_text: Optional[str] = None,
            use_published_geometry: bool = False, match_ground: bool = True,
            with_shield: bool = False) -> dict:
    """
    Compare Taki's lateral B profile with a published dataset or an uploaded
    survey. With `use_published_geometry`, Taki is run on the exact tower
    geometry the source used (like-for-like); otherwise on the current project.
    With `with_shield`, an uploaded survey is compared with the field Taki
    calculates WITH the project's shield in place - for measurements taken
    behind or inside a shield that has been built.
    """
    site = service.site_for(cfg)
    notes: List[str] = []
    ref = ds = None
    excluded: List[str] = []
    e_points = []
    if csv_text is not None:
        measured = validation.parse_field_meter_csv(csv_text)
        label = "Your survey data"
        kind = benchmarks.USER
    else:
        ref, ds = _find_dataset(dataset_id or "")
        if ds is None:
            raise ValueError("Unknown dataset.")
        comp = ds.comparable_points
        excluded = [p.location for p in ds.excluded_points]
        if not comp:
            raise ValueError("This dataset has no distance-referenced points.")
        measured = {"Distance": np.array([p.distance_m for p in comp], float),
                    "B_Field": np.array([p.b_field_uT for p in comp], float)}
        e_points = [(p.distance_m, p.e_field_kVm) for p in comp if p.e_field_kVm is not None]
        label = ds.label
        kind = ref.data_type

    with site.lock:
        gm, rho = site.ground_model, site.earth_rho
        height = site.meas_height
        basis = "the current project configuration"
        conds = None
        if ds is not None and use_published_geometry:
            conds = benchmarks.build_conductors_from_reference(
                ref, ds.line_type, ds.conditions.get("phasing", "untransposed"))
            if conds:
                for c in conds:
                    c.y_sagged = c.y_base
                height = float(ref.method.get("measurement_height_m", 1.0))
                basis = f"the source's published tower geometry ({ds.line_type}, " \
                        f"{ds.conditions.get('phasing', 'untransposed')})"
                if match_ground and "ground_conducting" in ds.conditions:
                    gm = earth.PERFECT_CONDUCTOR if ds.conditions["ground_conducting"] else earth.FREE_SPACE
                    notes.append("Ground model matched to the dataset: "
                                 + earth.MODEL_INFO[gm]["label"].lower() + ".")
            else:
                notes.append("The source did not publish tower geometry for this line type, so the "
                             "current project configuration was used instead.")
        half = max(site.x_max, -site.x_min, float(np.max(np.abs(measured["Distance"]))) + 5.0)
        x = np.linspace(-half, half, 801)
        if conds:
            b = physics.compute_b_field_1d(conds, x, height, gm, rho, site.freq)
            e = physics.compute_e_field_1d(conds, x, height, bundle_equivalent=site.bundle_eq)
        else:
            p = site.profile(-half, half, 801, height)
            b, e = p["b0"], p["e0"]
            if with_shield and csv_text is not None:
                if site.shield_on:
                    b, e = p["bS"], p["eS"]
                    basis = f"the current project configuration with its shield ({site.geom.description})"
                    notes.append("Compared with the shielded field. The profile is taken through the middle "
                                 "of the shield's length, at the measurement height.")
                else:
                    notes.append("No shield is switched on in this project, so the unshielded field was used.")

    r = validation.compare_simulation_to_measured(x, b, measured)
    ratio = r["mean_ratio"]
    sqrt2 = None
    if ref is not None and conds and math.isfinite(ratio):
        sqrt2 = ratio / math.sqrt(2.0)
        if abs(sqrt2 - 1.0) < 0.02:
            notes.append(
                "Taki reads sqrt(2) = 1.414 times this source, uniformly. Both use the same "
                "resultant formula, so a constant sqrt(2) is the signature of a peak / RMS "
                "convention difference in the reference solver's inputs or outputs, not a geometry "
                "or physics error. Taki's value is an RMS field for RMS currents (see the "
                "self-check 'RMS resultant matches the time-domain definition'), and it is the "
                "higher, more conservative of the two.")
    e_rows = []
    if e_points and conds:
        for d, ev in e_points:
            te = float(np.interp(d, x, e))
            e_rows.append({"distance": d, "taki": _num(te), "reference": _num(ev),
                           "ratio": _num(te / ev, 4) if ev else None})
    return {
        "label": label, "kind": kind, "kind_label": benchmarks.DATA_TYPE_LABELS.get(kind, ""),
        "basis": basis, "ground_label": earth.describe(gm, rho), "height": height,
        # a published dataset is only comparable when Taki ran on that source's own geometry
        "like_for_like": bool(conds) if ds is not None else None,
        "excluded": excluded, "notes": notes,
        "rmse": _num(r["rmse"]), "nrmse": _num(r["nrmse_percent"], 3),
        "mape": _num(r["mape"], 3) if math.isfinite(r["mape"]) else None,
        "mape_used": r["mape_n_used"], "mape_excluded": r["mape_n_excluded"],
        "mean_ratio": _num(ratio, 5) if math.isfinite(ratio) else None,
        "ratio_over_sqrt2": _num(sqrt2, 5) if sqrt2 is not None else None,
        "n_outside": r["n_outside_domain"], "domain": [_num(r["domain_min"], 2), _num(r["domain_max"], 2)],
        "n_points": r["n_points"],
        "curve": {"x": arr(x, 3), "b": arr(b), "e": arr(e)},
        "points": [{"distance": _num(d, 3), "taki": _num(s), "reference": _num(m),
                    "delta": _num(s - m), "ratio": _num(q, 4) if math.isfinite(q) else None}
                   for d, s, m, q in zip(r["distance"], r["simulated"], r["measured"], r["ratio"])],
        "e_points": e_rows,
    }
