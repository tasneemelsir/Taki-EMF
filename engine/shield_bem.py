"""
shield_bem.py
=============
Physical shielding solvers for a FINITE barrier beside a transmission line.

Both problems are solved in the x-y cross-section (the barrier is treated as
long compared with its height, which is the usual case for a wall beside a
line), by a boundary-element method on the barrier itself. The barrier is a set
of thin plates; each plate is cut into small straight elements.

MAGNETIC FIELD  -  thin-shell eddy-current / flux-shunting model
---------------------------------------------------------------
Every element carries two unknowns:

  K  sheet current [A/m] flowing along the line direction (eddy currents), and
  m  tangential magnetisation moment per unit area [A] (flux shunting).

They follow from the two thin-shell relations for a slab of conductivity sigma,
permeability mu and thickness t (Krahenbuhl & Muller, IEEE Trans. Magn. 1993):

  K = sigma * t_eff * E_z                    (Faraday + Ohm through the sheet)
  m = (mu_r * t_eff - t) * H_t               (flux carried along the sheet)
  t_eff = (2 / gamma) * tanh(gamma t / 2),   gamma = sqrt(j w mu sigma)

t_eff accounts for the skin effect INSIDE the sheet, so the model stays valid
when the sheet is several skin depths thick (steel plate at 50 Hz). E_z and H_t
at each element are the field of the line plus the field of every other
element, which gives a dense linear system. Plates that are bonded together
share one voltage gradient and carry zero net current between them (a ring of
walls around a building therefore supports a circulating loop current; an
isolated plate does not).

Because the plate is finite, flux that wraps around its edges is part of the
solution. The field behind a thin aluminium wall falls by a few tens of
percent, not by the 40-50 dB the infinite-sheet formula predicts, and close to
the edges the field goes UP. tests/test_shield_bem.py checks this solver
against the exact solution for an infinite slab (line source, any sigma and
mu) by making the plate very wide.

ELECTRIC FIELD  -  charge simulation
------------------------------------
The barrier is added to the line's electrostatic problem as a conductor. Each
element carries a surface charge; earthed plates are held at zero potential and
unearthed (floating) plates carry zero net charge at an unknown potential,
which is solved for. The ground is the usual image plane. An unearthed barrier
therefore shields less AND acquires an induced voltage, which is reported
because it is a touch-voltage hazard.

At 50/60 Hz any material whose charge-relaxation time is short compared with a
cycle is an equipotential. That covers every metal, wet concrete and living
vegetation; only a genuine insulator is transparent. The solver applies that
test instead of assuming a material-dependent attenuation.

LIMITS
------
  * 2-D: end effects at the two ends of the barrier along the line are not
    modelled. Results apply within the barrier's length, away from its ends.
  * Linear materials: saturation and hysteresis of steel are not modelled.
  * A mesh is homogenised by its metal fraction. Coverage below 100 % and
    unbonded seams are modelled as real gaps between panels.
  * Buildings are not conductors in this model; the shielding a building gives
    its own interior is not included.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

from . import earth, physics
from .shield_engine import EPS0, MU0, Geometry, Plate, ShieldConfig, get_material

TWO_PI = 2.0 * math.pi
_CHUNK = 2500        # field points evaluated per block (bounds memory)


# ---------------------------------------------------------------------------
# Mesh
# ---------------------------------------------------------------------------
@dataclass
class Mesh:
    cx: np.ndarray; cy: np.ndarray        # element midpoints
    tx: np.ndarray; ty: np.ndarray        # unit tangents
    h: np.ndarray                         # half lengths
    group: np.ndarray                     # bonding group per element
    grounded: np.ndarray                  # bool per element
    plate: np.ndarray                     # plate index per element
    nx: np.ndarray; ny: np.ndarray        # node positions (magnetic charges)
    inc: np.ndarray                       # nodes x elements incidence: q = inc @ m
    ds: float                             # typical element length

    @property
    def n(self) -> int:
        return int(self.cx.size)

    @property
    def length(self) -> np.ndarray:
        return 2.0 * self.h


def build_mesh(plates: Sequence[Plate], ds_target: float = 0.2, max_elements: int = 420) -> Mesh:
    total = sum(p.length for p in plates)
    ds = max(ds_target, total / max_elements) if total > 0 else ds_target
    cx, cy, tx, ty, hh, grp, gnd, pl = [], [], [], [], [], [], [], []
    node_x, node_y, rows, cols, vals = [], [], [], [], []
    for pi, p in enumerate(plates):
        first_node = len(node_x)
        e0 = len(cx)
        pts = p.points
        node_x.append(pts[0][0]); node_y.append(pts[0][1])
        for a, b in zip(pts[:-1], pts[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L <= 1e-9:
                continue
            n = int(max(6, math.ceil(L / ds)))
            ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            step = L / n
            for i in range(n):
                s = (i + 0.5) * step
                cx.append(a[0] + ux * s); cy.append(a[1] + uy * s)
                tx.append(ux); ty.append(uy); hh.append(step / 2.0)
                grp.append(p.group); gnd.append(p.grounded); pl.append(pi)
                node_x.append(a[0] + ux * (i + 1) * step); node_y.append(a[1] + uy * (i + 1) * step)
        ne = len(cx) - e0
        # magnetisation along the chain: charge +m at the element's end node, -m at its start
        for i in range(ne):
            rows += [first_node + i, first_node + i + 1]
            cols += [e0 + i, e0 + i]
            vals += [-1.0, 1.0]
    n_el, n_nodes = len(cx), len(node_x)
    inc = np.zeros((n_nodes, n_el))
    if n_el:
        inc[rows, cols] = vals
    arr = lambda v, t=float: np.asarray(v, dtype=t)
    return Mesh(arr(cx), arr(cy), arr(tx), arr(ty), arr(hh), arr(grp, int), arr(gnd, bool),
                arr(pl, int), arr(node_x), arr(node_y), inc, ds)


# ---------------------------------------------------------------------------
# Element kernels (uniform density on a straight element, exact)
# ---------------------------------------------------------------------------
def _local(px, py, cx, cy, tx, ty):
    """Field points (M,) against elements (N,) -> local coordinates (M, N)."""
    dx = px[:, None] - cx[None, :]
    dy = py[:, None] - cy[None, :]
    u = dx * tx[None, :] + dy * ty[None, :]
    v = -dx * ty[None, :] + dy * tx[None, :]
    return u, v


def _kernels(u, v, h, need_ln=True):
    """
    Returns (I_ln, theta, lam):
      I_ln  = integral of ln(r) along the element
      theta = angle the element subtends at the point (signed by the side)
      lam   = 0.5 * ln(r_plus^2 / r_minus^2)
    """
    up, um = u + h, u - h
    lp = up * up + v * v
    lm = um * um + v * v
    tiny = 1e-300
    theta = np.arctan2(2.0 * h * v, u * u + v * v - h * h)
    lnp = np.log(np.maximum(lp, tiny))
    lnm = np.log(np.maximum(lm, tiny))
    lam = 0.5 * (lnp - lnm)
    i_ln = (0.5 * (up * lnp - um * lnm) - 2.0 * h + v * theta) if need_ln else None
    return i_ln, theta, lam


def _to_global(fu, fv, tx, ty):
    return fu * tx - fv * ty, fu * ty + fv * tx


def _off_surface(mesh: "Mesh", px, py, delta: float):
    """
    A thin-sheet field is discontinuous across the sheet and undefined on it.
    Field points lying on a sheet, or within `delta` of one, are moved to
    `delta` from it on the side they are already on (points exactly on a sheet
    go to its +normal side), so profiles and maps show the clean step across a
    barrier instead of a numerical spike.
    """
    if mesh.n == 0 or delta <= 0:
        return px, py
    px = px.copy(); py = py.copy()
    for s in range(0, px.size, _CHUNK):
        sl = slice(s, s + _CHUNK)
        u, v = _local(px[sl], py[sl], mesh.cx, mesh.cy, mesh.tx, mesh.ty)
        near = (np.abs(v) < delta) & (np.abs(u) <= mesh.h[None, :] + 1e-9)
        rows = np.where(near.any(axis=1))[0]
        if rows.size == 0:
            continue
        j = np.argmin(np.where(near[rows], np.abs(v[rows]), np.inf), axis=1)
        vv = v[rows, j]
        shift = np.where(vv < 0, -1.0, 1.0) * delta - vv
        idx = np.arange(px.size)[sl][rows]
        px[idx] += shift * (-mesh.ty[j])
        py[idx] += shift * mesh.tx[j]
    return px, py


# ---------------------------------------------------------------------------
# Source field of the line conductors (vector potential and flux density)
# ---------------------------------------------------------------------------
def source_abh(conductors, X, Y, ground_model, rho, freq):
    """
    Complex A_z [Wb/m] and (Bx, By) [T] of the line at points (X, Y),
    including the earth-return image for the selected ground model.
    """
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    A = np.zeros(X.shape, complex)
    Bx = np.zeros(X.shape, complex)
    By = np.zeros(X.shape, complex)
    k = MU0 / TWO_PI
    for c in conductors:
        th = physics.conductor_angle_rad(c)
        for wx, wy, i_sub in physics._sub_conductor_positions(c):
            I = i_sub * np.exp(1j * th)
            dx = X - wx
            dy = Y - wy
            r2 = np.maximum(dx * dx + dy * dy, physics.MIN_DISTANCE_M ** 2)
            A += -k * I * 0.5 * np.log(r2)
            Bx += -k * I * dy / r2
            By += k * I * dx / r2
            if ground_model and ground_model != earth.FREE_SPACE:
                yi = earth.image_depth(wy, ground_model, rho, freq)
                dyi = Y - yi
                r2i = dx * dx + dyi * dyi
                r2i = np.where(np.abs(r2i) < physics.MIN_DISTANCE_M ** 2,
                               physics.MIN_DISTANCE_M ** 2, r2i)
                A += k * I * 0.5 * np.log(r2i)
                Bx += k * I * dyi / r2i
                By += -k * I * dx / r2i
    return A, Bx, By


# ---------------------------------------------------------------------------
# Magnetic solution
# ---------------------------------------------------------------------------
@dataclass
class SheetProps:
    y_s: complex          # sheet conductance sigma * t_eff * fill  [S]
    chi: complex          # magnetisation coefficient (mu_r t_eff - t) * fill  [m]
    t_eff: complex
    skin_depth: float


def sheet_props(cfg: ShieldConfig, freq: float, material=None, thickness_m: Optional[float] = None,
                fill: Optional[float] = None) -> SheetProps:
    """Thin-shell coefficients of the shield's sheet (or of another material / thickness)."""
    mat = material if material is not None else cfg.material
    t = max(cfg.thickness_m if thickness_m is None else thickness_m, 1e-9)
    w = TWO_PI * freq
    fill = cfg.fill_factor if fill is None else fill
    if mat.sigma > 0 and w > 0:
        gamma = cmath.sqrt(1j * w * MU0 * mat.mu_r * mat.sigma)
        x = gamma * t / 2.0
        t_eff = t if abs(x) < 1e-6 else (2.0 / gamma) * cmath.tanh(x)
        delta = math.sqrt(2.0 / (w * MU0 * mat.mu_r * mat.sigma))
    else:
        t_eff, delta = t, float("inf")
    y_s = mat.sigma * t_eff * fill
    chi = (mat.mu_r * t_eff - t) * fill
    if abs(mat.mu_r - 1.0) < 1e-3:
        chi = 0.0
    return SheetProps(complex(y_s), complex(chi), complex(t_eff), delta)


