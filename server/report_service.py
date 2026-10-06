"""
report_service.py
=================
Assembles the report document model (see engine/report.py) from the solved
site, and renders it as TXT, PDF or Word. Also builds the context handed to the
optional AI narrative.

The structure follows the engineering-report outline used by the Figma
prototype (summary, objective/configuration, methodology, results, shielding,
standards assessment, validation, limitations, references), filled entirely
from computed numbers. AI text is optional and always labelled.
"""

from __future__ import annotations

import base64
import math
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np

from engine import (ai_report, earth, field_lines, libraries, references, report,
                    report_figures as rf, shield_engine as sh, standards)

from . import service, validation_service

DEFAULT_SECTIONS = {
    "summary": True, "objective": True, "configuration": True, "methodology": True,
    "results": True, "compliance": True, "conductors": True, "shield": True, "options": False,
    "receptors": True, "points": True, "scenarios": False, "validation": False,
    "limitations": True, "conclusion": True, "references": True,
}
DEFAULT_FIGURES = {
    "profile": True, "cross_section": True, "map_b": True, "map_e": False, "shield_maps": True,
    "receptors": True, "field_lines": False, "earth": False, "twin": True,
}

SECTION_LABELS = {                    # in the order they appear in the report
    "summary": "Executive summary", "objective": "Objective", "configuration": "Configuration",
    "methodology": "Numerical methodology", "results": "Field results",
    "compliance": "Standards assessment", "conductors": "Conductor detail", "shield": "Shielding",
    "options": "Shielding options compared", "receptors": "Building receptors",
    "points": "Measurement points", "scenarios": "Scenario comparison",
    "validation": "Solver verification", "limitations": "Limitations and uncertainty",
    "conclusion": "Conclusion", "references": "References",
}
SECTION_HINTS = {
    "objective": "printed when you write one below",
    "options": "materials, thicknesses and arrangements, each solved for this site",
    "scenarios": "the project's saved scenarios side by side",
}
FIGURE_LABELS = {
    "profile": "Lateral field profile", "cross_section": "Corridor cross-section",
    "map_b": "Magnetic field map", "map_e": "Electric field map",
    "shield_maps": "Shield: with / without / difference maps", "receptors": "Building receptor chart",
    "field_lines": "Magnetic field lines", "earth": "Earth-return sensitivity",
    "twin": "3-D digital twin view",
}

STATUS_TEXT = {"PASS": "compliant", "MARGINAL": "compliant with low margin", "FAIL": "exceeding the limit",
               "NOT_ASSESSED": "not assessed (no applicable limit)"}


def _f(v, nd=3):
    return "-" if v is None else f"{float(v):.{nd}f}"


def _g(v):
    return "-" if v is None else f"{float(v):g}"


def _fu(v, nd: int, unit: str) -> str:
    """A value with its unit to `nd` decimals; one too small to show at that precision reads 'about 0'."""
    if v is None:
        return "-"
    v = float(v)
    return f"about 0 {unit}" if abs(v) < 0.5 * 10.0 ** (-nd) else f"{v:.{nd}f} {unit}"


def _lo(v, ref=None) -> str:
    """A field value to three figures; one that has all but vanished prints as 'about 0'."""
    if v is None:
        return "-"
    v = float(v)
    if (ref is not None and abs(v) < 1e-3 * abs(float(ref))) or abs(v) < 1e-9:
        return "about 0"
    return f"{v:.3g}" if abs(v) >= 1e-3 else f"{v:.2g}"


def _chg(reduction_pct) -> str:
    """
    A reduction as a signed change: 35 -> "-35%", -8 -> "+8%". Near total
    reductions keep their decimals, so 99.6 reads "-99.6%" and not "-100%".
    """
    c = -float(reduction_pct)
    if abs(c) < 0.5:
        return "0%"
    if 99.0 <= abs(c) < 99.995:
        return f"{c:+.{1 if abs(c) < 99.95 else 2}f}%"
    return f"{c:+.0f}%"


def options_catalogue() -> dict:
    return {"sections": [{"id": k, "label": v, "default": DEFAULT_SECTIONS[k], "hint": SECTION_HINTS.get(k, "")}
                         for k, v in SECTION_LABELS.items()],
            "figures": [{"id": k, "label": v, "default": DEFAULT_FIGURES[k]} for k, v in FIGURE_LABELS.items()],
            "ai_providers": ai_report.catalogue()}


def _pct_small(v: float) -> str:
    """An error in percent for a table: errors too small to matter print as 0%."""
    v = abs(float(v))
    if v < 0.0005:
        return "0%"
    return f"{v:.3f}%" if v < 0.01 else f"{v:.2g}%"


def _circuits_differ(ln: dict) -> bool:
    circ = ln.get("circuits") or []
    return bool(ln.get("separate")) or len({(k["kv"], k["rated_a"], k["load_pct"], k["on"]) for k in circ}) > 1


def _line_summary(ln: dict) -> str:
    bits = [ln["preset"], f"offset {ln['x_offset']:+g} m"]
    if _circuits_differ(ln):
        for k in ln["circuits"]:
            bits.append(f"{k['label']} circuit: " + (
                f"{k['kv']:g} kV, {k['operating_a']:.0f} A ({k['load_pct']:g}% of {k['rated_a']:.0f} A), "
                f"phases {k['phase_order']}" if k["on"] else "out of service (earthed)"))
    else:
        bits += [f"{ln['kv']:g} kV", f"{ln['operating_a']:.0f} A ({ln['load_pct']:g}% of {ln['rated_a']:.0f} A)"
                 + (" per circuit" if ln["is_double"] else "")]
        if ln["is_double"]:
            bits.append(ln["arrangement"])
    if ln["phase_offset_deg"]:
        bits.append(f"phase {ln['phase_offset_deg']:+g} deg")
    return " | ".join(bits)


def _any_off(sol: dict) -> bool:
    return any(not k["on"] for ln in sol["lines"] for k in ln.get("circuits") or [])


