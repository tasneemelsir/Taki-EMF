"""
tools/build_fikry2022.py
=========================
Generates engine/benchmark_data/fikry2022_f1000research.json.

The values below are transcribed from Tables 5 (magnetic field) and 6
(electric field) of:

    Fikry A, Lim SC, Ab Kadir MZA. "EMI radiation of power transmission
    lines in Malaysia" [version 2; peer review: 2 approved].
    F1000Research 2022, 10:1136.
    https://doi.org/10.12688/f1000research.73067.2

Article licence: CC-BY 4.0.
Underlying dataset licence: CC0 1.0 (public domain dedication),
    https://doi.org/10.6084/m9.figshare.16577423.v2

Kept as a generator script rather than a hand-written JSON file so the
transcription can be read as a compact table and diffed against the
source, instead of being buried in JSON punctuation.

RUN:  python3 tools/build_fikry2022.py
"""

import json
import os

# ---------------------------------------------------------------------------
# Transcribed source tables
#
# Row format:
#   (line_type, ground_conducting, phasing,
#    B_under_line, B_row_boundary,      <- Table 5, uT
#    E_under_line, E_row_boundary)      <- Table 6, kV/m
# ---------------------------------------------------------------------------
ROWS = [
    # --- 132 kV double circuit -------------------------------------------
    ("132kV_DC", True,  "untransposed",  4.794284, 0.253069, 0.924003, 0.245560),
    ("132kV_DC", True,  "transposed",    0.545671, 0.624946, 0.154410, 0.177480),
    ("132kV_DC", False, "untransposed",  2.604300, 1.430200, 0.263679, 0.179610),
    ("132kV_DC", False, "transposed",    1.338400, 0.467300, 0.182788, 0.121504),
    # --- 275 kV double circuit -------------------------------------------
    ("275kV_DC", True,  "untransposed",  3.928109, 0.960835, 1.508420, 0.574706),
    ("275kV_DC", True,  "transposed",    0.443016, 1.074408, 0.222091, 0.450741),
    ("275kV_DC", False, "untransposed",  2.088845, 1.494544, 0.394063, 0.305229),
    ("275kV_DC", False, "transposed",    1.263348, 0.636509, 0.276856, 0.181895),
    # --- 132/132 kV quadruple circuit ------------------------------------
    ("132_132kV_QC", True,  "untransposed", 13.620060, 2.978469, 1.127880, 0.367053),
    ("132_132kV_QC", True,  "transposed",    1.130040, 0.340224, 0.354182, 0.319246),
    ("132_132kV_QC", False, "untransposed",  7.289010, 4.670191, 0.321052, 0.211805),
    ("132_132kV_QC", False, "transposed",    1.493262, 0.676831, 0.105488, 0.081465),
    # --- 275/132 kV quadruple circuit ------------------------------------
    ("275_132kV_QC", True,  "untransposed", 10.135390, 2.489524, 1.481490, 0.578090),
    ("275_132kV_QC", True,  "transposed",    0.909531, 0.184360, 0.534335, 0.450279),
    ("275_132kV_QC", False, "untransposed",  5.405135, 3.546732, 0.457699, 0.314460),
    ("275_132kV_QC", False, "transposed",    1.113876, 0.588538, 0.135271, 0.113173),
    # --- 500 kV double circuit -------------------------------------------
    ("500kV_DC", True,  "untransposed", 18.431850, 4.860459, 3.089610, 1.094860),
    ("500kV_DC", True,  "transposed",    2.857379, 4.293753, 0.651354, 0.748960),
    ("500kV_DC", False, "untransposed",  9.693522, 6.762919, 0.724198, 0.539665),
    ("500kV_DC", False, "transposed",    4.852491, 2.516856, 0.414757, 0.232802),
]

LINE_TYPE_LABELS = {
    "132kV_DC": "132 kV double circuit",
    "275kV_DC": "275 kV double circuit",
    "132_132kV_QC": "132/132 kV quadruple circuit",
    "275_132kV_QC": "275/132 kV quadruple circuit",
    "500kV_DC": "500 kV double circuit",
}