def element_props(plates: Sequence[Plate], mesh: "Mesh", cfg: ShieldConfig, freq: float):
    """
    Per-element sheet conductance y_s [S], magnetisation coefficient chi [m] and
    series compensation [H/m]. A plate may use the shield's second material
    (two-material construction) or stand for a round conductor, in which case
    its strip carries the conductor's real cross-section.
    """
    cache = {}
    ys = np.zeros(mesh.n, complex); chi = np.zeros(mesh.n, complex); ls = np.zeros(mesh.n)
    for pi in sorted(set(int(v) for v in mesh.plate)):
        plate = plates[pi] if pi < len(plates) else None
        mat_id = getattr(plate, "material_id", None)
        area = float(getattr(plate, "wire_area_m2", 0.0) or 0.0)
        key = (mat_id, round(area, 9), round(plate.length, 6) if area > 0 and plate is not None else 0)
        if key not in cache:
            mat = get_material(mat_id, cfg.custom_material) if mat_id else cfg.material
            if area > 0:
                cache[key] = sheet_props(cfg, freq, mat, area / max(plate.length, 1e-6), 1.0)
            else:
                cache[key] = sheet_props(cfg, freq, mat)
        sel = mesh.plate == pi
        ys[sel] = cache[key].y_s
        chi[sel] = cache[key].chi
        ls[sel] = float(getattr(plate, "series_l", 0.0) or 0.0)
    return ys, chi, ls