def _summary_text(sol: dict, site) -> str:
    n = len(sol["lines"])
    cor = sol["corridor"]
    kinds = [f"{v:g} kV" for v in sorted({k["kv"] for ln in sol["lines"] for k in ln["circuits"] if k["on"]}
                                         or {ln["kv"] for ln in sol["lines"]})]
    t = [f"This report assesses the power-frequency electric and magnetic fields of "
         f"{n} overhead transmission line{'s' if n != 1 else ''} ({', '.join(kinds)}) at "
         f"{cor['freq']:g} Hz, evaluated at mid-span and {cor['meas_height']:g} m above ground "
         f"with the earth modelled as: {cor['ground_note'].lower()}."]
    t.append(f"The peak magnetic flux density is {sol['peak_b']:.2f} µT at x = {sol['peak_b_x']:.1f} m "
             f"and the peak electric field is {sol['peak_e']:.3f} kV/m at x = {sol['peak_e_x']:.1f} m."
             + (f" Outside the right-of-way (from ±{cor['row_half']:g} m outward) the highest values are "
                f"{sol['row_b']:.2f} µT and {sol['row_e']:.3f} kV/m." if sol.get("row_b") is not None else ""))
    g = sol.get("governing")
    if g:
        q = "magnetic field" if g["quantity"] == "B" else "electric field"
        t.append(f"Across the selected standards the governing case is the {q} against "
                 f"{g['standard']}: {g['value']:.3g} {g['unit']} against a limit of {g['limit']:g} "
                 f"{g['unit']} ({g['pct']:.0f}% of the limit). The overall result is: "
                 f"{STATUS_TEXT.get(sol['overall'], sol['overall'])}.")
    else:
        t.append("No selected standard sets a limit that could be assessed.")
    shd = sol["shield"]
    if shd["on"]:
        what = (f"{shd['material']['label'].split(' (')[0].lower()} conductors of {shd['wire_mm2']:g} mm2"
                if shd.get("is_wire") else
                f"{shd['material']['label'].lower()}, {shd['thickness_mm']:g} mm"
                + (f" with a second layer of {shd['layer2'].lower()}" if shd.get("layer2") else ""))
        t.append(f"Shielding is included for information: {shd['label']}, {what}, modelled with the "
                 f"{'physical (finite-shield solver)' if shd.get('is_wire') else shd['model_label'].lower()}.")
        z = shd.get("protected")
        if z:
            t.append(f"Inside {z['label']} the average magnetic field changes from {z['b']['avg0']:.3g} to "
                     f"{_lo(z['b']['avgS'], z['b']['avg0'])} µT ({_chg(z['b']['reduction_pct'])}) and the "
                     f"average electric field from {z['e']['avg0']:.3g} to "
                     f"{_lo(z['e']['avgS'], z['e']['avg0'])} kV/m ({_chg(z['e']['reduction_pct'])}).")
        t.append("The shield is not credited in the compliance result, which uses the unshielded field.")
    return "\n".join(t)


def _result_rows(sol: dict) -> List[List[str]]:
    cor, on = sol["corridor"], sol["shield"]["on"]
    row = sol.get("row_b") is not None
    return [
        ["Magnetic flux density (RMS)", f"{sol['peak_b']:.3f} µT", f"x = {sol['peak_b_x']:.1f} m",
         f"{sol['row_b']:.3f} µT (beyond ±{cor['row_half']:g} m)" if row else "-",
         f"{sol['peak_b_shield']:.3f} µT" if on else "-"],
        ["Electric field (RMS)", f"{sol['peak_e']:.3f} kV/m", f"x = {sol['peak_e_x']:.1f} m",
         f"{sol['row_e']:.3f} kV/m (beyond ±{cor['row_half']:g} m)" if row else "-",
         f"{sol['peak_e_shield']:.3f} kV/m" if on else "-"],
    ]


def _reach_rows(sol: dict) -> List[List[str]]:
    """Distance from the centreline beyond which the unshielded field stays below each level."""
    x = np.asarray(sol["profile"]["x"], float)
    out = []
    levels = [("B", v, "µT") for v in (100.0, 10.0, 1.0, 0.4)] + [("E", v, "kV/m") for v in (5.0, 1.0, 0.1)]
    for q, level, unit in levels:
        y = np.asarray(sol["profile"]["b0" if q == "B" else "e0"], float)
        if float(y.max()) < level:
            continue
        cells = []
        for side in (-1, 1):
            sel = x * side >= 0
            xs, ys = np.abs(x[sel]), y[sel]
            order = np.argsort(xs)
            xs, ys = xs[order], ys[order]
            above = np.nonzero(ys >= level)[0]
            if not len(above):
                cells.append("below everywhere")
            elif above[-1] == len(xs) - 1:
                cells.append(f"more than {xs[-1]:.0f} m")
            else:
                i = above[-1]
                d = xs[i] + (ys[i] - level) / max(ys[i] - ys[i + 1], 1e-12) * (xs[i + 1] - xs[i])
                cells.append(f"{d:.1f} m")
        out.append([f"{q} below {level:g} {unit}", cells[0], cells[1]])
    return out


def _conclusion_text(sol: dict) -> str:
    g, shd = sol.get("governing"), sol["shield"]
    t = []
    if g:
        q = "magnetic field" if g["quantity"] == "B" else "electric field"
        verdict = {"PASS": "are within every selected limit",
                   "MARGINAL": "are within every selected limit, with little margin",
                   "FAIL": "exceed at least one selected limit"}.get(sol["overall"], "could not be assessed")
        t.append(f"The calculated unshielded fields {verdict}. The governing case is the {q} against "
                 f"{g['standard']}, at {g['pct']:.0f}% of its limit"
                 + (f" ({g['headroom']:.0f}% margin)." if g["headroom"] >= 0 else f" ({-g['headroom']:.0f}% over)."))
    else:
        t.append("No selected standard sets a limit that could be assessed, so no compliance conclusion is drawn.")
    if shd["on"]:
        z = shd.get("protected")
        if z:
            b_red, e_red = z["b"]["reduction_pct"], z["e"]["reduction_pct"]
            t.append(f"The shield studied ({shd['label'][:1].lower() + shd['label'][1:]}) changes the average "
                     f"magnetic field inside "
                     f"{z['label']} by {_chg(b_red)} and the average electric field by {_chg(e_red)}."
                     + (" The electric field is far easier to screen than the magnetic field, which at "
                        "power frequency needs a closed, well-bonded conducting or magnetic shell."
                        if e_red - b_red > 25 else ""))
        if sol["peak_b_shield"] > 1.05 * sol["peak_b"]:
            t.append("Beside the shield the magnetic field is higher than without it, so the area around "
                     "the shield should be checked as well as the space it protects.")
        t.append("The shield is reported for information and is not a compliance credit.")
    t.append("These are calculated estimates for the stated geometry, loading and earth model. A compliance "
             "decision needs as-built line data and measurements with calibrated instruments under known load.")
    return " ".join(t)


