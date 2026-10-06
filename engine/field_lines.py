"""
field_lines.py
==============
Magnetic field lines, drawn from the vector potential.

WHAT "FIELD LINES" MEAN FOR AN AC SYSTEM
----------------------------------------
The rest of the app reports the RMS magnitude of the field, which has no
direction. A three-phase field has no static field lines either: the vector
rotates and pulses over the cycle. The usual way to draw a meaningful picture
is to freeze the waveform at one instant.

HOW THEY ARE DRAWN
------------------
Every current here flows along the line (z), so the flux density is the curl
of a potential with one component:

    B = curl(A z)      Bx = dA/dy      By = -dA/dx

A line of B is therefore a line of constant A. At the instant wt the potential
is  A(x, y, t) = Re[ A^(x, y) e^(jwt) ],  where A^ is the complex (phasor)
potential, so one complex grid gives the picture at every instant of the cycle:
the browser animates it without asking the server again.

Contours of A are exact field lines: they never cross, never stop in mid-air,
and close on themselves (a balanced three-phase line carries no net current).
Earlier versions traced each line step by step from seed points near the
conductors, which left lines cut off where the tracer ran out of steps.

With the physical shield model the potential includes the currents induced in
the shield and the magnetisation of a magnetic sheet. Across a magnetic sheet
A steps by the flux the sheet carries along itself, so lines visibly end on a
steel plate and leave it somewhere else: that is the flux being shunted.

SPACING OF THE LINES
--------------------
Equal steps of A put equal flux between neighbouring lines, so the lines crowd
where the field is strong - and almost none are left at a building 30 m from
the line. `spread()` maps A through a symmetric logarithm first, which spaces
the lines evenly enough to show the weak field too. Both are offered.

The mapping is linear below a level a0 and logarithmic above it. Levels below
a0 all sit close to the surface where A changes sign, so too low an a0 packs
lines into a dark band there that says nothing about the field. a0 is therefore
taken from the picture itself: the level the weakest fifth of it lies below
(`softness_of`). A single circuit, whose field reaches far, then gets a high
a0 and no band; a double circuit with cancelling phases, whose field dies away
quickly, gets a low one so the lines still reach the building.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from . import physics, shield_bem

#: Grid on which the potential is sampled for the browser and the report.
GRID_NX, GRID_NY = 181, 91


def potential(conductors, X, Y, ground_model, rho: float, freq: float,
              magnetic_solution=None) -> np.ndarray:
    """Complex A_z [Wb/m] of the line (and of the shield, when a solution is given)."""
    a, _, _ = shield_bem.source_abh(conductors, X, Y, ground_model, rho, freq)
    if magnetic_solution is not None:
        a = a + magnetic_solution.induced_a(X, Y)
    return a


def potential_grid(conductors, x_bounds: Tuple[float, float], y_bounds: Tuple[float, float],
                   ground_model, rho: float, freq: float, magnetic_solution=None,
                   nx: int = GRID_NX, ny: int = GRID_NY):
    """(x, y, A) with A complex, shaped (ny, nx). The lowest row sits just above the ground."""
    x = np.linspace(float(x_bounds[0]), float(x_bounds[1]), int(nx))
    y = np.linspace(max(0.0, float(y_bounds[0])), float(y_bounds[1]), int(ny))
    X, Y = np.meshgrid(x, y)
    return x, y, potential(conductors, X, Y, ground_model, rho, freq, magnetic_solution)


def scale_of(a: np.ndarray) -> float:
    """
    A representative size of the potential over the grid: nearly its largest
    magnitude, ignoring the few samples that sit on top of a conductor (where
    A grows without limit).
    """
    mag = np.abs(np.asarray(a))
    mag = mag[np.isfinite(mag)]
    if mag.size == 0:
        return 0.0
    return float(np.percentile(mag, 99.0))


def snapshot(a: np.ndarray, phase_deg: float = 0.0) -> np.ndarray:
    """The real potential at the instant wt = phase_deg."""
    return np.real(np.asarray(a) * np.exp(1j * np.deg2rad(phase_deg)))


#: The symmetric-log mapping is linear below a0 = scale / softness and logarithmic above it.
#: SOFTNESS is the softest allowed (and the value used before the picture is known).
SOFTNESS = 400.0
SOFTNESS_MIN = 8.0
#: a0 is the level this share (in percent) of the picture lies below.
WEAK_SHARE = 20.0


def softness_of(a: np.ndarray, scale: Optional[float] = None) -> float:
    """
    scale / a0 for `spread`, from the phasor potential over the picture: a0 is the
    magnitude the weakest WEAK_SHARE percent of it lies below. It depends on the
    phasor, not on the instant, so the spacing does not change through the cycle.
    """
    mag = np.abs(np.asarray(a))
    mag = mag[np.isfinite(mag)]
    scale = scale_of(a) if scale is None else float(scale)
    if mag.size == 0 or not scale > 0:
        return SOFTNESS
    a0 = float(np.percentile(mag, WEAK_SHARE))
    if not a0 > 0:
        return SOFTNESS
    return float(min(SOFTNESS, max(SOFTNESS_MIN, scale / a0)))


def spread(a_real: np.ndarray, scale: float, softness: float = SOFTNESS) -> np.ndarray:
    """
    Symmetric logarithm of the instantaneous potential, in the range -1 .. 1.
    Equal steps of the result are roughly geometric steps of A, which spaces the
    field lines so the weak field far from the line shows as well.
    """
    if not scale > 0:
        return np.zeros_like(np.asarray(a_real, float))
    a0 = scale / softness
    return np.sign(a_real) * np.log1p(np.abs(a_real) / a0) / np.log1p(softness)


def direction(a_real: np.ndarray, x: np.ndarray, y: np.ndarray):
    """(Bx, By) at the grid points from the potential: Bx = dA/dy, By = -dA/dx."""
    d_dy, d_dx = np.gradient(np.asarray(a_real, float), np.asarray(y, float), np.asarray(x, float))
    return d_dy, -d_dx


def arrows(a_real: np.ndarray, x: np.ndarray, y: np.ndarray, nx: int = 13, ny: int = 6,
           floor: float = 0.02) -> Optional[dict]:
    """
    A sparse set of arrows showing which way the field points: {"x", "y", "u", "v"}
    with (u, v) unit vectors. Points where the field is under `floor` of the
    strongest sampled value are left out.
    """
    bx, by = direction(a_real, x, y)
    ix = np.linspace(0, len(x) - 1, nx + 2)[1:-1].round().astype(int)
    iy = np.linspace(0, len(y) - 1, ny + 2)[1:-1].round().astype(int)
    gx, gy = np.meshgrid(ix, iy)
    u, v = bx[gy, gx], by[gy, gx]
    mag = np.hypot(u, v)
    if not np.any(mag > 0):
        return None
    keep = mag > floor * np.percentile(mag, 90)
    return {"x": x[gx][keep], "y": y[gy][keep], "u": (u / np.where(mag > 0, mag, 1))[keep],
            "v": (v / np.where(mag > 0, mag, 1))[keep]}


# ---------------------------------------------------------------------------
# Electric field lines
# ---------------------------------------------------------------------------
# The electric field of the line is that of a line charge on every conductor, with an image of
# the opposite sign in the ground. An electric field line starts on positive charge and ends on
# negative charge (a wire at the opposite point of its cycle, the ground, or an earthed shield),
# so unlike a magnetic line it has two ends, and the number of lines leaving a wire is in
# proportion to the charge on it. They are traced from the wires, which the browser does at
# every instant from three things worked out here once:
#
#   * the charge phasor on every conductor, as lam = q / (2 pi eps0) in volts, so the field of
#     one wire is simply lam / r;
#   * with a shield solved physically, the field of the charge induced on the shield, on a grid
#     (smooth everywhere except on the sheet itself, where the lines end anyway);
#   * the potential on a grid. Its contours are the equipotentials, which the field crosses at
#     right angles, and they show the weak field a long way from the line that few lines reach.
K_E = 1.0 / (2.0 * np.pi * physics.EPS0)


def electric_data(conductors, x_bounds: Tuple[float, float], y_bounds: Tuple[float, float],
                  bundle_eq: bool = True, electric_solution=None,
                  nx: int = GRID_NX, ny: int = GRID_NY) -> dict:
    """
    {"x", "y", "lam0", "v0"} and, with a shield solution, {"lamS", "vS", "exS", "eyS"}.
    lam* are complex [V] per conductor; v* complex potential [V], shaped (ny, nx);
    exS, eyS the complex field [V/m] of the charge on the shield alone.
    """
    x = np.linspace(float(x_bounds[0]), float(x_bounds[1]), int(nx))
    y = np.linspace(max(0.0, float(y_bounds[0])), float(y_bounds[1]), int(ny))
    X, Y = np.meshgrid(x, y)
    q0 = (physics.solve_conductor_charges(conductors, bundle_equivalent=bundle_eq)
          if conductors else np.zeros(0, complex))
    out = {"x": x, "y": y, "lam0": q0 * K_E,
           "v0": shield_bem.conductor_potential(conductors, q0, X, Y),
           "lamS": None, "vS": None, "exS": None, "eyS": None}
    if electric_solution is not None:
        ele = electric_solution
        out["lamS"] = np.asarray(ele.q_cond, complex) * K_E
        out["vS"] = ele.v_total(X, Y)
        out["exS"], out["eyS"] = ele.e_induced(X, Y)
    return out


def electric_field(conductors, lam, X, Y):
    """Complex (Ex, Ey) [V/m] of the line charges lam [V] with their images: what the browser sums."""
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    ex = np.zeros(X.shape, complex); ey = np.zeros(X.shape, complex)
    m2 = physics.MIN_DISTANCE_M ** 2
    for c, l in zip(conductors, lam):
        dx = X - c.x
        dy = Y - c.y_sagged
        dyi = Y + c.y_sagged
        r2 = np.maximum(dx * dx + dy * dy, m2)
        r2i = np.maximum(dx * dx + dyi * dyi, m2)
        ex += l * (dx / r2 - dx / r2i)
        ey += l * (dy / r2 - dyi / r2i)
    return ex, ey