class MagneticSolution:
    """Solved sheet currents and magnetisation; evaluates the shielded B field."""

    def __init__(self, mesh: Mesh, K: np.ndarray, m: np.ndarray, conductors, ground_model,
                 rho, freq, shield_ground=None):
        self.mesh, self.K, self.m = mesh, K, m
        self.q = mesh.inc @ m if m is not None else None
        self.conductors, self.ground_model, self.rho, self.freq = conductors, ground_model, rho, freq
        #: earth model seen by the shield's own induced currents (see solve_magnetic)
        self.shield_ground = shield_ground if shield_ground is not None else ground_model
        self.ys: Optional[np.ndarray] = None       # per-element sheet conductance, set by the solver
        self._eps2 = (0.5 * mesh.ds) ** 2

    # -- induced field ------------------------------------------------------
    def induced_h(self, X, Y):
        """Complex (Hx, Hy) [A/m] produced by the shield at points (X, Y)."""
        shape = np.shape(X)
        px = np.asarray(X, float).ravel(); py = np.asarray(Y, float).ravel()
        px, py = _off_surface(self.mesh, px, py, 0.5 * self.mesh.ds)
        Hx = np.zeros(px.size, complex); Hy = np.zeros(px.size, complex)
        for s in range(0, px.size, _CHUNK):
            sl = slice(s, s + _CHUNK)
            hx, hy = _induced_h(self.mesh, self.K, self.q, px[sl], py[sl], self.shield_ground,
                                self.rho, self.freq, self._eps2)
            Hx[sl], Hy[sl] = hx, hy
        return Hx.reshape(shape), Hy.reshape(shape)

    def induced_a(self, X, Y):
        """
        Complex vector potential A_z [Wb/m] produced by the shield at points
        (X, Y). Its contours at one instant are the field lines of the shield's
        own field: Bx = dA/dy, By = -dA/dx. Across a magnetic sheet A steps by
        the flux the sheet carries along itself.
        """
        shape = np.shape(X)
        px = np.asarray(X, float).ravel(); py = np.asarray(Y, float).ravel()
        px, py = _off_surface(self.mesh, px, py, 0.5 * self.mesh.ds)
        A = np.zeros(px.size, complex)
        for s in range(0, px.size, _CHUNK):
            sl = slice(s, s + _CHUNK)
            A[sl] = _induced_a(self.mesh, self.K, self.m, px[sl], py[sl], self.shield_ground,
                               self.rho, self.freq)
        return A.reshape(shape)

    def a_total(self, X, Y):
        """Complex A_z [Wb/m] of the line and the shield together."""
        a, _, _ = source_abh(self.conductors, X, Y, self.ground_model, self.rho, self.freq)
        return a + self.induced_a(X, Y)

    def b_total(self, X, Y, source=None):
        """Complex (Bx, By) [T] with the shield present."""
        if source is None:
            _, bx, by = source_abh(self.conductors, X, Y, self.ground_model, self.rho, self.freq)
        else:
            bx, by = source
        hx, hy = self.induced_h(X, Y)
        return bx + MU0 * hx, by + MU0 * hy

    def b_rms_uT(self, X, Y):
        bx, by = self.b_total(X, Y)
        return np.sqrt(np.abs(bx) ** 2 + np.abs(by) ** 2) * 1e6

    @property
    def max_sheet_current(self) -> float:
        return float(np.max(np.abs(self.K))) if self.K.size else 0.0

    def loss_w_per_m(self, y_s: Optional[complex] = None) -> float:
        """Eddy-current loss in the shield per metre of line [W/m]."""
        if not self.K.size:
            return 0.0
        g = np.real(self.ys) if (y_s is None and self.ys is not None) else np.full(self.K.size, complex(y_s or 0).real)
        ok = g > 0
        return float(np.sum(np.abs(self.K[ok]) ** 2 * self.mesh.length[ok] / g[ok]))

    def plate_currents(self) -> np.ndarray:
        """Net current in each plate [A]: the loop current, for conductor loops."""
        n_pl = int(self.mesh.plate.max()) + 1 if self.mesh.n else 0
        out = np.zeros(n_pl, complex)
        np.add.at(out, self.mesh.plate, self.K * self.mesh.length)
        return out


