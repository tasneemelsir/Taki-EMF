"""
report_figures.py
=================
Static figures for the PDF / Word reports, drawn with matplotlib.

Earlier versions rasterised the interactive Plotly figures through kaleido,
which needs a Chromium install; where that was missing every figure in the
report silently became a "[Figure could not be rendered]" placeholder.
matplotlib has no such dependency, so the report always carries its figures.

Colours follow theme tokens used by the web app (the original Taki palette).
"""

from __future__ import annotations

import io
import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.colors import LogNorm, Normalize, TwoSlopeNorm   # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from mpl_toolkits.axes_grid1 import make_axes_locatable   # noqa: E402

INK = "#0F1B24"
BLUE = "#004B87"
BLUE_BRIGHT = "#0072B5"
STEEL = "#5B6770"
LINE = "#DDE2E6"
GREEN = "#1E6B3F"
AMBER = "#B26B00"
RED = "#B3261E"
TEAL = "#00857C"
PHASE_COLORS = {"A": "#C0392B", "B": "#D9A400", "C": BLUE}
SERIES = [BLUE, RED, "#1E7A34", "#6B3FA0", "#D68910", STEEL]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": LINE, "axes.labelcolor": STEEL,
    "axes.titlecolor": BLUE, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "xtick.color": STEEL, "ytick.color": STEEL,
    "grid.color": LINE, "grid.linewidth": 0.7, "axes.grid": True, "axes.axisbelow": True,
    "legend.frameon": False, "legend.fontsize": 8, "figure.dpi": 100,
})


def _png(fig, dpi: int = 170) -> bytes:
    # The report gives every figure a heading, so the first line of the axes title would
    # repeat it. Keep only the explanatory second line, as a quiet sub-title.
    for ax in fig.axes:
        for loc in ("left", "center", "right"):
            t = ax.get_title(loc=loc)
            if t:
                rest = t.split("\n", 1)[1] if "\n" in t else ""
                ax.set_title("", loc=loc)
                if rest:
                    ax.set_title(rest, fontsize=8.5, color="#5B6770", fontweight="normal", loc="left")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _row_band(ax, row_half):
    if row_half:
        ax.axvspan(-row_half, row_half, color=BLUE, alpha=0.06, lw=0)
        for s in (-1, 1):
            ax.axvline(s * row_half, color=STEEL, lw=0.8, ls=":", alpha=0.6)


