"""
references.py
=============
Taki's research and reference library: standards, field-calculation methods,
shielding theory, mitigation practice and the sources behind the empirical
shielding percentages.

Every entry records WHAT KIND of record it is (`verification`):

    standard        a standard, guideline or regulation
    journal         a peer-reviewed paper
    textbook        a book
    org-publication a report by a standards body, utility group or agency
    dataset         published data bundled with Taki (see benchmarks.py)
    web             an engineering web page or patent. These back the original
                    Taki empirical percentages and are the weakest sources here.

DOIs are included only where they are known with confidence; an empty DOI means
"look it up", not "there is none". Nothing here is invented, and nothing should
be added without checking the source.
"""

from typing import Dict, List, Optional

TOPICS = ["Exposure standards", "Field calculation", "Shielding theory",
          "Mitigation practice", "Measurement", "Validation data", "Health review",
          "Empirical shielding estimates"]


def _r(id, title, authors, year, venue, topic, verification, findings, method="", materials="",
       freq="Power frequency", url="", doi="", used_for=""):
    return {"id": id, "title": title, "authors": authors, "year": str(year), "venue": venue,
            "publisher": venue, "topic": topic, "category": topic, "verification": verification,
            "findings": findings, "note": findings, "method": method, "materials": materials,
            "freq_range": freq, "url": url, "doi": doi, "used_for": used_for}