def _image_points(mesh_x, mesh_y, ground_model, rho, freq):
    """y-coordinates of the images of (x, y) for the ground model (None = no image)."""
    if not ground_model or ground_model == earth.FREE_SPACE:
        return None
    if ground_model == earth.PERFECT_CONDUCTOR:
        return -mesh_y
    p = earth.complex_depth(rho, freq)
    return -(mesh_y + 2.0 * p)


def _induced_h(mesh: Mesh, K, q, px, py, ground_model, rho, freq, eps2):
    """H from sheet currents K (analytic) and magnetic node charges q, with ground images."""
    Hx = np.zeros(px.size, complex); Hy = np.zeros(px.size, complex)
    h = mesh.h[None, :]
    # --- direct: sheet currents ---
    if K is not None and np.any(K):
        u, v = _local(px, py, mesh.cx, mesh.cy, mesh.tx, mesh.ty)
        _, th, lam = _kernels(u, v, h, need_ln=False)
        fu = -(th / TWO_PI)
        fv = lam / TWO_PI
        gx, gy = _to_global(fu, fv, mesh.tx[None, :], mesh.ty[None, :])
        Hx += gx @ K; Hy += gy @ K
    # --- direct: magnetic charges ---
    if q is not None and np.any(q):
        dx = px[:, None] - mesh.nx[None, :]
        dy = py[:, None] - mesh.ny[None, :]
        r2 = dx * dx + dy * dy + eps2
        Hx += (dx / r2) @ q / TWO_PI; Hy += (dy / r2) @ q / TWO_PI
    if not ground_model or ground_model == earth.FREE_SPACE:
        return Hx, Hy
    # --- earth-return images ---
    if ground_model == earth.PERFECT_CONDUCTOR:
        if K is not None and np.any(K):
            itx, ity = mesh.tx, -mesh.ty
            u, v = _local(px, py, mesh.cx, -mesh.cy, itx, ity)
            _, th, lam = _kernels(u, v, h, need_ln=False)
            gx, gy = _to_global(-(th / TWO_PI), lam / TWO_PI, itx[None, :], ity[None, :])
            Hx += gx @ (-K); Hy += gy @ (-K)
        if q is not None and np.any(q):
            dx = px[:, None] - mesh.nx[None, :]
            dy = py[:, None] + mesh.ny[None, :]
            r2 = dx * dx + dy * dy + eps2
            Hx += (dx / r2) @ q / TWO_PI; Hy += (dy / r2) @ q / TWO_PI
        return Hx, Hy
    # complex image: far away, so a point source at each element midpoint is exact enough
    p = earth.complex_depth(rho, freq)
    if K is not None and np.any(K):
        yi = -(mesh.cy + 2.0 * p)
        dx = px[:, None] - mesh.cx[None, :]
        dy = py[:, None] - yi[None, :]
        r2 = dx * dx + dy * dy
        I = -K * mesh.length
        Hx += (-dy / r2) @ I / TWO_PI; Hy += (dx / r2) @ I / TWO_PI
    if q is not None and np.any(q):
        yi = -(mesh.ny + 2.0 * p)
        dx = px[:, None] - mesh.nx[None, :]
        dy = py[:, None] - yi[None, :]
        r2 = dx * dx + dy * dy
        Hx += (dx / r2) @ q / TWO_PI; Hy += (dy / r2) @ q / TWO_PI
    return Hx, Hy