def _limits(ax, limits, unit):
    """limits: list of (value, label)."""
    merged: Dict[float, List[str]] = {}
    for v, lab in limits or []:
        if v is not None:
            merged.setdefault(round(float(v), 6), []).append(lab)
    ymax = ax.get_ylim()[1]
    for v, labs in sorted(merged.items()):
        if v > ymax * 1.6:
            continue
        ax.axhline(v, color=RED, lw=1.0, ls="--")
        lab = labs[0] if len(labs) == 1 else f"{labs[0]} +{len(labs) - 1}"
        ax.annotate(f"{lab} - {v:g} {unit}", xy=(0.01, v), xycoords=("axes fraction", "data"),
                    xytext=(0, 3), textcoords="offset points", color=RED, fontsize=7, zorder=20,
                    bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none", alpha=0.85))


def profile(x, b0, e0, row_half=None, b_limits=None, b_shield=None, e_shield=None,
            title="Lateral field profile", subtitle="") -> bytes:
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(x, b0, color=BLUE, lw=2.0, label="B field")
    if b_shield is not None:
        ax.plot(x, b_shield, color=GREEN, lw=1.8, label="B field, with shield")
    ax.set_xlabel("Lateral distance from centreline (m)")
    ax.set_ylabel("B field (µT)")
    ax.set_ylim(0, max(float(np.max(b0)), float(np.max(b_shield)) if b_shield is not None else 0) * 1.18 or 1)
    _row_band(ax, row_half)
    _limits(ax, b_limits, "µT")
    ax2 = ax.twinx()
    ax2.grid(False)
    ax2.plot(x, e0, color=BLUE_BRIGHT, lw=1.4, ls=":", label="E field")
    if e_shield is not None:
        ax2.plot(x, e_shield, color=GREEN, lw=1.3, ls=":", label="E field, with shield")
    ax2.set_ylabel("E field (kV/m)")
    ax2.set_ylim(0, max(float(np.max(e0)), 1e-9) * 1.18)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", ncol=2)
    ax.set_title(title + (f"\n{subtitle}" if subtitle else ""))
    return _png(fig)


def _decorate_section(ax, conductors, walls, buildings, row_half, pins=None, dark=False, fill=True):
    """
    Buildings, shield, conductors and right-of-way over a cross-section.
    dark: the picture behind is a dark field map, so outlines are drawn light.
    fill: tint the inside of each building (off over a colour-coded map, whose colours must stay true).
    """
    edge = "#F2F5F7" if dark else INK
    for b in buildings or []:
        x0, x1, h = b["x0"], b["x1"], b["h"]
        ax.add_patch(Rectangle((min(x0, x1), 0), abs(x1 - x0), h,
                               fc=(0.06, 0.1, 0.14, 0.12) if fill else "none",
                               ec=edge, lw=1.0, zorder=4))
        ax.annotate(b.get("name", ""), ((x0 + x1) / 2, h), xytext=(0, 3), textcoords="offset points",
                    ha="center", fontsize=7, color=edge, zorder=6)
    for (x1, y1, x2, y2) in walls or []:
        if math.hypot(x2 - x1, y2 - y1) < 0.3:        # a conductor (loop or screening wire), not a sheet
            ax.scatter([(x1 + x2) / 2], [(y1 + y2) / 2], s=42, facecolors="white", edgecolors="#00B8B0",
                       linewidths=1.8, zorder=6)
        else:
            ax.plot([x1, x2], [y1, y2], color="#00B8B0", lw=3.0, solid_capstyle="round", zorder=5)
    if conductors:
        ax.scatter([c[0] for c in conductors], [c[1] for c in conductors], s=28,
                   c=[PHASE_COLORS.get(c[2], STEEL) for c in conductors], edgecolors="white",
                   linewidths=0.8, zorder=7)
    if row_half:
        for s in (-1, 1):
            ax.axvline(s * row_half, color="white", lw=0.8, ls=":", alpha=0.8)
    for i, p in enumerate(pins or []):
        ax.scatter([p[0]], [p[1]], s=46, c="white", edgecolors=INK, linewidths=1.2, zorder=8)
        ax.annotate(str(i + 1), (p[0], p[1]), xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=7, color=INK, zorder=9)


def map_range(g0) -> Tuple[float, float]:
    """
    (low, high) of the colour scale of a field map, from the unshielded picture:
    high is the level 99.5 % of the picture lies below - the few cells that touch
    a conductor would otherwise stretch the scale and leave the rest dark - and
    low is its lowest level, at most four decades down. A shielded space falls
    below the scale and shows as the darkest colour.
    """
    v = np.asarray(g0, float)
    v = v[np.isfinite(v) & (v > 0)]
    if v.size == 0:
        return 1e-3, 1.0
    hi = float(np.percentile(v, 99.5))
    lo = max(float(np.percentile(v, 0.5)), hi * 1e-4)
    return (lo, hi) if lo < hi else (hi * 1e-3, hi)


def field_map(x, y, g0, gS, quantity="B", view="without", conductors=None, walls=None,
              buildings=None, row_half=None, log_scale=True, title=None, subtitle="",
              pins=None) -> bytes:
    """view: 'without' | 'with' | 'diff' (percentage change)."""
    g0 = np.asarray(g0, float); gS = np.asarray(gS, float)
    unit = "µT" if quantity == "B" else "kV/m"
    name = "Magnetic field" if quantity == "B" else "Electric field"
    span_x = float(x[-1] - x[0]); span_y = float(y[-1] - y[0])
    fig, ax = plt.subplots(figsize=(9, max(3.4, min(6.0, 9 * span_y / max(span_x, 1e-9) + 1.2))))
    ax.grid(False)
    # the colour bar gets its own axes beside the map, so it is exactly as tall as the map
    cax = make_axes_locatable(ax).append_axes("right", size="2.2%", pad=0.09)
    cax.grid(False)
    if view == "diff":
        pct = np.where(g0 > 1e-12, (gS - g0) / np.maximum(g0, 1e-12) * 100.0, 0.0)
        lim = max(5.0, float(np.nanpercentile(np.abs(pct), 99.5)))
        im = ax.pcolormesh(x, y, np.clip(pct, -lim, lim), cmap="RdBu_r",
                           norm=TwoSlopeNorm(0.0, -lim, lim), shading="gouraud", rasterized=True)
        cb = fig.colorbar(im, cax=cax)
        cb.set_label("Change with shield (%)")
        ttl = title or f"Effect of the shield - {name}"
    else:
        z = gS if view == "with" else g0
        lo, vmax = map_range(g0)
        if log_scale:
            norm = LogNorm(lo, vmax)
            z = np.clip(z, lo, vmax)
        else:
            norm = Normalize(0, vmax)
        im = ax.pcolormesh(x, y, z, cmap="cividis", norm=norm, shading="gouraud", rasterized=True)
        cb = fig.colorbar(im, cax=cax)
        cb.set_label(f"{quantity} ({unit})" + (", log scale" if log_scale else ""))
        ttl = title or f"{name} - {'with' if view == 'with' else 'without'} shield"
    cb.outline.set_edgecolor(LINE)
    _decorate_section(ax, conductors, walls, buildings, row_half, pins, dark=view != "diff", fill=False)
    ax.set_xlim(x[0], x[-1]); ax.set_ylim(0, y[-1])
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Lateral distance (m)"); ax.set_ylabel("Height above ground (m)")
    ax.set_title(ttl + (f"\n{subtitle}" if subtitle else ""))
    return _png(fig)


def arrangement(lines, row_half=None, buildings=None, walls=None, x_range=None) -> bytes:
    """Cross-section of the corridor: towers, conductors (by phase), buildings and shield."""
    fig, ax = plt.subplots(figsize=(9, 4.2))
    top = 10.0
    for ln in lines:
        xs = [c[0] for c in ln["conductors"]]
        att = [c[3] for c in ln["conductors"]]
        xc, t = float(np.mean(xs)), max(att) + 4.0
        top = max(top, t)
        half = max(2.5, (max(xs) - min(xs)) / 2 * 0.5 + 1.5)
        ax.plot([xc - half, xc, xc + half], [0, t, 0], color="#8C959C", lw=1.2, zorder=2)
        for c in ln["conductors"]:
            ax.plot([xc, c[0]], [c[3], c[3]], color="#8C959C", lw=1.2, zorder=2)
            ax.plot([c[0], c[0]], [c[3], c[1]], color=LINE, lw=1.0, ls=":", zorder=2)
        ax.scatter(xs, [c[1] for c in ln["conductors"]], s=42,
                   c=[PHASE_COLORS.get(c[2], STEEL) for c in ln["conductors"]],
                   edgecolors=INK, linewidths=0.6, zorder=5)
        ax.annotate(ln["name"], (xc, t), xytext=(0, 4), textcoords="offset points", ha="center",
                    fontsize=7, color=STEEL)
    _decorate_section(ax, None, walls, buildings, None)
    _row_band(ax, row_half)
    ax.axhline(0, color=STEEL, lw=1.0)
    if x_range:
        ax.set_xlim(*x_range)
    for b in buildings or []:
        top = max(top, b["h"] + 4)
    ax.set_ylim(-1, top + 4)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Lateral distance (m)"); ax.set_ylabel("Height (m)")
    for ph, col in PHASE_COLORS.items():
        ax.scatter([], [], c=col, s=30, label=f"Phase {ph}")
    ax.legend(loc="upper right", ncol=3)
    ax.set_title("Corridor cross-section at mid-span\nMarkers at mid-span height; dotted lines "
                 "show the drop from the tower attachment")
    return _png(fig)


def receptors(rows: Sequence[dict]) -> bytes:
    """Average magnetic field inside each building: unshielded, with the shield, and the fabric estimate."""
    fig, ax = plt.subplots(figsize=(9, 3.6))
    n = len(rows)
    xs = np.arange(n)
    barrier = any(r.get("barrier_on") for r in rows)
    emp = any(r.get("material_key", "none") != "none" for r in rows)
    k = 1 + int(emp) + int(barrier)
    w = 0.8 / k
    i = 0
    avg = "b_in_avg_uT" if all("b_in_avg_uT" in r for r in rows) else "b_unshielded_uT"
    groups = [ax.bar(xs + (i - (k - 1) / 2) * w, [r[avg] for r in rows], w, color=RED, label="Unshielded")]
    i += 1
    if emp:
        groups.append(ax.bar(xs + (i - (k - 1) / 2) * w, [r["b_shielded_uT"] for r in rows], w, color=GREEN,
                             label="Empirical building material (at the wall probe)"))
        i += 1
    if barrier:
        key = "b_in_avg_shield_uT" if avg == "b_in_avg_uT" else "b_barrier_uT"
        groups.append(ax.bar(xs + (i - (k - 1) / 2) * w,
                             [r[key] if r.get("barrier_on") else np.nan for r in rows], w,
                             color=BLUE_BRIGHT, label="With the shield"))
    for g in groups:                                   # the value on each bar: a shielded one can be too low to see
        ax.bar_label(g, labels=["" if not np.isfinite(v) else f"{v:.3g}" for v in g.datavalues],
                     padding=2, fontsize=7.5, color=STEEL)
    ax.set_xticks(xs)
    ax.set_xticklabels([r["building"] for r in rows])
    span = max(n, 3)                                   # one or two buildings do not get bars as wide as the page
    ax.set_xlim((n - 1) / 2 - span / 2, (n - 1) / 2 + span / 2)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.08)
    ax.set_ylabel("B field, average inside (µT)" if avg == "b_in_avg_uT" else "B field (µT)")
    ax.legend(loc="upper right")
    ax.grid(axis="x", visible=False)
    ax.set_title("Building receptors - magnetic field\nAverage over the inside of each building")
    return _png(fig)