LIBRARY: List[Dict[str, str]] = [
    # ---------------------------------------------------------------- standards
    _r("icnirp2010",
       "Guidelines for limiting exposure to time-varying electric and magnetic fields (1 Hz to 100 kHz)",
       "International Commission on Non-Ionizing Radiation Protection", 2010,
       "Health Physics 99(6):818-836", "Exposure standards", "standard",
       "General-public reference levels at 50 Hz: 5 kV/m and 200 uT. Occupational: 10 kV/m and "
       "1 mT. The electric-field level falls as 250/f above 50 Hz.",
       method="Guideline / reference levels", freq="1 Hz - 100 kHz",
       url="https://www.icnirp.org/en/publications/article/lf-guidelines-2010.html",
       doi="10.1097/HP.0b013e3181f06c86", used_for="Standards registry (ICNIRP 2010 entries)."),
    _r("icnirp1998",
       "Guidelines for limiting exposure to time-varying electric, magnetic and electromagnetic fields (up to 300 GHz)",
       "International Commission on Non-Ionizing Radiation Protection", 1998,
       "Health Physics 74(4):494-522", "Exposure standards", "standard",
       "General-public reference levels 5/f uT and 250/f V/m (f in kHz): 100 uT and 5 kV/m at "
       "50 Hz. Still the basis of the EU Recommendation and of many national rules.",
       method="Guideline / reference levels", freq="up to 300 GHz",
       used_for="Standards registry (ICNIRP 1998, EU and Malaysia entries)."),
    _r("eu1999", "Council Recommendation 1999/519/EC on the limitation of exposure of the general "
       "public to electromagnetic fields (0 Hz to 300 GHz)", "Council of the European Union", 1999,
       "Official Journal of the European Communities L 199", "Exposure standards", "standard",
       "Adopts the ICNIRP 1998 public reference levels. Not revised after ICNIRP 2010.",
       freq="0 Hz - 300 GHz", used_for="Standards registry (EU entry)."),
    _r("ieee-c95-6", "IEEE Standard for Safety Levels with Respect to Human Exposure to "
       "Electromagnetic Fields, 0-3 kHz", "IEEE International Committee on Electromagnetic Safety",
       2002, "IEEE Std C95.6-2002", "Exposure standards", "standard",
       "General public: 0.904 mT and 5 kV/m (10 kV/m on power-line rights-of-way). Controlled "
       "environment: 2.71 mT and 20 kV/m.", freq="0 - 3 kHz",
       url="https://standards.ieee.org/ieee/C95.6/2054/",
       used_for="Standards registry (IEEE entries, flagged to verify)."),
    _r("bfs-europe", "European limit values and regulations for static and low-frequency fields",
       "Bundesamt fur Strahlenschutz (German Federal Office for Radiation Protection)", "n.d.",
       "BfS web publication", "Exposure standards", "org-publication",
       "Country-by-country summary: Italy (100 uT limit, 3 uT quality objective), Slovenia "
       "(10 uT and 0.5 kV/m for new sources near sensitive areas), Switzerland (1 uT "
       "installation limit), the Netherlands (0.4 uT advisory).",
       url="https://www.bfs.de/EN/topics/emf/expansion-grid/protection/limit-values-europes/limit-values-europe.html",
       used_for="Standards registry (precautionary entries)."),
    # --------------------------------------------------------- field calculation
    _r("deri1981", "The Complex Ground Return Plane: A Simplified Model for Homogeneous and "
       "Multi-Layer Earth Return", "A. Deri, G. Tevan, A. Semlyen, A. Castanheira", 1981,
       "IEEE Transactions on Power Apparatus and Systems PAS-100(8):3686-3693",
       "Field calculation", "journal",
       "Earth return represented by an image at complex depth p = sqrt(rho / (j w mu0)).",
       method="Complex-image method", used_for="Finite-resistivity ground model (earth.py)."),
    _r("epri-redbook", "EPRI AC Transmission Line Reference Book - 200 kV and Above, Third Edition",
       "Electric Power Research Institute", 2005, "EPRI, Palo Alto", "Field calculation",
       "org-publication",
       "Reference methods for electric and magnetic fields of overhead lines: potential "
       "coefficients, images, bundle equivalent radius, corridor field management.",
       method="Engineering reference", materials="Conductors",
       used_for="Maxwell potential-coefficient E-field method; bundle equivalent radius."),
    _r("olsen1992", "Characteristics of low frequency electric and magnetic fields in the vicinity "
       "of electric power lines", "R. G. Olsen, P. S. Wong", 1992,
       "IEEE Transactions on Power Delivery 7(4):2046-2055", "Field calculation", "journal",
       "Shows when quasi-static line-source models with images are adequate for power-line "
       "fields, and how the earth affects the electric and magnetic fields differently.",
       method="Quasi-static analysis", used_for="Basis for the 2-D quasi-static line model."),
    _r("itu-k90", "Recommendation ITU-T K.90: Evaluation techniques and working procedures for "
       "compliance with exposure limits of network operator personnel to power-frequency "
       "electromagnetic fields", "International Telecommunication Union", 2018, "ITU-T Series K",
       "Field calculation", "standard",
       "Calculation procedures and the EMFACDC reference software used by Fikry et al. (2022).",
       url="https://www.itu.int/rec/T-REC-K.90", used_for="Code-to-code verification target."),
    _r("ng-3phase", "How to calculate the magnetic field from a three-phase circuit",
       "National Grid EMF (emfs.info)", 2014, "emfs.info", "Field calculation", "org-publication",
       "In-phase / out-of-phase decomposition of the magnetic field of a three-phase circuit; "
       "equivalent to the complex-phasor sum used here.",
       url="https://www.emfs.info/", used_for="Phasor superposition of phase currents."),
    # --------------------------------------------------------- shielding theory
    _r("schelkunoff1943", "Electromagnetic Waves", "S. A. Schelkunoff", 1943,
       "D. Van Nostrand, New York", "Shielding theory", "textbook",
       "Origin of the shielding-effectiveness decomposition SE = absorption + reflection + "
       "multiple-reflection correction (transmission-line analogy).",
       method="Analytical", materials="Conductive sheets", freq="Broadband",
       used_for="Analytical (infinite-sheet) shielding model."),
    _r("ott2009", "Electromagnetic Compatibility Engineering", "H. W. Ott", 2009,
       "John Wiley & Sons", "Shielding theory", "textbook",
       "Near-field electric and magnetic reflection-loss formulas, absorption loss and "
       "aperture leakage for practical shields.",
       method="Analytical near-field formulas", materials="Metals, meshes, gaskets", freq="Broadband",
       used_for="Analytical (infinite-sheet) shielding model; material properties."),
    _r("celozzi2008", "Electromagnetic Shielding", "S. Celozzi, R. Araneo, G. Lovat", 2008,
       "Wiley-IEEE Press", "Shielding theory", "textbook",
       "Low-frequency magnetic shielding by conductive and ferromagnetic plates, finite-size "
       "effects, and numerical methods for shields.",
       method="Analytical and numerical", materials="Conductive and ferromagnetic sheets",
       freq="DC to RF", used_for="Background for the physical finite-barrier model."),
    _r("krahenbuhl1993", "Thin layers in electrical engineering. Example of shell models in "
       "analysing eddy-currents by boundary and finite element methods",
       "L. Krahenbuhl, D. Muller", 1993, "IEEE Transactions on Magnetics 29(2):1450-1455",
       "Shielding theory", "journal",
       "Thin-shell relations linking the jumps of tangential E and H across a conducting, "
       "permeable sheet, valid from thin to several skin depths thick.",
       method="Thin-shell boundary-element / finite-element model",
       materials="Conductive and ferromagnetic sheets",
       used_for="Sheet relations in the physical magnetic shield solver (shield_bem.py)."),
    _r("hasselgren1995", "Geometrical aspects of magnetic shielding at extremely low frequencies",
       "L. Hasselgren, J. Luomi", 1995,
       "IEEE Transactions on Electromagnetic Compatibility 37(3):409-420", "Shielding theory",
       "journal",
       "Shows that at power frequency the shape and size of a shield and the position of the "
       "source dominate its performance: open and finite shields behave very differently from "
       "the infinite-sheet formulas.",
       method="Analytical and numerical", materials="Conductive and ferromagnetic shields",
       freq="Extremely low frequency",
       used_for="Why the infinite-sheet formula over-predicts for a finite barrier."),
    # ------------------------------------------------------ mitigation practice
    _r("cigre373", "Mitigation techniques of power-frequency magnetic fields originated from "
       "electric power systems", "CIGRE Working Group C4.204", 2009, "CIGRE Technical Brochure 373",
       "Mitigation practice", "org-publication",
       "Survey of mitigation: phase arrangement, compaction, passive and active loops, "
       "conductive and ferromagnetic plates, with achievable reduction factors.",
       method="Engineering survey", materials="Aluminium, copper, steel, loops",
       used_for="Context for barrier, loop and enclosure options."),
    _r("memari1996", "Mitigation of magnetic field near power lines", "A. R. Memari, W. Janischewskyj",
       1996, "IEEE Transactions on Power Delivery 11(3):1577-1586", "Mitigation practice", "journal",
       "Compares ways of lowering the field near overhead lines, including passive shield loops "
       "strung parallel to the phase conductors, in which the line's own field induces the "
       "compensating current.",
       method="Analytical field calculation", materials="Line conductors used as loops",
       used_for="Passive loop along the line (Shield > Passive loop)."),
    _r("pettersson1996", "Principles in transmission line magnetic field reduction", "P. Pettersson",
       1996, "IEEE Transactions on Power Delivery 11(3):1587-1592", "Mitigation practice", "journal",
       "Sets out the principles behind field reduction at the line: phase splitting and "
       "arrangement, compaction, and screening conductors.",
       method="Analytical", used_for="Line-side measures listed under Compare > Measures."),
    _r("yamazaki2000", "Requirements for power line magnetic field mitigation using a passive loop "
       "conductor", "K. Yamazaki, T. Kawamoto, H. Fujinami", 2000,
       "IEEE Transactions on Power Delivery 15(2):646-651", "Mitigation practice", "journal",
       "Conditions on the position and impedance of a passive loop for it to lower the field in a "
       "target region; a loop helps on one side of itself and can raise the field elsewhere.",
       method="Analysis and measurement", materials="Loop conductors",
       used_for="Passive loop: placement guidance and the warning that the field can rise elsewhere."),
    _r("walling1993", "Series-capacitor compensated shield scheme for enhanced mitigation of "
       "transmission line magnetic fields", "R. A. Walling, J. J. Paserba, C. W. Burns", 1993,
       "IEEE Transactions on Power Delivery 8(1):461-469", "Mitigation practice", "journal",
       "A capacitor in series with a passive shield loop cancels part of the loop's reactance, so "
       "the induced current, and with it the field cancellation, is larger.",
       method="Analysis and field test", materials="Loop conductors with series capacitor",
       used_for="Series compensation setting of the passive loop. Volume and page numbers are "
                "quoted from secondary citations and were not re-checked against the paper."),
    _r("cruz2002", "Magnetic field mitigation in power lines with passive and active loops",
       "P. Cruz, C. Izquierdo, M. Burgos, L. F. Ferrer, F. Soto, C. Llanos, J. D. Pacheco", 2002,
       "CIGRE Session 2002, paper 36-107", "Mitigation practice", "org-publication",
       "Design and test of passive and actively driven compensation loops on overhead lines.",
       method="Calculation and field measurement", materials="Loop conductors",
       url="https://e-cigre.org/publication/36-107_2002-magnetic-field-mitigation-in-power-lines-with-passive-and-active-loops",
       used_for="Passive loop. Active (driven) loops are not modelled in Taki."),
    _r("bravo2019", "A survey on optimization techniques applied to magnetic field mitigation in "
       "power systems", "J. C. Bravo-Rodriguez, J. C. del-Pino-Lopez, P. Cruz-Romero", 2019,
       "Energies 12(7):1332", "Mitigation practice", "journal",
       "Review of mitigation by passive and active loops and by conductive and ferromagnetic "
       "shields, and of the optimisation methods used to place and size them.",
       method="Literature survey", materials="Loops; aluminium, steel and combined shields",
       doi="10.3390/en12071332", url="https://doi.org/10.3390/en12071332",
       used_for="Overview of the measures offered on the Shield tab."),
    _r("patent5360998", "Magnetic field minimization in power transmission",
       "US Patent 5,360,998", 1994, "United States Patent", "Mitigation practice", "web",
       "Compensated (closed-loop) shielding circuits along a right-of-way; reports roughly "
       "60-80 % magnetic and 20-40 % electric field reduction.",
       method="Passive / compensated loop", materials="Loop conductors",
       url="https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5360998",
       used_for="Empirical model: grounded mesh / passive loop defaults."),
    # --------------------------------------------------------------- measurement
    _r("ieee644", "IEEE Standard Procedures for Measurement of Power Frequency Electric and "
       "Magnetic Fields from AC Power Lines", "IEEE", 2019, "IEEE Std 644-2019", "Measurement",
       "standard",
       "Measurement procedures, including the 1 m height above ground used for lateral profiles.",
       used_for="Default 1 m measurement height."),
    _r("iec62110", "Electric and magnetic field levels generated by AC power systems - "
       "Measurement procedures with regard to public exposure", "International Electrotechnical "
       "Commission", 2009, "IEC 62110:2009", "Measurement", "standard",
       "Measurement heights and averaging for public-exposure assessment near power systems.",
       used_for="Context for measurement height and receptor points."),
    # ----------------------------------------------------------- validation data
    _r("fikry2022", "EMI radiation of power transmission lines in Malaysia",
       "A. Fikry, S. C. Lim, M. Z. A. Ab Kadir", 2022, "F1000Research 10:1136 (version 2)",
       "Validation data", "dataset",
       "Simulated E and B for five Malaysian line types under transposed / untransposed phasing "
       "and conducting / non-conducting ground. Article CC-BY 4.0, data CC0. Bundled with Taki.",
       method="EMFACDC (ITU-T K.90)", url="https://doi.org/10.12688/f1000research.73067.2",
       doi="10.12688/f1000research.73067.2", used_for="Code-to-code verification (Validation page)."),
    _r("jimbin2017", "Magnetic field measurement from 132/275 kV overhead power lines",
       "V. S. Jimbin, N. A. Ahmad", 2017, "Jurnal Teknologi", "Validation data", "journal",
       "Field measurements on Malaysian 132 kV and 275 kV lines. Not redistributed: digitise the "
       "published figures with the CSV template on the Validation page.",
       method="Measurement", doi="10.11113/jt.v79.7270",
       used_for="Suggested measured dataset for model validation."),
    # -------------------------------------------------------------- health review
    _r("who2007", "Environmental Health Criteria 238: Extremely Low Frequency Fields",
       "World Health Organization", 2007, "WHO, Geneva", "Health review", "org-publication",
       "Review of ELF exposure sources and health evidence. Notes that electric fields are "
       "readily perturbed and screened by buildings, trees and other earthed objects, whereas "
       "magnetic fields are not.",
       freq="ELF (below 300 Hz)", url="https://www.who.int/publications/i/item/9789241572385",
       used_for="Why E and B shielding are treated as different problems."),
    # ------------------------------------------- empirical percentages (Taki v2)
    _r("emf_shielding_overview", "EMF Shielding and Mitigation", "EMF Services", "n.d.",
       "EMF Services (engineering web page)", "Empirical shielding estimates", "web",
       "Explains why a power-frequency magnetic shield behaves very differently from an RF shield.",
       url="https://m.emfservices.com/emf-shielding.htm",
       used_for="Empirical model: vegetation / thin non-ferrous materials."),
    _r("eagle_magnetic_lf_hf", "How Shielding Requirements Change Between Low-Frequency and "
       "High-Frequency Applications", "Eagle Magnetic", 2026, "Eagle Magnetic (engineering web page)",
       "Empirical shielding estimates", "web",
       "Low-frequency magnetic shielding needs high-permeability material; copper and aluminium "
       "give little attenuation unless thick.",
       url="https://eaglemagnetic.com/shielding-low-frequency-and-high-frequency-applications/",
       used_for="Empirical model: steel versus non-ferrous defaults."),
    _r("steel_vs_aluminum_60hz", "Steel vs Aluminum at 60 Hz Magnetic Field", "Snubber.ai", 2026,
       "Snubber.ai (engineering reference page)", "Empirical shielding estimates", "web",
       "At 60 Hz, shielding performance is governed mainly by permeability rather than "
       "conductivity for thin sheet.",
       url="https://snubber.ai/engineering-interview-questions/electromagnetics-magnetic-shielding-steel-aluminum",
       used_for="Empirical model: metal siding / structural steel."),
    _r("emf_metals_guide", "Metals for EMF Shielding: A Guide to Conductive Materials",
       "EMF Safe Living", 2026, "EMF Safe Living (web page)", "Empirical shielding estimates", "web",
       "Comparative shielding figures for steel, aluminium and other conductive materials.",
       url="https://emfsafeliving.com/metals-for-emf-shielding/",
       used_for="Empirical model: metal siding / structural steel."),
    _r("rebar_concrete_shielding", "Shielding Effectiveness of Reinforced-Concrete / Rebar "
       "Structures (radio-frequency studies)", "IEICE ISAP Proceedings; IEEE Trans. EMC (various)",
       "2003-2014", "Conference and journal papers", "Empirical shielding estimates", "web",
       "Rebar grids act as conductive-mesh shields at radio frequencies. Taki extrapolates "
       "conservatively to 50/60 Hz, hence the low magnetic figure for concrete.",
       freq="Radio frequency", url="https://www.ieice.org/cs/isap/ISAP_Archives/2014/pdf/WE1A_03.pdf",
       used_for="Empirical model: reinforced-concrete wall."),
]

_BY_ID = {r["id"]: r for r in LIBRARY}

#: The six sources behind shielding.py's percentages - the list earlier versions exported.
REFERENCES: List[Dict[str, str]] = [
    _BY_ID[k] for k in ("emf_shielding_overview", "eagle_magnetic_lf_hf", "steel_vs_aluminum_60hz",
                        "emf_metals_guide", "patent5360998", "rebar_concrete_shielding")]
# shielding.py refers to the patent by its older id
_BY_ID["compensated_shielding_patent"] = _BY_ID["patent5360998"]


def get(ref_id: str) -> Optional[Dict[str, str]]:
    return _BY_ID.get(ref_id)


def format_reference_line(ref: Dict[str, str]) -> str:
    return f"{ref['title']} - {ref.get('venue') or ref.get('publisher', '')} ({ref['year']})"


def format_citation(ref: Dict[str, str]) -> str:
    bits = [f"{ref['authors']} ({ref['year']}). {ref['title']}. {ref['venue']}."]
    if ref.get("doi"):
        bits.append(f"doi:{ref['doi']}")
    return " ".join(bits)