def _induced_a(mesh: Mesh, K, m, px, py, ground_model, rho, freq):
    """
    A_z from sheet currents K and tangential magnetisation m, with ground images.
    Uses the same kernels as the system matrix in solve_magnetic (A_K, A_m), at
    arbitrary field points.
    """
    A = np.zeros(px.size, complex)
    use_k = K is not None and bool(np.any(K))
    use_m = m is not None and bool(np.any(m))
    if not (use_k or use_m):
        return A
    k0 = MU0 / TWO_PI
    h = mesh.h[None, :]
    u, v = _local(px, py, mesh.cx, mesh.cy, mesh.tx, mesh.ty)
    i_ln, th, _ = _kernels(u, v, h, need_ln=use_k)
    if use_k:
        A += (-k0 * i_ln) @ K
    if use_m:
        A += (k0 * th) @ m
    if not ground_model or ground_model == earth.FREE_SPACE:
        return A
    if ground_model == earth.PERFECT_CONDUCTOR:
        itx, ity = mesh.tx, -mesh.ty
        u, v = _local(px, py, mesh.cx, -mesh.cy, itx, ity)
        i2, th2, _ = _kernels(u, v, h, need_ln=use_k)
        if use_k:
            A += (k0 * i2) @ K                             # image current is -K
        if use_m:
            A += (k0 * th2) @ m                            # image dipole keeps its moment
        return A
    p = earth.complex_depth(rho, freq)                     # complex image: a point source per element
    L = mesh.length[None, :]
    yi = -(mesh.cy + 2.0 * p)
    dx = px[:, None] - mesh.cx[None, :]
    dy = py[:, None] - yi[None, :]
    r2 = dx * dx + dy * dy
    if use_k:
        A += (k0 * 0.5 * np.log(r2) * L) @ K
    if use_m:
        A += (k0 * (mesh.tx[None, :] * dy + mesh.ty[None, :] * dx) / r2 * L) @ m
    return A


def local_ground_model(ground_model):
    """
    Earth model for the SHIELD'S OWN induced currents.

    "Perfectly conducting earth" is a classical approximation for the line's
    field (an image of each conductor at -h). Applied to a barrier standing on
    the ground it would put an opposite image current directly under the
    barrier's foot, which lets the whole return current collapse onto the
    ground line - an artefact: real soil is some nine orders of magnitude less
    conductive than a metal sheet and cannot carry the barrier's eddy currents.
    So the barrier's currents always see real soil (complex image at the site's
    resistivity), unless the earth is switched off altogether.
    """
    if not ground_model or ground_model == earth.FREE_SPACE:
        return earth.FREE_SPACE
    return earth.COMPLEX_IMAGE