def field_lines(x, y, a, conductors, walls=None, buildings=None, subtitle="",
                phase_deg: float = 0.0, n_lines: int = 15, reference=None) -> bytes:
    """
    Magnetic field lines at one instant, as contours of the vector potential
    (see engine/field_lines.py). `a` is the complex potential on the (y, x) grid;
    `reference` is the potential without the shield, when `a` includes one, so
    the lines are spaced as in the unshielded picture (as the app does).
    """
    from . import field_lines as fl
    x = np.asarray(x, float); y = np.asarray(y, float)
    real = fl.snapshot(a, phase_deg)
    base = a if reference is None else reference
    scale = fl.scale_of(base)
    f = fl.spread(real, scale, fl.softness_of(base, scale))
    span_x = float(x[-1] - x[0]); span_y = float(y[-1] - y[0])
    fig, ax = plt.subplots(figsize=(9, max(3.4, min(6.0, 9 * span_y / max(span_x, 1e-9) + 1.2))))
    ax.grid(False)
    # half steps keep the zero contour (the surface where the potential changes sign) out of the picture
    levels = (np.arange(-n_lines, n_lines) + 0.5) / n_lines
    ax.contour(x, y, f, levels=levels, colors=BLUE, linewidths=0.75, alpha=0.85, linestyles="solid")
    arr = fl.arrows(real, x, y)
    if arr is not None:
        ax.quiver(arr["x"], arr["y"], arr["u"], arr["v"], color=BLUE, pivot="mid", scale=42, width=0.0028,
                  headwidth=4.5, headlength=5.5, headaxislength=4.5, zorder=3)
    _decorate_section(ax, conductors, walls, buildings, None)
    ax.set_xlim(x[0], x[-1]); ax.set_ylim(0, y[-1])
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Lateral distance (m)"); ax.set_ylabel("Height above ground (m)")
    ax.set_title("Magnetic field lines - instantaneous snapshot"
                 + (f"\n{subtitle}" if subtitle else ""))
    return _png(fig)