# ---------------------------------------------------------------------------
# Tower geometries published in full (Tables 2 and 3).
#
# The remaining three line types have their geometry in the Figshare
# dataset rather than the article body, so they are marked unavailable
# rather than guessed at. Conductor entries:
#   (phase_untransposed, phase_transposed, x_m, y_m, current_A, voltage_kV)
# ---------------------------------------------------------------------------
GEOMETRIES = {
    "275_132kV_QC": {
        "source_table": "Table 2",
        "conductors": [
            ("A1", "A1", -6.0, 43.13, 1232, 275),
            ("B1", "B1", -6.0, 37.58, 1232, 275),
            ("C1", "C1", -6.0, 32.03, 1232, 275),
            ("A2", "C2",  6.0, 43.13, 1232, 275),
            ("B2", "B2",  6.0, 37.58, 1232, 275),
            ("C2", "A2",  6.0, 32.03, 1232, 275),
            ("a1", "c1", -5.2, 24.31,  729, 132),
            ("b1", "b1", -5.2, 20.43,  729, 132),
            ("c1", "a1", -5.2, 16.55,  729, 132),
            ("a2", "a2",  5.2, 24.31,  729, 132),
            ("b2", "b2",  5.2, 20.43,  729, 132),
            ("c2", "c2",  5.2, 16.55,  729, 132),
        ],
    },
    "500kV_DC": {
        "source_table": "Table 3",
        "conductors": [
            ("A1", "A1", -6.2, 47.50, 2309.4, 500),
            ("B1", "B1", -6.2, 36.50, 2309.4, 500),
            ("C1", "C1", -7.0, 25.25, 2309.4, 500),
            ("A2", "C2",  6.2, 47.50, 2309.4, 500),
            ("B2", "B2",  6.2, 36.50, 2309.4, 500),
            ("C2", "A2",  7.0, 25.25, 2309.4, 500),
        ],
    },
}