def solve_magnetic(geom: Geometry, cfg: ShieldConfig, conductors, ground_model, rho, freq,
                   mesh: Optional[Mesh] = None, closed_return: bool = False,
                   shield_ground: Optional[str] = None) -> Optional[MagneticSolution]:
    """
    Solve the thin-shell problem. Returns None when there is nothing to solve.

    ground_model applies to the line's (source) field. shield_ground is the
    earth model seen by the barrier's own currents; by default it follows
    local_ground_model(ground_model).

    closed_return=True lets each plate carry a net current, as if its two ends
    were joined by a perfect return conductor. That is the infinite-sheet
    situation and is used by the verification tests; a real barrier is isolated
    (zero net current per bonded group), which is the default.
    """
    if not geom.plates:
        return None
    mesh = mesh or build_mesh(geom.plates)
    n = mesh.n
    if n == 0:
        return None
    ys, chi, ls = element_props(geom.plates, mesh, cfg, freq)
    w = TWO_PI * freq
    conducting = np.abs(ys) > 1e-12
    use_k = bool(np.any(conducting)) and w > 0
    use_m = bool(np.any(np.abs(chi) > 1e-12))
    sg = shield_ground if shield_ground is not None else local_ground_model(ground_model)
    if not use_k and not use_m:
        out = MagneticSolution(mesh, np.zeros(n, complex), None, conductors, ground_model, rho, freq, sg)
        out.ys = ys
        return out

    cx, cy, tx, ty, hh = mesh.cx, mesh.cy, mesh.tx, mesh.ty, mesh.h
    h = hh[None, :]
    eye = np.eye(n, dtype=bool)
    k0 = MU0 / TWO_PI

    # ---- kernels between elements (collocation at midpoints) ----
    u, v = _local(cx, cy, cx, cy, tx, ty)
    v = np.where(eye, 0.0, v)
    i_ln, th, lam = _kernels(u, v, h)
    th = np.where(eye, 0.0, th)            # principal value on the element itself
    lam = np.where(eye, 0.0, lam)
    A_K = (-k0 * i_ln).astype(complex)                     # A at i per unit K on j
    A_m = (k0 * th).astype(complex)                        # A at i per unit m on j
    gx, gy = _to_global(-(th / TWO_PI), lam / TWO_PI, tx[None, :], ty[None, :])
    Ht_K = (gx * tx[:, None] + gy * ty[:, None]).astype(complex)   # tangential H at i per unit K on j
    # tangential H at i per unit charge on node k
    dxn = cx[:, None] - mesh.nx[None, :]
    dyn = cy[:, None] - mesh.ny[None, :]
    r2n = dxn * dxn + dyn * dyn
    Ht_q = ((dxn * tx[:, None] + dyn * ty[:, None]) / (TWO_PI * r2n)).astype(complex)

    if sg == earth.PERFECT_CONDUCTOR:
        itx, ity = tx, -ty
        u2, v2 = _local(cx, cy, cx, -cy, itx, ity)
        i2, th2, lam2 = _kernels(u2, v2, h)
        A_K += k0 * i2                                    # image current is -K
        A_m += k0 * th2                                   # image dipole keeps its moment
        g2x, g2y = _to_global(-(th2 / TWO_PI), lam2 / TWO_PI, itx[None, :], ity[None, :])
        Ht_K += -(g2x * tx[:, None] + g2y * ty[:, None])
        dyn2 = cy[:, None] + mesh.ny[None, :]
        r2 = dxn * dxn + dyn2 * dyn2
        Ht_q += (dxn * tx[:, None] + dyn2 * ty[:, None]) / (TWO_PI * r2)
    elif sg == earth.COMPLEX_IMAGE:
        p = earth.complex_depth(rho, freq)
        L = mesh.length[None, :]
        yi = -(cy + 2.0 * p)
        dx = cx[:, None] - cx[None, :]
        dy = cy[:, None] - yi[None, :]
        r2 = dx * dx + dy * dy
        A_K += k0 * 0.5 * np.log(r2) * L                  # image current -K L at the image midpoint
        # image dipole m t* L, t* = (tx, -ty):  A = k0 * (t* x r)_z / r^2
        A_m += k0 * (tx[None, :] * dy + ty[None, :] * dx) / r2 * L
        Ht_K += -(L / TWO_PI) * ((-dy / r2) * tx[:, None] + (dx / r2) * ty[:, None])
        yni = -(mesh.ny + 2.0 * p)
        dyn2 = cy[:, None] - yni[None, :]
        r2 = dxn * dxn + dyn2 * dyn2
        Ht_q += (dxn * tx[:, None] + dyn2 * ty[:, None]) / (TWO_PI * r2)

    A_src, bx, by = source_abh(conductors, cx, cy, ground_model, rho, freq)
    Ht_src = (bx * tx + by * ty) / MU0

    groups = [] if closed_return else sorted(set(int(g) for g in mesh.group))
    ng = len(groups)
    gidx = {g: i for i, g in enumerate(groups)}
    nk = n if use_k else 0
    nm = n if use_m else 0
    size = nk + nm + (ng if use_k else 0)
    M = np.zeros((size, size), complex)
    rhs = np.zeros(size, complex)
    Ht_m = Ht_q @ mesh.inc if use_m else None

    if use_k:
        inv_ys = np.where(conducting, 1.0 / np.where(conducting, ys, 1.0), 0.0)
        M[:n, :n] = 1j * w * A_K + np.diag(inv_ys)
        if np.any(ls != 0.0):
            # series capacitor in a conductor loop: a drop -j w L_c I along each leg, I = that leg's current
            same = mesh.plate[:, None] == mesh.plate[None, :]
            M[:n, :n] += np.where(same, (-1j * w * ls)[:, None] * mesh.length[None, :], 0.0)
        if use_m:
            M[:n, nk:nk + n] = 1j * w * A_m
        if ng:
            for i in range(n):
                M[i, nk + nm + gidx[int(mesh.group[i])]] = 1.0
        rhs[:n] = -1j * w * A_src
        for g, gi in gidx.items():
            M[nk + nm + gi, :n] = np.where(mesh.group == g, mesh.length, 0.0)
        for i in np.nonzero(~conducting)[0]:            # a non-conducting plate carries no current
            M[i, :] = 0.0
            M[i, i] = 1.0
            rhs[i] = 0.0
        for g, gi in gidx.items():                      # a group with no conducting element: G = 0
            if not np.any(conducting & (mesh.group == g)):
                M[nk + nm + gi, :] = 0.0
                M[nk + nm + gi, nk + nm + gi] = 1.0
    if use_m:
        r0 = nk
        M[r0:r0 + n, nk:nk + n] = np.eye(n) - chi[:, None] * Ht_m
        if use_k:
            M[r0:r0 + n, :n] = -chi[:, None] * Ht_K
        rhs[r0:r0 + n] = chi * Ht_src

    scale = np.max(np.abs(M), axis=1)
    scale[scale == 0] = 1.0
    sol = np.linalg.solve(M / scale[:, None], rhs / scale)
    K = sol[:n] if use_k else np.zeros(n, complex)
    m = sol[nk:nk + n] if use_m else None
    out = MagneticSolution(mesh, K, m, conductors, ground_model, rho, freq, sg)
    out.ys = ys
    return out