def earth_envelope(x, b_free, b_perf, b_sel=None, sel_label="", row_half=None, b_limits=None) -> bytes:
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.fill_between(x, np.minimum(b_free, b_perf), np.maximum(b_free, b_perf), color=BLUE,
                    alpha=0.10, lw=0, label="Earth-return envelope")
    ax.plot(x, b_perf, color=BLUE, lw=1.8, label="Perfectly conducting earth")
    ax.plot(x, b_free, color=STEEL, lw=1.5, ls="--", label="Free space (no earth return)")
    if b_sel is not None:
        ax.plot(x, b_sel, color="#6B3FA0", lw=1.8, ls=":", label=sel_label or "Selected model")
    _row_band(ax, row_half)
    _limits(ax, b_limits, "µT")
    ax.set_xlabel("Lateral distance from centreline (m)"); ax.set_ylabel("B field (µT)")
    ax.legend(loc="upper right")
    ax.set_title("Earth-return sensitivity\nReal earth lies between the two exact limits")
    return _png(fig)


def sweep(labels, values, baseline=None, title="", unit="µT", ylabel="B at receptor (µT)") -> bytes:
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.bar(range(len(labels)), values, color=BLUE, width=0.65)
    if baseline is not None:
        ax.axhline(baseline, color=RED, lw=1.0, ls="--")
        ax.annotate(f"unshielded {baseline:.3g} {unit}", xy=(0.01, baseline),
                    xycoords=("axes fraction", "data"), xytext=(0, 3), textcoords="offset points",
                    color=RED, fontsize=7)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25 if max(len(str(l)) for l in labels) > 8 else 0,
                       ha="right" if max(len(str(l)) for l in labels) > 8 else "center")
    ax.set_ylabel(ylabel)
    ax.grid(axis="x", visible=False)
    ax.set_title(title)
    return _png(fig)


def scenario_overlay(curves, row_half=None, b_limits=None) -> bytes:
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for i, c in enumerate(curves):
        ax.plot(c["x"], c["b"], color=SERIES[i % len(SERIES)], lw=1.8, label=c["name"])
    _row_band(ax, row_half)
    _limits(ax, b_limits, "µT")
    ax.set_xlabel("Lateral distance from centreline (m)"); ax.set_ylabel("B field (µT)")
    ax.legend(loc="upper right")
    ax.set_title("Scenario comparison - lateral B profile")
    return _png(fig)