def _reference_items(sol: dict) -> List[str]:
    """
    The reference list: each selected standard's own source (standards that
    share a document are listed together), then the method references, leaving
    out any that a standard's source has already named.
    """
    by_source: Dict[str, List[str]] = {}
    for r in sol["results"]:
        if r["source"]:
            by_source.setdefault(r["source"].strip(), []).append(r["name"])
    # a source that is another one plus a remark ("... 1998. Applied in Malaysian practice.") is the
    # same document: list it once, under both names, and keep the remark
    order = list(by_source)
    groups: Dict[str, dict] = {}
    for src in order:
        shorter = [s for s in order if s != src and src.startswith(s)]
        base = min(shorter, key=len) if shorter else src
        g = groups.setdefault(base, {"names": [], "extra": []})
        g["names"] += by_source[src]
        if src[len(base):].strip():
            g["extra"].append(src[len(base):].strip())
    items = [f"{'; '.join(g['names'])}: {base}" + (" " + " ".join(g["extra"]) if g["extra"] else "")
             for base, g in groups.items()]
    flat = " ".join(by_source).lower()
    used = ["icnirp2010", "icnirp1998", "deri1981", "epri-redbook", "ieee644"]
    if sol["shield"]["on"]:
        used += ["krahenbuhl1993", "hasselgren1995", "ott2009", "cigre373"]
    for rid in used:
        ref = references.get(rid)
        if not ref:
            continue
        marks = [m.lower() for m in (ref.get("doi"), ref.get("venue")) if m]
        if any(m in flat for m in marks):
            continue                                   # a selected standard already cites this document
        items.append(references.format_citation(ref))
    return items