def conductor_potential(conductors, q, X, Y):
    """
    Complex potential [V] of line charges q [C/m] on the conductors, above a perfectly
    conducting ground (each charge with its image). E = -grad V.
    """
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    V = np.zeros(X.shape, complex)
    k = 1.0 / (TWO_PI * EPS0)
    m2 = physics.MIN_DISTANCE_M ** 2
    for c, qi in zip(conductors, q):
        dx = X - c.x
        r2 = np.maximum(dx * dx + (Y - c.y_sagged) ** 2, m2)
        r2i = np.maximum(dx * dx + (Y + c.y_sagged) ** 2, m2)
        V += k * qi * 0.5 * np.log(r2i / r2)
    return V


# ---------------------------------------------------------------------------
# Electric solution
# ---------------------------------------------------------------------------
class ElectricSolution:
    """Solved conductor and barrier charges; evaluates the shielded E field."""

    def __init__(self, mesh: Mesh, conductors, q_cond, rho_s, v_float, kappa):
        self.mesh, self.conductors = mesh, conductors
        self.q_cond, self.rho, self.v_float, self.kappa = q_cond, rho_s, v_float, kappa

    def e_conductors(self, X, Y):
        """Complex (Ex, Ey) [V/m] of the line charges alone, as they are with the barrier present."""
        shape = np.shape(X)
        px = np.asarray(X, float).ravel(); py = np.asarray(Y, float).ravel()
        Ex = np.zeros(px.size, complex); Ey = np.zeros(px.size, complex)
        k = 1.0 / (TWO_PI * EPS0)
        m2 = physics.MIN_DISTANCE_M ** 2
        for c, q in zip(self.conductors, self.q_cond):
            dx = px - c.x
            dy = py - c.y_sagged
            r2 = np.maximum(dx * dx + dy * dy, m2)
            Ex += k * q * dx / r2; Ey += k * q * dy / r2
            dyi = py + c.y_sagged
            r2i = np.maximum(dx * dx + dyi * dyi, m2)
            Ex -= k * q * dx / r2i; Ey -= k * q * dyi / r2i
        return Ex.reshape(shape), Ey.reshape(shape)

    def e_induced(self, X, Y):
        """Complex (Ex, Ey) [V/m] of the charge the line induces on the barrier (and its image)."""
        shape = np.shape(X)
        px = np.asarray(X, float).ravel(); py = np.asarray(Y, float).ravel()
        Ex = np.zeros(px.size, complex); Ey = np.zeros(px.size, complex)
        k = 1.0 / (TWO_PI * EPS0)
        mesh = self.mesh
        h = mesh.h[None, :]
        px, py = _off_surface(mesh, px, py, 0.5 * mesh.ds)
        for s in range(0, px.size, _CHUNK):
            sl = slice(s, s + _CHUNK)
            u, v = _local(px[sl], py[sl], mesh.cx, mesh.cy, mesh.tx, mesh.ty)
            _, th, lam = _kernels(u, v, h, need_ln=False)
            gx, gy = _to_global(lam, th, mesh.tx[None, :], mesh.ty[None, :])
            Ex[sl] += k * (gx @ self.rho); Ey[sl] += k * (gy @ self.rho)
            itx, ity = mesh.tx, -mesh.ty
            u, v = _local(px[sl], py[sl], mesh.cx, -mesh.cy, itx, ity)
            _, th, lam = _kernels(u, v, h, need_ln=False)
            gx, gy = _to_global(lam, th, itx[None, :], ity[None, :])
            Ex[sl] -= k * (gx @ self.rho); Ey[sl] -= k * (gy @ self.rho)
        return Ex.reshape(shape), Ey.reshape(shape)

    def e_total(self, X, Y):
        """Complex (Ex, Ey) [V/m] with the barrier present."""
        exc, eyc = self.e_conductors(X, Y)
        exs, eys = self.e_induced(X, Y)
        return exc + exs, eyc + eys

    def v_induced(self, X, Y):
        """Complex potential [V] of the charge on the barrier (and its image)."""
        shape = np.shape(X)
        px = np.asarray(X, float).ravel(); py = np.asarray(Y, float).ravel()
        V = np.zeros(px.size, complex)
        k = 1.0 / (TWO_PI * EPS0)
        mesh = self.mesh
        h = mesh.h[None, :]
        for s in range(0, px.size, _CHUNK):
            sl = slice(s, s + _CHUNK)
            u, v = _local(px[sl], py[sl], mesh.cx, mesh.cy, mesh.tx, mesh.ty)
            i1, _, _ = _kernels(u, v, h)
            u, v = _local(px[sl], py[sl], mesh.cx, -mesh.cy, mesh.tx, -mesh.ty)
            i2, _, _ = _kernels(u, v, h)
            V[sl] = k * ((i2 - i1) @ self.rho)
        return V.reshape(shape)

    def v_total(self, X, Y):
        """Complex potential [V] with the barrier present. E = -grad V."""
        return conductor_potential(self.conductors, self.q_cond, X, Y) + self.v_induced(X, Y)

    def e_rms_kVm(self, X, Y):
        ex, ey = self.e_total(X, Y)
        return np.sqrt(np.abs(ex) ** 2 + np.abs(ey) ** 2) / 1000.0

    @property
    def floating_voltage_kv(self) -> float:
        """Largest induced voltage on any unearthed plate [kV rms]."""
        return float(max((abs(v) for v in self.v_float.values()), default=0.0)) / 1000.0

    def earth_current_ma_per_m(self, freq: float) -> float:
        """Capacitive current flowing to earth through the earthed plates [mA per metre of line]."""
        gnd = self.mesh.grounded
        if not np.any(gnd):
            return 0.0
        q = np.sum(self.rho[gnd] * self.mesh.length[gnd])
        return float(TWO_PI * freq * abs(q) * 1000.0)