def build():
    datasets = []
    for line_type, conducting, phasing, b_under, b_row, e_under, e_row in ROWS:
        datasets.append({
            "id": f"{line_type}__{phasing}__{'cond' if conducting else 'noncond'}",
            "line_type": line_type,
            "line_type_label": LINE_TYPE_LABELS[line_type],
            "phasing": phasing,
            "ground_conducting": conducting,
            "points": [
                {
                    "location": "under_line",
                    "distance_m": 0.0,
                    "distance_known": True,
                    "b_field_uT": b_under,
                    "e_field_kVm": e_under,
                },
                {
                    "location": "row_boundary",
                    "distance_m": None,
                    "distance_known": False,
                    "b_field_uT": b_row,
                    "e_field_kVm": e_row,
                },
            ],
        })

    geometries = {}
    for lt, label in LINE_TYPE_LABELS.items():
        if lt in GEOMETRIES:
            g = GEOMETRIES[lt]
            geometries[lt] = {
                "available": True,
                "source_table": g["source_table"],
                "conductors": [
                    {
                        "phase_untransposed": p_u,
                        "phase_transposed": p_t,
                        "x_m": x,
                        "y_m": y,
                        "current_A": i,
                        "voltage_kV": v,
                    }
                    for p_u, p_t, x, y, i, v in g["conductors"]
                ],
            }
        else:
            geometries[lt] = {
                "available": False,
                "reason": (
                    "Conductor geometry for this line type is published in the "
                    "Figshare underlying dataset (doi:10.6084/m9.figshare.16577423.v2) "
                    "rather than in the article body. Not transcribed here — "
                    "obtain from the dataset before using this configuration "
                    "for like-for-like comparison."
                ),
            }

    doc = {
        "schema_version": 1,
        "id": "fikry2022_f1000research",
        "title": "EMI radiation of power transmission lines in Malaysia",
        "data_type": "simulated",
        "citation": {
            "authors": "Fikry A, Lim SC, Ab Kadir MZA",
            "title": "EMI radiation of power transmission lines in Malaysia",
            "container": "F1000Research",
            "version": "version 2; peer review: 2 approved",
            "year": 2022,
            "volume": "10",
            "article_number": "1136",
            "doi": "10.12688/f1000research.73067.2",
            "url": "https://doi.org/10.12688/f1000research.73067.2",
            "article_license": "CC-BY 4.0",
            "data_doi": "10.6084/m9.figshare.16577423.v2",
            "data_license": "CC0 1.0 (public domain dedication)",
        },
        "method": {
            "solver": "EMFACDC v2.0 (ITU-T Recommendation K.90, Appendix II)",
            "solver_url": "https://www.itu.int/rec/T-REC-K.90-201905-I!Amd1/en",
            "b_field_method": "Complex phasor superposition of infinite "
                              "straight-conductor Biot-Savart contributions",
            "e_field_method": "Method of images with Maxwell potential "
                              "coefficient matrix",
            "measurement_height_m": 1.0,
            "centreline_x_m": 0.0,
            "current_basis": "rated current for each conductor",
            "plotted_domain_x_m": [-30.0, 30.0],
            "plotted_domain_y_m": [0.0, 40.0],
            "step_m": 0.1,
        },
        "provenance_notes": [
            "SIMULATED, NOT MEASURED. These values come from a numerical "
            "solver, so comparing Taki against them is code-to-code "
            "verification (does Taki's implementation agree with an "
            "established ITU-referenced tool?), not validation against "
            "physical reality.",
            "The ROW boundary distance is not stated in the article body; it "
            "is referred to the Suruhanjaya Tenaga wayleave values per line "
            "type. Every row_boundary point therefore has distance_m = null "
            "and must not be plotted against a distance axis until that "
            "figure is supplied.",
            "The article cites IEEE Std C37.1 for the 1 m measurement height. "
            "C37.1 covers SCADA and automatic control systems; IEEE Std 644 "
            "is the standard normally cited for power-line field measurement "
            "height. The 1 m height itself is conventional and consistent "
            "with Taki's own 1 m profile.",
            "Conductor geometry is transcribed in full for two of the five "
            "line types only (Tables 2 and 3). The other three are available "
            "in the Figshare dataset.",
            "Ground condition is a modelled binary (conducting / "
            "non-conducting) in the source. Taki's physics engine assumes a "
            "perfectly conducting ground plane for the E-field method of "
            "images, so the 'conducting' rows are the like-for-like "
            "comparison set.",
        ],
        # Determined empirically by running Taki against the reconstructed
        # geometries in this source. Recorded here so the Validation tab can
        # surface WHY a discrepancy exists rather than just reporting an
        # unexplained error metric.
        # Determined empirically by running Taki against the reconstructed
        # geometries in this source, with earth.py's ground models applied.
        "comparison_caveats": [
            {
                "id": "sqrt2_scale_factor",
                "affects": "B",
                "severity": "high",
                "status": "unresolved",
                "summary": "Taki reads high by exactly sqrt(2) against this "
                           "source, universally.",
                "detail": "Across all four published geometries x both ground "
                          "conditions (8 independent comparisons), the ratio "
                          "Taki/reference is 1.4142 to four decimal places, "
                          "independent of geometry, phasing and ground model. "
                          "This is a pure convention constant, not a geometry "
                          "or physics error. Taki computes the resultant as "
                          "sqrt(|Bx|^2 + |By|^2) from RMS current phasors, "
                          "which is the standard RMS resultant used for ICNIRP "
                          "comparison. The reference uses the National Grid "
                          "in-phase / out-of-phase decomposition. The "
                          "discrepancy has NOT been resolved and Taki's "
                          "scaling has deliberately NOT been altered: "
                          "rescaling a compliance tool on an unproven "
                          "inference would be worse than a documented open "
                          "question. Resolve by working through the reference "
                          "solver's normalisation before quoting absolute "
                          "agreement with this source.",
            },
            {
                "id": "ground_model_validated",
                "affects": "B",
                "severity": "none",
                "status": "resolved",
                "summary": "Earth-return model VALIDATED against this source.",
                "detail": "With earth.py applied, the ratio between "
                          "conducting-ground and non-conducting-ground results "
                          "matches the reference to four decimal places in all "
                          "four cases (1.9015, 0.5888, 1.8751, 0.8165). Taki's "
                          "PERFECT_CONDUCTOR model corresponds to the "
                          "reference's conducting-ground rows and FREE_SPACE "
                          "to its non-conducting rows.",
            },
            {
                "id": "transposition_benefit_RETRACTED",
                "affects": "B",
                "severity": "none",
                "status": "retracted",
                "summary": "RETRACTED: Taki does NOT understate the benefit of "
                           "transposition.",
                "detail": "An earlier analysis, made before the earth-return "
                          "model existed, concluded that Taki understated the "
                          "field reduction achieved by transposed phasing. "
                          "That was an artifact of comparing a free-space Taki "
                          "result against conducting-ground reference values. "
                          "With the ground model applied the transposition "
                          "ratios agree exactly. Retained here so the "
                          "incorrect conclusion is not repeated.",
            },
            {
                "id": "conductor_radius_unpublished",
                "affects": "E",
                "severity": "medium",
                "status": "open",
                "summary": "Conductor radius and bundling are not published in "
                           "this source, and E field depends on both.",
                "detail": "Taki falls back to conductor_radius_m = 0.015 m "
                          "when no radius is supplied. The reference tables "
                          "give no radius or bundle configuration, though a "
                          "500 kV line would normally be bundled, giving a "
                          "much larger equivalent radius. Obtain the radius "
                          "from the Figshare dataset before quoting E-field "
                          "agreement.",
            },
            {
                "id": "e_field_ground_model",
                "affects": "E",
                "severity": "low",
                "status": "open",
                "summary": "Compare E only against the conducting-ground rows.",
                "detail": "Taki's E-field solver uses the method of images, "
                          "which assumes a perfectly conducting ground plane. "
                          "The reference's non-conducting rows model a "
                          "different assumption and are not like-for-like.",
            },
            {
                "id": "phase_convention_ruled_out",
                "affects": "B",
                "severity": "none",
                "status": "resolved",
                "summary": "Phase-angle convention is NOT a source of "
                           "discrepancy.",
                "detail": "Taki uses A=0, B=-120, C=+120; the reference uses "
                          "A=0, B=+120, C=+240. Tested directly: computed |B| "
                          "is identical under both, because reversing the "
                          "phase sequence conjugates the entire current set "
                          "and leaves the magnitude unchanged.",
            },
        ],
        "tower_geometries": geometries,
        "datasets": datasets,
    }
    return doc


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(os.path.dirname(here), "engine", "benchmark_data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "fikry2022_f1000research.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(build(), fh, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}")
    doc = build()
    print(f"  {len(doc['datasets'])} configurations, "
          f"{sum(len(d['points']) for d in doc['datasets'])} reference points")
