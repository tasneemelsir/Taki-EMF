"""
standards.py
============
Exposure-standard registry and compliance evaluation for Taki.

WHAT CHANGED IN v4 (and why)
----------------------------
The registry was re-checked against sources that could actually be read:

  * "MS 2332-1:2009 (Malaysia), 100 uT" could NOT be confirmed against any
    primary or secondary source, so it is no longer presented as a verified
    national standard. Malaysian practice is represented by an entry on the
    ICNIRP 1998 public reference levels (100 uT, 5 kV/m at 50 Hz), flagged
    `needs_verification` - confirm the governing document with Suruhanjaya
    Tenaga / the Ministry of Health before certifying anything. Scenario files
    that reference the old id still load (see ALIASES).
  * "Slovenia / Italy (residential), 10 uT + 0.5 kV/m" merged two different
    regimes. Slovenia applies 10 uT and 0.5 kV/m to NEW or modified sources
    near homes, schools, hospitals and similar. Italy applies a 100 uT / 5 kV/m
    exposure limit, a 10 uT "attention value" (24 h median) and a 3 uT "quality
    objective" for new lines and new buildings - it has no 0.5 kV/m rule.
    They are now separate entries.
  * Reference levels depend on frequency. ICNIRP 1998 (and the EU
    Recommendation built on it) scale as 1/f, so 100 uT at 50 Hz is 83.3 uT at
    60 Hz; ICNIRP 2010's electric-field level is 250/f kV/m, i.e. 4.17 kV/m at
    60 Hz. Limits are now evaluated at the system frequency.
  * IEEE C95.6-2002 and precautionary values from Switzerland and the
    Netherlands were added, because consultancy reports usually tabulate them.

Each entry carries a `kind`:
    "limit"          a reference level / legal exposure limit
    "precautionary"  a stricter planning or attention value. Exceeding one is
                     not a breach of an exposure limit; it is a planning flag.

The limit values are an engineering convenience, not a legal authority. Verify
against the current text of the standard before issuing a certificate.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

PASS = "PASS"
MARGINAL = "MARGINAL"
FAIL = "FAIL"
NOT_ASSESSED = "NOT_ASSESSED"

#: Fraction of the limit above which a passing result is flagged MARGINAL.
#: A reporting convenience, not a threshold defined by any standard.
MARGINAL_FRACTION = 0.75

LimitFn = Callable[[float], Optional[float]]


def _const(v: Optional[float]) -> LimitFn:
    return lambda f: v


def _inv_f(k: float) -> LimitFn:
    """Limit of the form k / f (f in Hz)."""
    return lambda f: k / max(float(f), 1e-9)


def _icnirp2010_e_public(f: float) -> float:
    # ICNIRP 2010 Table 4: 5 kV/m for 25-50 Hz, 2.5e2 / f kV/m for 50-400 Hz.
    return 5.0 if f <= 50.0 else 250.0 / f


def _icnirp2010_e_occ(f: float) -> float:
    # ICNIRP 2010 Table 3: 5e2 / f kV/m for 25 Hz - 3 kHz.
    return 500.0 / f


@dataclass(frozen=True)
class Standard:
    id: str
    name: str
    jurisdiction: str
    year: int
    b_fn: LimitFn
    e_fn: LimitFn
    population: str = "general public"
    kind: str = "limit"                 # "limit" | "precautionary"
    source: str = ""
    url: str = ""
    notes: str = ""
    needs_verification: bool = False

    def b_limit(self, freq_hz: float = 50.0) -> Optional[float]:
        return self.b_fn(freq_hz)

    def e_limit(self, freq_hz: float = 50.0) -> Optional[float]:
        return self.e_fn(freq_hz)

    # 50 Hz values, kept as attributes for code that predates frequency scaling.
    @property
    def b_limit_uT(self) -> Optional[float]:
        return self.b_fn(50.0)

    @property
    def e_limit_kVm(self) -> Optional[float]:
        return self.e_fn(50.0)


_ICNIRP_2010_SRC = ("ICNIRP. Guidelines for limiting exposure to time-varying electric and "
                    "magnetic fields (1 Hz to 100 kHz). Health Physics 99(6):818-836, 2010. "
                    "doi:10.1097/HP.0b013e3181f06c86")
_ICNIRP_1998_SRC = ("ICNIRP. Guidelines for limiting exposure to time-varying electric, magnetic "
                    "and electromagnetic fields (up to 300 GHz). Health Physics 74(4):494-522, 1998.")
_BFS_URL = ("https://www.bfs.de/EN/topics/emf/expansion-grid/protection/limit-values-europes/"
            "limit-values-europe.html")

_STANDARDS: Dict[str, Standard] = {s.id: s for s in [
    Standard(
        id="MY_ICNIRP_1998", name="Malaysia (ICNIRP 1998 basis)", jurisdiction="Malaysia",
        year=1998, b_fn=_inv_f(5000.0), e_fn=_inv_f(250.0),
        source=_ICNIRP_1998_SRC + " Applied in Malaysian practice (Ministry of Health / "
               "Suruhanjaya Tenaga).",
        notes="100 uT and 5 kV/m at 50 Hz. Earlier versions of Taki labelled this entry "
              "'MS 2332-1:2009'; that standard number could not be confirmed against a primary "
              "source, so the entry is now named for the guideline its values come from. Confirm "
              "the governing Malaysian document with the regulator before certification.",
        needs_verification=True),
    Standard(
        id="ICNIRP_2010", name="ICNIRP 2010", jurisdiction="International", year=2010,
        b_fn=_const(200.0), e_fn=_icnirp2010_e_public,
        source=_ICNIRP_2010_SRC,
        url="https://www.icnirp.org/en/publications/article/lf-guidelines-2010.html",
        notes="General-public reference levels: 200 uT (25-400 Hz); 5 kV/m at 50 Hz, falling as "
              "250/f above 50 Hz (4.17 kV/m at 60 Hz). Reference levels are screening values: "
              "exceeding one does not by itself show the basic restriction is exceeded."),
    Standard(
        id="ICNIRP_1998", name="ICNIRP 1998", jurisdiction="International (superseded)",
        year=1998, b_fn=_inv_f(5000.0), e_fn=_inv_f(250.0),
        source=_ICNIRP_1998_SRC,
        notes="General-public reference levels 5/f uT and 250/f V/m (f in kHz): 100 uT and "
              "5 kV/m at 50 Hz, 83.3 uT and 4.17 kV/m at 60 Hz. Superseded by ICNIRP 2010 for "
              "1 Hz-100 kHz but still the basis of many national frameworks."),
    Standard(
        id="EU_1999_519_EC", name="EU Recommendation 1999/519/EC", jurisdiction="European Union",
        year=1999, b_fn=_inv_f(5000.0), e_fn=_inv_f(250.0),
        source="Council Recommendation 1999/519/EC of 12 July 1999 on the limitation of exposure "
               "of the general public to electromagnetic fields (0 Hz to 300 GHz).",
        url=_BFS_URL,
        notes="Adopts the ICNIRP 1998 public reference levels (100 uT, 5 kV/m at 50 Hz). It was "
              "not revised to follow ICNIRP's 2010 increase to 200 uT."),
    Standard(
        id="IEEE_C95_6_2002", name="IEEE C95.6-2002 (public)", jurisdiction="International (IEEE)",
        year=2002, b_fn=_const(904.0), e_fn=_const(5.0),
        source="IEEE Std C95.6-2002, IEEE Standard for Safety Levels with Respect to Human "
               "Exposure to Electromagnetic Fields, 0-3 kHz.",
        notes="General-public maximum permissible exposure: 0.904 mT (20-759 Hz) and 5 kV/m. "
              "The standard allows 10 kV/m within power-line rights-of-way. Values transcribed "
              "from secondary summaries - check the standard text.",
        needs_verification=True),
    Standard(
        id="SI_ZONE_I", name="Slovenia (new sources, protected areas)", jurisdiction="Slovenia",
        year=1996, b_fn=_const(10.0), e_fn=_const(0.5), kind="precautionary",
        source="Decree on Electromagnetic Radiation in the Natural and Living Environment "
               "(Slovenia, 1996, revised 2004), as summarised by the German Federal Office for "
               "Radiation Protection (BfS).",
        url=_BFS_URL,
        notes="10 uT and 0.5 kV/m for NEW or modified installations near homes, schools, "
              "kindergartens, hospitals, playgrounds and parks. Existing sources and other "
              "areas: 100 uT and 10 kV/m."),
    Standard(
        id="IT_ATTENTION", name="Italy - attention value", jurisdiction="Italy", year=2003,
        b_fn=_const(10.0), e_fn=_const(5.0), kind="precautionary",
        source="Decreto del Presidente del Consiglio dei Ministri, 8 July 2003 (power lines, "
               "50 Hz).",
        url=_BFS_URL,
        notes="10 uT attention value, defined as the 24-hour median, for homes, schools and "
              "places occupied 4 hours a day or more. The exposure limit is 100 uT and 5 kV/m. "
              "Taki compares the modelled peak against 10 uT, which is conservative relative "
              "to a 24-hour median."),
    Standard(
        id="IT_QUALITY", name="Italy - quality objective", jurisdiction="Italy", year=2003,
        b_fn=_const(3.0), e_fn=_const(5.0), kind="precautionary",
        source="Decreto del Presidente del Consiglio dei Ministri, 8 July 2003 (power lines, "
               "50 Hz).",
        url=_BFS_URL,
        notes="3 uT quality objective (24-hour median) for new lines near sensitive places and "
              "for new buildings near existing lines."),
    Standard(
        id="CH_ONIR", name="Switzerland - installation limit", jurisdiction="Switzerland",
        year=1999, b_fn=_const(1.0), e_fn=_const(5.0), kind="precautionary",
        source="Ordinance relating to Protection from Non-Ionising Radiation (ONIR / NISV), "
               "23 December 1999.",
        url=_BFS_URL,
        notes="1 uT precautionary installation limit at places of sensitive use for new "
              "installations (in force since 1 February 2000). Immission limits for everyone: "
              "100 uT and 5 kV/m."),
    Standard(
        id="NL_ADVISORY", name="Netherlands - advisory (children)", jurisdiction="Netherlands",
        year=2005, b_fn=_const(0.4), e_fn=_const(None), kind="precautionary",
        source="Dutch ministerial advice on overhead power lines (2005, clarified 2008).",
        url=_BFS_URL,
        notes="0.4 uT annual-average advisory value for new situations where children stay for "
              "long periods. Not an exposure limit; it is a planning recommendation, and it is "
              "an annual average rather than a peak."),
    Standard(
        id="ICNIRP_2010_OCC", name="ICNIRP 2010 (occupational)", jurisdiction="International",
        year=2010, b_fn=_const(1000.0), e_fn=_icnirp2010_e_occ, population="occupational",
        source=_ICNIRP_2010_SRC,
        url="https://www.icnirp.org/en/publications/article/lf-guidelines-2010.html",
        notes="Occupational reference levels: 1 mT (25-300 Hz) and 500/f kV/m (10 kV/m at "
              "50 Hz, 8.33 kV/m at 60 Hz). Workers under a managed exposure regime only - do "
              "not apply to residential or public receptors."),
    Standard(
        id="ICNIRP_1998_OCC", name="ICNIRP 1998 (occupational)",
        jurisdiction="International (superseded)", year=1998,
        b_fn=_inv_f(25000.0), e_fn=_inv_f(500.0), population="occupational",
        source=_ICNIRP_1998_SRC,
        notes="Occupational reference levels 25/f uT and 500/f V/m (f in kHz): 500 uT and "
              "10 kV/m at 50 Hz."),
    Standard(
        id="IEEE_C95_6_CONTROLLED", name="IEEE C95.6-2002 (controlled environment)",
        jurisdiction="International (IEEE)", year=2002,
        b_fn=_const(2710.0), e_fn=_const(20.0), population="occupational",
        source="IEEE Std C95.6-2002, IEEE Standard for Safety Levels with Respect to Human "
               "Exposure to Electromagnetic Fields, 0-3 kHz.",
        notes="Controlled-environment maximum permissible exposure: 2.71 mT and 20 kV/m. Values "
              "transcribed from secondary summaries - check the standard text.",
        needs_verification=True),
]}

#: Old ids -> current ids, so scenario files saved by earlier versions still load.
ALIASES = {
    "MS_2332_1_2009": "MY_ICNIRP_1998",
    "SI_IT_RESIDENTIAL": "SI_ZONE_I",
    "icnirp-public": "ICNIRP_2010",
    "icnirp-occ": "ICNIRP_2010_OCC",
    "ieee-public": "IEEE_C95_6_2002",
}

#: Shown by default: the Malaysian basis and the current international benchmark.
#: Reporting only the more permissive of the two is how a false PASS gets issued.
DEFAULT_STANDARD_IDS = ["MY_ICNIRP_1998", "ICNIRP_2010"]


def resolve_id(standard_id: str) -> str:
    return ALIASES.get(standard_id, standard_id)


def get_standards() -> Dict[str, Standard]:
    return dict(_STANDARDS)


def get_standard(standard_id: str) -> Standard:
    return _STANDARDS[resolve_id(standard_id)]


def public_standard_ids() -> List[str]:
    return [s.id for s in _STANDARDS.values() if s.population == "general public"]


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
@dataclass
class QuantityResult:
    quantity: str            # "B" or "E"
    value: float
    limit: Optional[float]
    status: str
    unit: str

    @property
    def fraction_of_limit(self) -> Optional[float]:
        if self.limit is None or self.limit <= 0:
            return None
        return self.value / self.limit

    @property
    def percent_of_limit(self) -> Optional[float]:
        frac = self.fraction_of_limit
        return None if frac is None else frac * 100.0

    @property
    def headroom_percent(self) -> Optional[float]:
        frac = self.fraction_of_limit
        return None if frac is None else (1.0 - frac) * 100.0


@dataclass
class ComplianceResult:
    standard: Standard
    b: QuantityResult
    e: QuantityResult

    @property
    def overall(self) -> str:
        statuses = [q.status for q in (self.b, self.e) if q.status != NOT_ASSESSED]
        if not statuses:
            return NOT_ASSESSED
        for worst in (FAIL, MARGINAL):
            if worst in statuses:
                return worst
        return PASS

    @property
    def is_compliant(self) -> bool:
        return self.overall in (PASS, MARGINAL)

    @property
    def governing(self) -> Optional[QuantityResult]:
        """The quantity using the larger share of its limit (B or E)."""
        qs = [q for q in (self.b, self.e) if q.fraction_of_limit is not None]
        return max(qs, key=lambda q: q.fraction_of_limit) if qs else None


def _classify(value: float, limit: Optional[float], quantity: str, unit: str) -> QuantityResult:
    if limit is None:
        return QuantityResult(quantity, value, None, NOT_ASSESSED, unit)
    if value > limit:
        status = FAIL
    elif value >= limit * MARGINAL_FRACTION:
        status = MARGINAL
    else:
        status = PASS
    return QuantityResult(quantity, value, limit, status, unit)


def evaluate(peak_b_uT: float, peak_e_kVm: float,
             standard_ids: Optional[List[str]] = None,
             freq_hz: float = 50.0) -> List[ComplianceResult]:
    """
    Evaluate peak field values against one or more standards at `freq_hz`.
    Unknown ids are skipped, so a scenario saved against a later registry
    still loads. Duplicate ids (after alias resolution) are assessed once.
    """
    ids = standard_ids if standard_ids is not None else DEFAULT_STANDARD_IDS
    results, seen = [], set()
    for sid in ids:
        sid = resolve_id(sid)
        std = _STANDARDS.get(sid)
        if std is None or sid in seen:
            continue
        seen.add(sid)
        results.append(ComplianceResult(
            standard=std,
            b=_classify(peak_b_uT, std.b_limit(freq_hz), "B", "uT"),
            e=_classify(peak_e_kVm, std.e_limit(freq_hz), "E", "kV/m"),
        ))
    return results


def overall_status(results: List[ComplianceResult]) -> str:
    """Worst case across every standard assessed. Deliberately pessimistic."""
    statuses = [r.overall for r in results if r.overall != NOT_ASSESSED]
    if not statuses:
        return NOT_ASSESSED
    for worst in (FAIL, MARGINAL):
        if worst in statuses:
            return worst
    return PASS


def binding_standard(results: List[ComplianceResult]) -> Optional[ComplianceResult]:
    """The standard imposing the tightest B-field constraint (kept for older callers)."""
    with_b = [r for r in results if r.b.limit is not None]
    if not with_b:
        return None
    return max(with_b, key=lambda r: r.b.fraction_of_limit or 0.0)


def governing(results: List[ComplianceResult]) -> Tuple[Optional[ComplianceResult],
                                                         Optional[QuantityResult]]:
    """
    The (standard, quantity) pair using the largest share of its limit across
    BOTH fields. The old `binding_standard` looked at B only, so a case governed
    by the electric field (e.g. 0.9 kV/m against 0.5 kV/m) reported a comfortable
    magnetic margin on the dashboard while failing on E.
    """
    best, best_q, best_f = None, None, -1.0
    for r in results:
        q = r.governing
        if q is not None and q.fraction_of_limit > best_f:
            best, best_q, best_f = r, q, q.fraction_of_limit
    return best, best_q


def summary_line(results: List[ComplianceResult]) -> str:
    if not results:
        return "Compliance: no standard selected."
    parts = []
    for r in results:
        bits = []
        if r.b.limit is not None:
            bits.append(f"B {r.b.value:.2f}/{r.b.limit:.4g} uT")
        if r.e.limit is not None:
            bits.append(f"E {r.e.value:.2f}/{r.e.limit:.3g} kV/m")
        detail = ", ".join(bits) if bits else "no applicable limit"
        parts.append(f"{r.standard.name}: {r.overall} ({detail})")
    return " | ".join(parts)