def relaxation_factor(cfg: ShieldConfig, freq: float, height_m: float) -> complex:
    """
    How completely the barrier behaves as an equipotential for the E field:
    kappa = 1 / (1 + j w tau), tau = eps0 * H / (sigma * t). Essentially 1 for
    every metal, concrete and vegetation; tends to 0 for a true insulator.
    """
    mat = cfg.material
    g = mat.sigma * cfg.thickness_m * cfg.fill_factor
    if g <= 0:
        return 0.0
    tau = EPS0 * max(height_m, 0.5) / g
    return 1.0 / (1.0 + 1j * TWO_PI * freq * tau)


def solve_electric(geom: Geometry, cfg: ShieldConfig, conductors, freq: float,
                   bundle_eq: bool = True, mesh: Optional[Mesh] = None
                   ) -> Optional[ElectricSolution]:
    if not geom.plates or not conductors:
        return None
    mesh = mesh or build_mesh(geom.plates)
    n = mesh.n
    if n == 0:
        return None
    k = 1.0 / (TWO_PI * EPS0)
    nc = len(conductors)
    P = physics.build_potential_coefficient_matrix(conductors, bundle_equivalent=bundle_eq)
    V = np.array([(c.voltage_kV * 1000.0 / math.sqrt(3.0)) * np.exp(1j * physics.conductor_angle_rad(c))
                  for c in conductors])
    cxc = np.array([c.x for c in conductors]); cyc = np.array([c.y_sagged for c in conductors])
    h = mesh.h[None, :]

    def strip_potential(px, py):
        u, v = _local(px, py, mesh.cx, mesh.cy, mesh.tx, mesh.ty)
        i1, _, _ = _kernels(u, v, h)
        u, v = _local(px, py, mesh.cx, -mesh.cy, mesh.tx, -mesh.ty)
        i2, _, _ = _kernels(u, v, h)
        return k * (i2 - i1)                     # potential per unit surface charge

    phi_ss = strip_potential(mesh.cx, mesh.cy)
    phi_cs = strip_potential(cxc, cyc)
    dx = mesh.cx[:, None] - cxc[None, :]
    r2 = dx * dx + (mesh.cy[:, None] - cyc[None, :]) ** 2
    r2i = dx * dx + (mesh.cy[:, None] + cyc[None, :]) ** 2
    phi_sc = k * 0.5 * np.log(r2i / np.maximum(r2, 1e-12))

    fgroups = sorted(set(int(g) for g, gd in zip(mesh.group, mesh.grounded) if not gd))
    fidx = {g: i for i, g in enumerate(fgroups)}
    nf = len(fgroups)
    size = nc + n + nf
    M = np.zeros((size, size), complex)
    rhs = np.zeros(size, complex)
    M[:nc, :nc] = P
    M[:nc, nc:nc + n] = phi_cs
    rhs[:nc] = V
    M[nc:nc + n, :nc] = phi_sc
    M[nc:nc + n, nc:nc + n] = phi_ss
    for i in range(n):
        if not mesh.grounded[i]:
            gi = fidx[int(mesh.group[i])]
            M[nc + i, nc + n + gi] = -1.0
            M[nc + n + gi, nc + i] = mesh.length[i]
    scale = np.max(np.abs(M), axis=1)
    scale[scale == 0] = 1.0
    try:
        sol = np.linalg.solve(M / scale[:, None], rhs / scale)
    except np.linalg.LinAlgError:
        sol = np.linalg.lstsq(M / scale[:, None], rhs / scale, rcond=None)[0]
    q_cond = sol[:nc]
    rho_s = sol[nc:nc + n]
    v_float = {g: sol[nc + n + i] for g, i in fidx.items()}
    height = float(np.max(mesh.cy + mesh.h) - np.min(mesh.cy - mesh.h)) if n else 1.0
    kappa = relaxation_factor(cfg, freq, max(height, mesh.ds))
    if abs(kappa - 1.0) > 1e-3:
        # Poor conductor: only part of the ideal induced charge has time to form.
        q0 = physics.solve_conductor_charges(conductors, bundle_equivalent=bundle_eq)
        rho_s = rho_s * kappa
        q_cond = q0 + (q_cond - q0) * kappa
    return ElectricSolution(mesh, conductors, q_cond, rho_s, v_float, kappa)