def build_doc(cfg: dict, options: Optional[dict] = None, user: Optional[dict] = None) -> dict:
    options = options or {}
    sec = dict(DEFAULT_SECTIONS); sec.update(options.get("sections") or {})
    figs = dict(DEFAULT_FIGURES); figs.update(options.get("figures") or {})
    with_figures = bool(options.get("with_figures", True))
    log_scale = bool(options.get("log_scale", True))
    site = service.site_for(cfg)
    sol = service.solve(cfg)
    cor, shd = sol["corridor"], sol["shield"]
    blocks: List[dict] = []
    H = lambda t, lvl=1: blocks.append({"type": "heading", "text": t, "level": lvl})
    P = lambda t: blocks.append({"type": "para", "text": t})
    N = lambda t: blocks.append({"type": "note", "text": t})

    blocks.append({"type": "status", "status": sol["overall"],
                   "text": f"Overall result (worst case across selected standards, unshielded field): "
                           f"{report.STATUS_LABEL.get(sol['overall'], sol['overall'])}"})
    if sec["summary"]:
        H(SECTION_LABELS["summary"]); P(_summary_text(sol, site))

    objective = str(options.get("objective") or "").strip()[:2000]
    if sec["objective"] and objective:
        H(SECTION_LABELS["objective"]); P(objective)

    if sec["configuration"]:
        H(SECTION_LABELS["configuration"])
        rows = [[ln["name"], _line_summary(ln)] for ln in sol["lines"]]
        rows += [
            ["Right-of-way half-width", f"± {cor['row_half']:g} m"],
            ["Span length", f"{2 * cor['half_span']:g} m (towers at ± {cor['half_span']:g} m)"],
            ["Thermal sag at 100% load", f"{site.max_sag * site.sag_scale:.3g} m"
             + (f" ({site.max_sag:g} m at the 300 m reference span)" if site.sag_follows_span else "")],
            ["Sag and span", (f"sag follows the span: design and thermal sag scaled by (span / 300 m)^2 = "
                              f"{site.sag_scale:.3g}; attachment heights fixed" if site.sag_follows_span
                              else "sag set independently of the span (mid-span heights as entered)")],
            ["Earth-return model", cor["ground_note"]],
            ["System frequency", f"{cor['freq']:g} Hz"],
            ["Measurement height", f"{cor['meas_height']:g} m above ground"],
            ["E field: bundle-equivalent radius", "on" if cor["bundle_eq"] else "off"],
            ["Peak B (unshielded)", f"{sol['peak_b']:.3f} µT at x = {sol['peak_b_x']:.1f} m"],
            ["Peak E (unshielded)", f"{sol['peak_e']:.3f} kV/m at x = {sol['peak_e_x']:.1f} m"],
        ]
        cl = sol.get("clearance")
        if cl:
            rows.insert(len(sol["lines"]) + 4, [
                "Lowest conductor at mid-span",
                f"{cl['min_height_m']:.1f} m above ground ({cl['line']}); indicative minimum for "
                f"{cl['tightest_line']} is {cl['required_m']:.1f} m" + ("" if cl["ok"] else " - NOT MET")])
        for b in site.buildings:
            rows.append([b["name"], f"{b['type']}, {libraries.BUILDING_SHAPES.get(b['shape'], b['shape']).lower()}, "
                                    f"{b['width']:g} x {b['depth']:g} x {b['height']:g} m, near wall "
                                    f"{b['distance']:g} m {b['side']} of the centreline, z = {b['z_offset']:g} m"])
        blocks.append({"type": "table", "header": ["Parameter", "Value"], "rows": rows, "widths": [1, 2.2]})

    if sec["methodology"]:
        H(SECTION_LABELS["methodology"])
        items = [
            "Magnetic field: Biot-Savart law for long straight conductors with complex-phasor "
            "superposition of every sub-conductor of every phase. The reported value is the RMS "
            "resultant sqrt(|Bx|^2 + |By|^2) for RMS phase currents.",
            f"Earth return: {cor['ground_note']}. Free space and perfectly conducting earth are the "
            "two exact limits of earth resistivity; real earth lies between them.",
            "Electric field: Maxwell potential-coefficient matrix with the method of images "
            "(ground as an equipotential plane); bundled phases use the bundle-equivalent radius"
            + ("." if cor["bundle_eq"] else " (switched off for this run)."),
            "Operating current is the rated current multiplied by the loading; loading also sets "
            "the thermal sag. Fields are evaluated at mid-span, where the conductors are lowest."
            + (" A circuit out of service is taken as de-energised and earthed: it carries no current "
               "and sits at zero potential (its conductors still shape the electric field), and the "
               "current the live circuits induce in it is not modelled." if _any_off(sol) else ""),
            "Compliance compares the unshielded peak on the lateral profile with each selected "
            "limit at the system frequency. Shielding never changes a compliance result.",
        ]
        if shd["on"]:
            if shd["model"] == "physical":
                items.append(
                    "Shield (physical model): the shield is meshed into thin-shell boundary "
                    "elements. Magnetic field: eddy currents and flux shunting in the finite plate, "
                    "solved with the line as the source, so flux wrapping round the edges is "
                    "included. Electric field: the shield is a conductor in the electrostatic "
                    "problem, earthed or floating as specified.")
            elif shd["model"] == "analytical":
                items.append(
                    "Shield (analytical model): Schelkunoff absorption + reflection + "
                    "multiple-reflection for an infinite sheet, applied to points in the shield's "
                    "geometric shadow. For the 50/60 Hz magnetic field this is a theoretical upper "
                    "bound on a real shield.")
            else:
                items.append("Shield (empirical model): literature-based percentage reductions "
                             "applied to points in the shield's geometric shadow.")
        blocks.append({"type": "bullets", "items": items})

    if sec["results"]:
        H(SECTION_LABELS["results"])
        blocks.append({"type": "table", "header": ["Quantity", "Peak", "Where", "Highest outside the right-of-way",
                                                   "With the shield (peak)"],
                       "rows": _result_rows(sol), "widths": [1.5, 1.0, 1.1, 1.5, 1.4]})
        reach = _reach_rows(sol)
        if reach:
            blocks.append({"type": "heading", "text": "How far the field reaches", "level": 2})
            blocks.append({"type": "table", "header": ["Level", "Left of the centreline", "Right of the centreline"],
                           "rows": reach, "widths": [1.6, 1.4, 1.4]})
            N("Distance from the centreline beyond which the field stays below each level. "
              "\"More than\" means it is still above the level at the edge of the calculated width.")
        N(f"Unshielded RMS values on the lateral profile at mid-span, {cor['meas_height']:g} m above ground. "
          "The electric field follows the voltage and the conductor heights; the magnetic field follows "
          "the current, so it scales with loading.")

    if sec["compliance"]:
        H(SECTION_LABELS["compliance"])
        rows = []
        for r in sol["results"]:
            rows.append([r["name"], "Limit" if r["kind"] == "limit" else "Precautionary",
                         f"{_f(r['b']['value'])} / {_g(r['b']['limit'])} µT" if r["b"]["limit"] is not None else "-",
                         f"{_f(r['e']['value'])} / {_g(r['e']['limit'])} kV/m" if r["e"]["limit"] is not None else "-",
                         r["overall"].replace("_", " ")])
        if rows:
            blocks.append({"type": "table", "header": ["Standard", "Type", "B: value / limit",
                                                       "E: value / limit", "Result"],
                           "rows": rows, "widths": [2.3, 1.0, 1.5, 1.5, 1.0], "status_col": 4})
        else:
            P("No standard was selected.")
        flagged = [r["name"] for r in sol["results"] if r["needs_verification"]]
        N("Limits are evaluated at the system frequency. 'Precautionary' entries are planning or "
          "attention values, not exposure limits."
          + (f" Verify against the primary document before certifying: {', '.join(flagged)}." if flagged else ""))

    if sec["conductors"]:
        H(SECTION_LABELS["conductors"])
        rows = []
        for ln in sol["lines"]:
            for c in ln["conductors"]:
                on = c.get("on", True)
                rows.append([ln["name"], c["phase"], str(c["circuit"]), f"{c['x']:.2f}", f"{c['y']:.2f}",
                             f"{c['y_att']:.2f}", f"{c['current_a']:.0f}" if on else "off",
                             f"{c['voltage_kv']:.0f}" if on else "earthed", str(len(c["bundle"]) or 1)])
        blocks.append({"type": "table",
                       "header": ["Line", "Phase", "Circuit", "x (m)", "Mid-span height (m)",
                                  "Attachment (m)", "Current (A)", "Voltage (kV)", "Bundle"],
                       "rows": rows, "widths": [1.6, 0.7, 0.7, 0.8, 1.2, 1.1, 1.0, 1.0, 0.7]})

    models = None
    if shd["on"] and sec["shield"]:
        H(SECTION_LABELS["shield"])
        m = shd["material"]
        wire = bool(shd.get("is_wire"))
        rows = [["Arrangement", shd["label"]],
                ["Model", "Physical (finite-shield solver)" if wire else shd["model_label"]],
                ["Material", f"{m['label']} ({m['quality']} property data): sigma = {m['sigma']:.3g} S/m, "
                             f"mu_r = {m['mu_r']:g}"]]
        if wire:
            rows.append(["Conductors", f"{len(shd['wires'])} x {shd['wire_mm2']:g} mm2 "
                                       f"(diameter {2 * shd['wire_radius_mm']:.1f} mm); "
                                       f"{'earthed' if shd['grounded'] else 'unearthed'}; "
                                       f"{'bonded at both ends (closed loop)' if shd['bonded'] else 'not bonded (open)'}"
                                       + (f"; {shd['compensation_pct']:g}% series-capacitor compensation"
                                          if shd.get("compensation_pct") else "")])
            rows.append(["Positions (x, height)", "; ".join(f"({w[0]:.1f}, {w[1]:.1f}) m" for w in shd["wires"])])
            if shd.get("loop_current_a") is not None:
                rows.append(["Largest induced conductor current", f"{shd['loop_current_a']:.3g} A"])
        else:
            rows.append(["Construction", f"{shd['thickness_mm']:g} mm x {shd['layers']} "
                                         f"layer{'' if shd['layers'] == 1 else 's'}"
                                         + (f", second layer {shd['layer2']}" if shd.get("layer2") else "")
                                         + f"; coverage {shd['coverage_pct']:g}%; "
                                         f"{'earthed' if shd['grounded'] else 'unearthed'}; "
                                         f"{'bonded' if shd['bonded'] else 'unbonded'} seams"
                                         + ("; mesh" if shd["mesh"] else "")])
        rows.append(["Extent along the line", f"z = {shd['zc'] - shd['zh']:g} to {shd['zc'] + shd['zh']:g} m"])
        z = shd.get("protected")
        if z:
            rows.append([f"Magnetic field inside {z['label']}",
                         f"average {z['b']['avg0']:.3g} -> {_lo(z['b']['avgS'], z['b']['avg0'])} µT "
                         f"({_chg(z['b']['reduction_pct'])}); highest point {z['b']['max0']:.3g} -> "
                         f"{_lo(z['b']['maxS'], z['b']['max0'])} µT"])
            rows.append([f"Electric field inside {z['label']}",
                         f"average {z['e']['avg0']:.3g} -> {_lo(z['e']['avgS'], z['e']['avg0'])} kV/m "
                         f"({_chg(z['e']['reduction_pct'])}); highest point {z['e']['max0']:.3g} -> "
                         f"{_lo(z['e']['maxS'], z['e']['max0'])} kV/m"])
        if shd.get("skin_depth_mm") and not wire:
            rows.append(["Skin depth", f"{shd['skin_depth_mm']:.2f} mm at {cor['freq']:g} Hz"])
        pr = shd.get("probe")
        if pr:
            at_wall = bool(z) and not shd.get("room")
            rows.append([("At one point: 1 m inside the wall facing the line" if at_wall
                          else "At one point: the centre of the room" if shd.get("room")
                          else "At one point behind the shield"),
                         f"x = {pr['x']:.1f} m, y = {pr['y']:.1f} m: magnetic {pr['b0']:.3g} -> "
                         f"{_lo(pr['bS'], pr['b0'])} µT ({_chg(pr['b_red_pct'])}, {shd['se_b']:.1f} dB); electric "
                         f"{pr['e0']:.3g} -> {_lo(pr['eS'], pr['e0'])} kV/m ({_chg(pr['e_red_pct'])}, "
                         f"{shd['se_e']:.1f} dB)"])
        if shd.get("floating_kv"):
            rows.append(["Induced voltage on the unearthed shield", f"{shd['floating_kv']:.2f} kV (touch hazard)"])
        if shd.get("loss_w_per_m") is not None and shd["model"] == "physical":
            rows.append(["Eddy-current loss in the shield", f"{shd['loss_w_per_m']:.3g} W per metre of line"])
        rows.append(["Peak on the profile", f"B {sol['peak_b']:.3f} -> {sol['peak_b_shield']:.3f} µT; "
                                            f"E {sol['peak_e']:.3f} -> {sol['peak_e_shield']:.3f} kV/m"])
        blocks.append({"type": "table", "header": ["Property", "Value"], "rows": rows, "widths": [1, 2.2]})
        if z:
            N("The shield is judged on the average over the protected space, 1 m clear of its walls, floor "
              "and roof. One point can sit in a quiet spot or a hot one: right inside a shielded wall the "
              "field can fall far more than the building as a whole gains, and at an open edge it can rise.")
        closed = shd["preset"] in ("enclosure", "envelope", "room")
        if closed and shd["coverage_pct"] >= 99.5 and shd["bonded"] and not shd["mesh"]:
            N("These figures are for an ideal shell: continuous sheet, every seam bonded, no doors, windows "
              "or service openings. They are the ceiling for this arrangement. Openings and unbonded seams "
              "in a real building reduce the magnetic shielding substantially and must be assessed "
              "(coverage and seam settings) before the figures are relied on.")
    if shd["on"] and sec["shield"] and not shd.get("is_wire"):
        models = service.shield_models(cfg)
        blocks.append({"type": "heading", "level": 2,
                       "text": "The same shield under each model ("
                               + ("average " if models["basis"] == "inside" else "") + f"{models['receptor']})"})
        blocks.append({"type": "table",
                       "header": ["Model", "B without", "B with", "B change", "E without", "E with", "E change"],
                       "rows": [[r["label"], _fu(r["b0"], 3, "µT"), _fu(r["bS"], 3, "µT"), f"{_chg(r['b_red_pct'])}",
                                 _fu(r["e0"], 4, "kV/m"), _fu(r["eS"], 4, "kV/m"), f"{_chg(r['e_red_pct'])}"]
                                for r in models["rows"] if r["available"]],
                       "widths": [2.6, 1, 1, 0.9, 1.1, 1.1, 0.9]})
        N("The physical model solves the shield as built. The analytical model is the infinite-sheet "
          "formula and is an upper bound for the magnetic field at power frequency. The empirical "
          "model is the literature percentage. None of them is a compliance credit.")

    if sec["options"] and site.buildings:
        H(SECTION_LABELS["options"])
        first = None
        for kind, title in (("geometry", "Arrangements and measures at the line"),
                            ("material", "Materials, same arrangement"),
                            ("thickness", "Thickness, same material and arrangement")):
            if kind != "geometry" and (not shd["on"] or shd.get("is_wire")):
                continue
            sw = service.shield_sweep(cfg, kind)
            first = first or sw
            blocks.append({"type": "heading", "text": f"{title} (average {sw['receptor']})", "level": 2})

            def name(r):
                # the note after the last dash says where the option stands ("27 m from the centreline, ...")
                place = r["sub"].rsplit(" - ", 1)[1] if kind == "geometry" and " - " in (r.get("sub") or "") else ""
                return r["label"] + (f" ({place})" if place else "")

            blocks.append({"type": "table",
                           "header": ["Option", "B inside", "B change", "B worst point", "E inside", "E change"],
                           "rows": [[name(r), _fu(r["bS"], 3, "µT"), f"{_chg(r['b_red_pct'])}",
                                     _fu(r["b_maxS"], 3, "µT") if r.get("b_maxS") is not None else "-",
                                     _fu(r["eS"], 4, "kV/m"), f"{_chg(r['e_red_pct'])}"]
                                    for r in sw["rows"]],
                           "widths": [3.6, 1.0, 0.9, 1.1, 1.2, 0.9]})
            if sw.get("note"):
                N(sw["note"].replace('"Use" applies exactly what the row was solved with.', "").strip())
        if first:
            N("Every row is a separate solution for this site; nothing is scaled from another row. Values are "
              "the average over the inside of the building, with the highest point inside beside it. Without "
              f"a shield the averages are {_f(first['b0'])} µT and {_f(first['e0'], 4)} kV/m. "
              "A positive change is an increase.")

    if sec["receptors"] and sol["receptors"]:
        H(SECTION_LABELS["receptors"])
        rows = []
        any_emp = any(r["material_key"] != "none" for r in sol["receptors"])
        for r in sol["receptors"]:
            on = r["barrier_on"]
            row = [r["building"], r["building_type"], _fu(r["b_in_avg_uT"], 3, "µT"),
                   f"{_fu(r['b_in_avg_shield_uT'], 3, 'µT')} ({_chg(r['b_in_reduction_pct'])})" if on else "-",
                   _fu(r["e_in_avg_kVm"], 4, "kV/m"),
                   f"{_fu(r['e_in_avg_shield_kVm'], 4, 'kV/m')} ({_chg(r['e_in_reduction_pct'])})" if on else "-",
                   f"{_f(r['b_unshielded_uT'])}" + (f" -> {_f(r['b_barrier_uT'])}" if on else "") + " µT"]
            if any_emp:
                row.append(f"{r['material']}: B {_f(r['b_shielded_uT'])} µT" if r["material_key"] != "none" else "-")
            rows.append(row)
        blocks.append({"type": "table",
                       "header": ["Building", "Type", "B inside, average", "with the shield", "E inside, average",
                                  "with the shield", "B at the wall probe"]
                                 + (["Empirical building material"] if any_emp else []),
                       "rows": rows, "widths": [1.3, 1.0, 1.0, 1.5, 1.1, 1.6, 1.4] + ([1.6] if any_emp else [])})
        N("Averages are taken over the inside of each building, 1 m clear of its walls, floor and roof, in "
          "the cross-section through its centre. The wall probe is a single point 1 m inside the wall facing "
          "the line, at half height: it reads higher than the average, and behind a shielded wall it can "
          "fall by more than the building as a whole gains. A shield acts on the building it is built around.")

    pts = service.points(cfg)["rows"]
    if sec["points"] and pts:
        H(SECTION_LABELS["points"])
        head = ["#", "Label", "x (m)", "y (m)", "z (m)", "B (µT)", "E (kV/m)"]
        widths = [0.4, 1.6, 0.7, 0.7, 0.7, 1.0, 1.0]
        if shd["on"]:
            head = head[:6] + ["B with shield"] + head[6:] + ["E with shield"]
            widths = [0.4, 1.3, 0.7, 0.7, 0.7, 0.9, 1.5, 0.9, 1.6]
        prow = []
        for p in pts:
            base = [str(p["n"]), p["label"], f"{p['x']:.1f}", f"{p['y']:.1f}", f"{p['z']:.1f}"]
            if not shd["on"]:
                prow.append(base + [_f(p["b0"]), _f(p["e0"], 4)])
            elif not p["in_shield_length"]:
                prow.append(base + [_f(p["b0"]), "beyond the shield", _f(p["e0"], 4), "beyond the shield"])
            else:
                zero = lambda v, nd: "about 0" if abs(float(v)) < 0.5 * 10.0 ** (-nd) else _f(v, nd)   # noqa: E731
                prow.append(base + [_f(p["b0"]), f"{zero(p['bS'], 3)} ({_chg(p['b_red_pct'])})",
                                    _f(p["e0"], 4), f"{zero(p['eS'], 4)} ({_chg(p['e_red_pct'])})"])
        blocks.append({"type": "table", "header": head, "rows": prow, "widths": widths})
        N("Exact values recomputed at each point for the conductor heights at its position along the span."
          + (" \"Beyond the shield\" marks a point outside the shield's length along the line, where the "
             "field is the unshielded one." if shd["on"] and any(not p["in_shield_length"] for p in pts) else ""))

    saved = [s for s in (options.get("scenarios") or []) if isinstance(s, dict) and isinstance(s.get("config"), dict)]
    if sec["scenarios"] and saved:
        H(SECTION_LABELS["scenarios"])
        items = [{"name": str(s.get("name") or "Scenario")[:80], "config": service.normalise_config(s["config"])}
                 for s in saved[:12]]
        items.append({"name": "This report (current inputs)", "config": cfg})
        cmp_rows = []
        for r in service.compare_scenarios(items)["rows"]:
            if r.get("error"):
                cmp_rows.append([r["name"], "-", "-", "-", "-", r["error"], "-"])
                continue
            eff = r.get("shield_effect")
            cmp_rows.append([r["name"], str(r["lines"]), f"{_f(r['peak_b'])} µT", f"{_f(r['peak_e'], 4)} kV/m",
                             r["overall"].replace("_", " "), r["ground"],
                             "off" if r["shield"] == "off" else r["shield"] + (
                                 f": B {_chg(eff['b_red_pct'])}, E {_chg(eff['e_red_pct'])} "
                                 + ("inside" if eff["basis"] == "inside" else "behind it") if eff else "")])
        blocks.append({"type": "table",
                       "header": ["Scenario", "Lines", "Peak B", "Peak E", "Result", "Earth", "Shield and its effect"],
                       "rows": cmp_rows, "widths": [1.9, 0.75, 1.05, 1.2, 1.1, 1.3, 2.6], "status_col": 4})
        N("Each scenario is recalculated with its own lines, earth model, standards and shield. "
          "Peaks are unshielded values. The shield's effect is the change in the average field inside "
          "the space it protects.")

    if sec["validation"]:
        H(SECTION_LABELS["validation"])
        blocks.append({"type": "table",
                       "header": ["Check", "Expected", "Calculated", "Error", "Result"],
                       "rows": [[c["title"]] + [f"{v:.5g}" + ("" if c["unit"] == "ratio" else f" {c['unit']}")
                                                for v in (c["expected"], c["got"])]
                                + [_pct_small(c["error_pct"]), "PASS" if c["passed"] else "FAIL"]
                                for c in validation_service.checks()],
                       "widths": [3.2, 1.2, 1.2, 0.8, 0.7], "status_col": 4})
        N("These are verifications of the implementation against analytical solutions. They do not "
          "validate the model against site measurements. Values without a unit are ratios; errors "
          "below 0.0005% are printed as 0%.")

    if options.get("ai_narrative"):
        H("AI-generated assessment")
        P(str(options["ai_narrative"]))
        N("This section was drafted by an AI model from the results above. It does not determine, "
          "and must not be read as overriding, the compliance result computed by the standards "
          "engine. Review by a qualified engineer before distribution.")

    if sec["limitations"]:
        H(SECTION_LABELS["limitations"])
        items = [
            "Two-dimensional model of long, straight, parallel conductors. It is not valid near "
            "angle towers, terminations or line crossings.",
            "The field along the span uses the 2-D solution for the conductor heights at each "
            "position; tower steelwork and insulators are not field sources.",
            "Tower presets and currents are representative engineering values, not as-built data. "
            "Replace them with project data before relying on the result.",
            "Balanced three-phase currents are assumed; unbalance and earth-wire currents are not modelled.",
        ]
        if not cor["ground_validated"]:
            items.append("The finite-resistivity earth model has not been validated against reference "
                         "data; bracket the result with the two exact limits before reporting it.")
        if shd["on"]:
            items.append("Shield results apply within the shield's length, away from its ends. "
                         "Material properties marked 'assumed' are nominal; steel saturation and the "
                         "shielding a building gives its own interior are not modelled.")
        items.append("An engineering-reference calculation. It does not replace a certified "
                     "compliance study with calibrated measurements.")
        blocks.append({"type": "bullets", "items": items})

    if sec["conclusion"]:
        H(SECTION_LABELS["conclusion"]); P(_conclusion_text(sol))

    if sec["references"]:
        H(SECTION_LABELS["references"])
        blocks.append({"type": "bullets", "items": _reference_items(sol)})

    # ------------------------------------------------------------------ figures
    if with_figures and any(figs.values()):
        blocks.append({"type": "pagebreak"})
        H("Figures")
        with site.lock:
            conds = [(c.x, c.y_sagged, c.phase) for c in site.conductors]
            bld = [{"x0": sh.building_x(b)[0], "x1": sh.building_x(b)[1], "h": b["height"], "name": b["name"]}
                   for b in site.buildings]
            walls = site.geom.walls if site.shield_on else None
            prof = site.profile()
            b_limits = [(r["b"]["limit"], r["name"]) for r in sol["results"] if r["b"]["limit"] is not None]
            sub = f"{cor['ground_note']} - {cor['freq']:g} Hz - {cor['meas_height']:g} m above ground"

            def fig(title, png, caption=None):
                blocks.append({"type": "figure", "title": title, "png": png, "caption": caption})

            if figs["profile"]:
                fig("Lateral field profile",
                    rf.profile(prof["x"], prof["b0"], prof["e0"], site.row_half, b_limits,
                               prof["bS"] if site.shield_on else None,
                               prof["eS"] if site.shield_on else None, subtitle=sub),
                    "Shaded band: right-of-way. Dashed red: selected magnetic limits within range."
                    + (" Green: with the shield, in the cross-section through it." if site.shield_on else ""))
            if figs["cross_section"]:
                fig("Corridor cross-section",
                    rf.arrangement([{"name": ln["name"],
                                     "conductors": [(c["x"], c["y"], c["phase"], c["y_att"]) for c in ln["conductors"]]}
                                    for ln in sol["lines"]], site.row_half, bld, walls,
                                   (site.x_min, site.x_max)))
            zg = site.geom.z_center if site.shield_on else 0.0
            g = site.grid(z=zg) if (figs["map_b"] or figs["map_e"] or (figs["shield_maps"] and site.shield_on)) else None
            if figs["map_b"]:
                fig("Magnetic field map (unshielded)",
                    rf.field_map(g["x"], g["y"], g["b0"], g["bS"], "B", "without", conds, None, bld,
                                 site.row_half, log_scale, subtitle=sub))
            if figs["map_e"]:
                fig("Electric field map (unshielded)",
                    rf.field_map(g["x"], g["y"], g["e0"], g["eS"], "E", "without", conds, None, bld,
                                 site.row_half, log_scale, subtitle=sub))
            if figs["shield_maps"] and site.shield_on:
                for q, key in (("B", "b"), ("E", "e")):
                    fig(f"{'Magnetic' if q == 'B' else 'Electric'} field with the shield",
                        rf.field_map(g["x"], g["y"], g[key + "0"], g[key + "S"], q, "with", conds, walls, bld,
                                     site.row_half, log_scale, subtitle=f"{shd['label']} - {shd['model_label']}"),
                        "Same colour scale as the unshielded map.")
                    fig(f"Change in the {'magnetic' if q == 'B' else 'electric'} field caused by the shield",
                        rf.field_map(g["x"], g["y"], g[key + "0"], g[key + "S"], q, "diff", conds, walls, bld,
                                     site.row_half, subtitle=f"{shd['label']} - {shd['model_label']}"),
                        "Blue: reduced. Red: increased (field redistributed around the shield).")
            if figs["receptors"] and sol["receptors"]:
                fig("Building receptors", rf.receptors(sol["receptors"]))
            if figs["field_lines"]:
                zf, mag = 0.0, None
                if site.shield_on and site.physical:
                    zf = 0.0 if site.shield_at(0.0) else float(site.geom.z_center)
                    mag = site.solution(zf)[0]
                cz = site.conductors_at(zf)
                fx, fy, bare = field_lines.potential_grid(cz, (site.x_min, site.x_max), (0.0, site.y_max),
                                                          site.ground_model, site.earth_rho, site.freq)
                fa = bare if mag is None else bare + mag.induced_a(*np.meshgrid(fx, fy))
                fig("Magnetic field lines",
                    rf.field_lines(fx, fy, fa, [(c.x, c.y_sagged, c.phase) for c in cz],
                                   walls if (mag is not None or not site.shield_on) else None, bld,
                                   "the instant wt = 0 of the cycle"
                                   + (", with the currents induced in the shield" if mag is not None else ""),
                                   reference=bare),
                    "Lines of the magnetic field at one instant; arrows give its direction. The lines are "
                    "spaced to show the weak field far from the line too, so their density is not the field "
                    "strength. The RMS magnitude used for compliance is on the field maps.")
            if figs["earth"]:
                env = service.earth_envelope(cfg)
                fig("Earth-return sensitivity",
                    rf.earth_envelope(np.array(env["x"]), np.array(env["free"]), np.array(env["perfect"]),
                                      np.array(env["selected"]) if env["selected"] else None,
                                      env["selected_label"], site.row_half, b_limits))
        twin_png = options.get("twin_png")
        if figs["twin"] and twin_png:
            try:
                raw = base64.b64decode(twin_png.split(",", 1)[-1])
                if raw[:8] == b"\x89PNG\r\n\x1a\n" and len(raw) < 12_000_000:
                    blocks.append({"type": "figure", "title": "3-D digital twin", "png": raw,
                                   "caption": "View captured from the interactive twin."})
            except Exception:
                pass

    user = user or {}
    proj = options.get("project") or {}
    if not isinstance(proj, dict):
        proj = {"name": str(proj)}
    return {
        "title": "EMF assessment report",
        "subtitle": proj.get("description") or "Electric and magnetic fields of overhead transmission lines",
        "project": proj.get("name") or "Untitled project",
        "author": options.get("author") or user.get("name") or "",
        "organisation": options.get("organisation") or user.get("organisation") or "",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "blocks": blocks,
    }


def render(cfg: dict, fmt: str, options: Optional[dict] = None, user: Optional[dict] = None):
    """Returns (bytes, media_type, filename)."""
    options = dict(options or {})
    if fmt == "txt":
        options["with_figures"] = False
    doc = build_doc(cfg, options, user)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in doc["project"])[:40] or "Taki"
    if fmt == "pdf":
        return report.build_pdf(doc), "application/pdf", f"Taki_{safe}_{stamp}.pdf"
    if fmt == "docx":
        return (report.build_docx(doc),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                f"Taki_{safe}_{stamp}.docx")
    if fmt == "txt":
        return report.build_txt(doc).encode("utf-8"), "text/plain; charset=utf-8", f"Taki_{safe}_{stamp}.txt"
    raise ValueError("Unknown report format.")


def preview(cfg: dict, options: Optional[dict] = None, user: Optional[dict] = None) -> dict:
    """The document model without figures (the browser renders it as HTML), plus plain text."""
    opts = dict(options or {})
    opts["with_figures"] = False
    doc = build_doc(cfg, opts, user)
    return {"doc": doc, "text": report.build_txt(doc)}


def ai_context(cfg: dict) -> dict:
    sol = service.solve(cfg)
    shd = sol["shield"]
    std_lines = []
    for r in sol["results"]:
        bits = []
        if r["b"]["limit"] is not None:
            bits.append(f"B {r['b']['value']:.2f}/{r['b']['limit']:g} µT ({r['b']['pct']:.0f}%)")
        if r["e"]["limit"] is not None:
            bits.append(f"E {r['e']['value']:.3f}/{r['e']['limit']:g} kV/m ({r['e']['pct']:.0f}%)")
        std_lines.append(f"{r['name']} ({r['jurisdiction']}; {'exposure limit' if r['kind'] == 'limit' else 'precautionary value'}): "
                         f"{r['overall']} - {', '.join(bits) if bits else 'no applicable limit'}.")
    shield_lines, caveats = [], []
    if shd["on"]:
        shield_lines = [
            f"Configuration: {shd['label']}; model: {shd['model_label']}",
            f"Material: {shd['material']['label']} ({shd['material']['quality']} data), {shd['thickness_mm']:g} mm, "
            f"{'earthed' if shd['grounded'] else 'unearthed'}, {'bonded' if shd['bonded'] else 'unbonded'} seams, "
            f"coverage {shd['coverage_pct']:g}%",
        ]
        head = shd.get("headline")
        if head:
            what = (f"Average field inside {head['where']}" if head["basis"] == "inside"
                    else f"Field at {head['where']}")
            shield_lines.append(f"{what}: B {head['b0']:.3f} -> {head['bS']:.3f} µT ({_chg(head['b_red_pct'])}), "
                                f"E {head['e0']:.4f} -> {head['eS']:.4f} kV/m ({_chg(head['e_red_pct'])})")
        z = shd.get("protected")
        if z:
            shield_lines.append(f"Highest point inside {z['label']}: B {z['b']['max0']:.3f} -> {z['b']['maxS']:.3f} µT")
        shield_lines += [
            f"Peak on the lateral profile: B {sol['peak_b']:.3f} -> {sol['peak_b_shield']:.3f} µT, "
            f"E {sol['peak_e']:.3f} -> {sol['peak_e_shield']:.3f} kV/m",
        ]
        if shd.get("floating_kv"):
            shield_lines.append(f"Induced voltage on the unearthed shield: {shd['floating_kv']:.2f} kV")
        if shd["model"] == "analytical":
            caveats.append("The analytical magnetic shielding figure is an infinite-sheet upper bound, "
                           "not a prediction for a real shield.")
        caveats.append("Shielding is informational and is never a compliance credit; compliance uses "
                       "the unshielded field.")
    for r in sol["results"]:
        if r["needs_verification"]:
            caveats.append(f"The limit values for {r['name']} must be verified against the primary document.")
    return {
        "num_lines": len(sol["lines"]),
        "lines": [f"{ln['name']}: {_line_summary(ln)}" for ln in sol["lines"]],
        "ground_note": sol["corridor"]["ground_note"], "freq_hz": sol["corridor"]["freq"],
        "peak_b_uT": sol["peak_b"], "peak_b_location_m": sol["peak_b_x"], "peak_e_kVm": sol["peak_e"],
        "standard_results": std_lines, "overall_status": sol["overall"],
        "buildings": [
            f"{r['building']} ({r['building_type']}), average over its inside: B {r['b_in_avg_uT']:.3f} µT"
            + (f" -> {r['b_in_avg_shield_uT']:.3f} µT with the shield" if r["barrier_on"] else "")
            + f"; E {r['e_in_avg_kVm']:.4f} kV/m"
            + (f" -> {r['e_in_avg_shield_kVm']:.4f} kV/m with the shield" if r["barrier_on"] else "")
            for r in sol["receptors"]],
        "shield": shield_lines,
        "points": [f"#{p['n']} {p['label']} x={p['x']:.1f} y={p['y']:.1f} z={p['z']:.1f}: "
                   + (f"B {p['b0']:.3f} -> {p['bS']:.3f} µT, E {p['e0']:.4f} -> {p['eS']:.4f} kV/m"
                      if shd["on"] and p["in_shield_length"] else f"B {p['b0']:.3f} µT, E {p['e0']:.4f} kV/m")
                   for p in service.points(cfg)["rows"]],
        "caveats": caveats,
        "references": [references.format_reference_line(references.get(k))
                       for k in ("icnirp2010", "icnirp1998", "krahenbuhl1993", "hasselgren1995", "cigre373")],
    }
