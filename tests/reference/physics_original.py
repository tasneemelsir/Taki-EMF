"""
physics.py
==========
Core physics engine for the "Taki" EMF Simulation Dashboard.

Implements:
  1. Magnetic field (B) calculation using the Biot-Savart law for
     infinite straight parallel conductors, with full 3-phase AC
     phasor (complex) superposition.
  2. Electric field (E) calculation using the Method of Images and
     Maxwell's Potential Coefficient Matrix to solve for conductor
     surface charge densities from applied phase voltages.
  3. Thermal sag model relating conductor loading (%) to a reduction
     in conductor height (ground clearance).

All field outputs are returned in engineering-friendly units:
  - B field -> microtesla (uT)
  - E field -> kilovolts per metre (kV/m)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
MU0 = 4 * np.pi * 1e-7          # Permeability of free space [H/m]
EPS0 = 8.8541878128e-12         # Permittivity of free space [F/m]

# Small numerical floor to avoid division-by-zero when a field point
# coincides exactly with a conductor location.
MIN_DISTANCE_M = 1e-3


def _earth_module():
    """
    Imported lazily: earth.py imports MU0 from this module, so a
    top-level import here would be circular.
    """
    import earth
    return earth


class _EarthProxy:
    """Thin lazy proxy so call sites can read like `_earth.FREE_SPACE`."""
    def __getattr__(self, name):
        return getattr(_earth_module(), name)


_earth = _EarthProxy()


@dataclass
class Conductor:
    """
    Represents a single physical conductor (phase wire) in the tower
    configuration.

    Attributes:
        x        : Horizontal position [m], line centre = 0
        y_base   : Nominal (no-sag / no-load) height above ground [m]
        phase    : 'A', 'B', or 'C' - determines the 120 deg phase shift
        circuit  : circuit identifier (1 or 2) for double-circuit towers
        current_A: RMS phase current magnitude [A]
        voltage_kV: Line-to-line RMS voltage magnitude [kV]
        bundle_offsets: list of (dx, dy) offsets [m] for bundled sub-conductors
                        (e.g. quadruple bundle on 500kV lines). If empty,
                        the conductor is treated as a single wire.
    """
    x: float
    y_base: float
    phase: str
    circuit: int = 1
    current_A: float = 0.0
    voltage_kV: float = 0.0
    bundle_offsets: List[Tuple[float, float]] = field(default_factory=list)

    # Physical/bundle radius [m] used for the E-field self-potential term.
    # If left as None, callers fall back to a scalar conductor_radius_m
    # argument. Set explicitly when combining conductors from different
    # tower presets (e.g. multiple parallel lines) so each keeps its own
    # correct physical radius rather than sharing one global value.
    radius_m: float = None

    # runtime (sagged) height - populated by apply_sag()
    y_sagged: float = None

    def __post_init__(self):
        if self.y_sagged is None:
            self.y_sagged = self.y_base


# Phase angle lookup (degrees) for a balanced 3-phase system
PHASE_ANGLE_DEG = {"A": 0.0, "B": -120.0, "C": 120.0}


def phase_angle_rad(phase: str) -> float:
    """Return the phase angle in radians for phase label 'A'/'B'/'C'."""
    return np.deg2rad(PHASE_ANGLE_DEG.get(phase.upper(), 0.0))


# ---------------------------------------------------------------------------
# Thermal sag model
# ---------------------------------------------------------------------------
def compute_sag_offset(load_percent: float, max_sag_m: float = 1.5) -> float:
    """
    Simplified thermal sag model.

    As current loading increases, conductor temperature rises, the
    conductor expands, and mechanical sag increases -> the effective
    mid-span height above ground decreases.

    A quadratic relationship is used (I^2*R heating means thermal
    expansion roughly tracks loading^2 over moderate ranges), clipped
    to [0, ~max_sag_m].

    Args:
        load_percent: line loading as a percentage of rated ampacity (0-100+)
        max_sag_m: maximum additional sag at 100% loading [m]

    Returns:
        Sag offset (positive number of metres the conductor drops).
    """
    load_fraction = np.clip(load_percent / 100.0, 0.0, 1.5)  # allow slight overload
    sag = max_sag_m * (load_fraction ** 2)
    return float(np.clip(sag, 0.0, max_sag_m * 1.05))


def apply_sag(conductors: List[Conductor], load_percent: float,
              max_sag_m: float = 1.5) -> List[Conductor]:
    """
    Returns a NEW list of conductors with y_sagged updated according to
    the current loading percentage. Original list is left untouched.
    """
    offset = compute_sag_offset(load_percent, max_sag_m)
    sagged = []
    for c in conductors:
        new_c = Conductor(
            x=c.x, y_base=c.y_base, phase=c.phase, circuit=c.circuit,
            current_A=c.current_A, voltage_kV=c.voltage_kV,
            bundle_offsets=list(c.bundle_offsets),
        )
        new_c.y_sagged = max(c.y_base - offset, 0.5)  # never let it hit ground
        sagged.append(new_c)
    return sagged


# ---------------------------------------------------------------------------
# Magnetic Field (Biot-Savart, infinite straight wire, phasor superposition)
# ---------------------------------------------------------------------------
def _sub_conductor_positions(c: Conductor) -> List[Tuple[float, float, float]]:
    """
    Expand a Conductor into its physical sub-conductor positions (for
    bundled conductors) along with the current carried by EACH
    sub-conductor (total current is split evenly across the bundle).

    Returns a list of (x, y, current_per_subconductor).
    """
    if not c.bundle_offsets:
        return [(c.x, c.y_sagged, c.current_A)]
    n = len(c.bundle_offsets)
    i_sub = c.current_A / n
    return [(c.x + dx, c.y_sagged + dy, i_sub) for dx, dy in c.bundle_offsets]


def compute_b_field_at_points(conductors: List[Conductor],
                               x_pts: np.ndarray,
                               y_pts: np.ndarray,
                               ground_model: str = None,
                               earth_resistivity_ohm_m: float = 100.0,
                               freq_Hz: float = 50.0) -> np.ndarray:
    """
    Compute the RMS resultant magnetic flux density (in microtesla) at
    an arbitrary set of field points using the Biot-Savart law for
    infinite straight parallel current-carrying conductors combined
    with full complex (phasor) superposition for a 3-phase AC system.

    Physics:
        For an infinite straight wire carrying current I, the magnetic
        field magnitude at perpendicular distance r is:
            B = (mu0 * I) / (2 * pi * r)
        directed tangentially (perpendicular to the radius vector, i.e.
        circling the wire per the right-hand rule).

        Because each phase current is a complex phasor
        (I_A, I_B, I_C separated by 120 degrees), the Bx and By
        components from every conductor are summed as COMPLEX
        quantities (magnitude + phase) before being combined into a
        resultant field. This correctly captures both the
        constructive/destructive interference between phases AND the
        elliptical/rotating nature of the AC magnetic field.

        The reported "resultant" field magnitude uses the standard
        industry simplification:
            B_result = sqrt(|Bx_phasor|^2 + |By_phasor|^2)
        representing the maximum magnitude of the (generally
        elliptical) field vector locus - the conventional way EMF
        software reports a single scalar B value.

    Args:
        conductors: list of Conductor objects (with y_sagged already set)
        x_pts, y_pts: numpy arrays of field point coordinates [m].
                      Must be broadcastable to the same shape.
        ground_model: earth-return model from earth.py. None (the
                      default) means FREE_SPACE, i.e. no earth return -
                      preserving this function's original behaviour
                      exactly for every existing caller.
        earth_resistivity_ohm_m, freq_Hz: used only by the complex-image
                      model; ignored otherwise.

    Earth return:
        A conducting earth carries return current, which contributes its
        own field. This is modelled by adding an image sub-conductor
        carrying the NEGATIVE of the source current (see earth.py for
        the placement rules and how much each model can be trusted).
        The image field is summed as a complex phasor alongside the
        direct field, before the magnitude is taken - so interference
        between the direct and earth-return paths is captured correctly.

    Returns:
        numpy array (same shape as x_pts) of B field magnitude in
        microtesla (uT).
    """
    x_pts = np.asarray(x_pts, dtype=float)
    y_pts = np.asarray(y_pts, dtype=float)

    Bx = np.zeros(x_pts.shape, dtype=complex)
    By = np.zeros(x_pts.shape, dtype=complex)

    for c in conductors:
        theta = phase_angle_rad(c.phase)
        for (wx, wy, i_sub) in _sub_conductor_positions(c):
            # Complex current phasor (RMS magnitude, phase angle)
            I_phasor = i_sub * np.exp(1j * theta)

            dx = x_pts - wx
            dy = y_pts - wy
            r2 = dx ** 2 + dy ** 2
            r2 = np.where(r2 < MIN_DISTANCE_M ** 2, MIN_DISTANCE_M ** 2, r2)
            r = np.sqrt(r2)

            # Biot-Savart magnitude phasor for this conductor at each point
            B_mag = (MU0 * I_phasor) / (2 * np.pi * r)

            # Direction: field circles the wire, perpendicular to the
            # radius vector (dx, dy). Unit tangential vector = (-dy/r, dx/r)
            ux = -dy / r
            uy = dx / r

            Bx += B_mag * ux
            By += B_mag * uy

            # Earth-return image contribution (no-op for free space).
            if ground_model is not None and ground_model != _earth.FREE_SPACE:
                ibx, iby = _earth.b_field_image_contribution(
                    x_pts, y_pts, wx, wy, I_phasor, ground_model,
                    earth_resistivity_ohm_m, freq_Hz, MIN_DISTANCE_M,
                )
                Bx = Bx + ibx
                By = By + iby

    B_result = np.sqrt(np.abs(Bx) ** 2 + np.abs(By) ** 2)  # Tesla
    return B_result * 1e6  # Convert Tesla -> microtesla


def compute_b_field_1d(conductors: List[Conductor], x_range: np.ndarray,
                        y_height: float = 1.0, ground_model: str = None,
                        earth_resistivity_ohm_m: float = 100.0) -> np.ndarray:
    """Convenience wrapper: B field along a horizontal line at fixed height."""
    y_pts = np.full_like(x_range, y_height, dtype=float)
    return compute_b_field_at_points(conductors, x_range, y_pts,
                                      ground_model, earth_resistivity_ohm_m)


def compute_b_field_grid(conductors: List[Conductor], x_range: np.ndarray,
                          y_range: np.ndarray, ground_model: str = None,
                          earth_resistivity_ohm_m: float = 100.0) -> np.ndarray:
    """Convenience wrapper: B field over a 2D (X, Y) meshgrid. Returns
    a 2D array shaped (len(y_range), len(x_range))."""
    Xg, Yg = np.meshgrid(x_range, y_range)
    return compute_b_field_at_points(conductors, Xg, Yg,
                                      ground_model, earth_resistivity_ohm_m)


# ---------------------------------------------------------------------------
# Electric Field (Method of Images + Maxwell Potential Coefficient Matrix)
# ---------------------------------------------------------------------------
def build_potential_coefficient_matrix(conductors: List[Conductor],
                                        conductor_radius_m: float = 0.015) -> np.ndarray:
    """
    Build Maxwell's potential coefficient matrix [P] for a system of
    parallel conductors above a perfectly conducting ground plane,
    using the Method of Images.

    Diagonal terms (self potential coefficient):
        P_ii = (1 / (2*pi*eps0)) * ln(2*h_i / r_i)
    where h_i is conductor height above ground and r_i its physical radius.

    Off-diagonal terms (mutual potential coefficient):
        P_ij = (1 / (2*pi*eps0)) * ln(D_ij' / D_ij)
    where D_ij is the direct distance between conductors i and j, and
    D_ij' is the distance between conductor i and the IMAGE of
    conductor j (mirrored below the ground plane).

    The matrix relates conductor voltages to line charge densities:
        [V] = [P] * [q]   =>   [q] = [P]^-1 * [V]

    Returns:
        NxN real-valued numpy array [P] (units: 1/Farad per metre)
    """
    n = len(conductors)
    P = np.zeros((n, n))
    k = 1.0 / (2 * np.pi * EPS0)

    for i, ci in enumerate(conductors):
        for j, cj in enumerate(conductors):
            if i == j:
                h = max(ci.y_sagged, 0.5)
                r_i = ci.radius_m if ci.radius_m else conductor_radius_m
                P[i, j] = k * np.log(2 * h / r_i)
            else:
                # Direct distance between conductor i and conductor j
                Dij = np.hypot(ci.x - cj.x, ci.y_sagged - cj.y_sagged)
                Dij = max(Dij, MIN_DISTANCE_M)
                # Distance between conductor i and the IMAGE of conductor j
                Dij_image = np.hypot(ci.x - cj.x, ci.y_sagged + cj.y_sagged)
                Dij_image = max(Dij_image, MIN_DISTANCE_M)
                P[i, j] = k * np.log(Dij_image / Dij)
    return P


def solve_conductor_charges(conductors: List[Conductor],
                             conductor_radius_m: float = 0.015) -> np.ndarray:
    """
    Solve for the complex line-charge-density phasors [q] (C/m) on each
    conductor, given their applied phase voltage magnitudes and 3-phase
    phase angles.

    [V] = [P] [q]  =>  [q] = [P]^-1 [V]

    Returns:
        complex numpy array of length N (one charge phasor per conductor)
    """
    P = build_potential_coefficient_matrix(conductors, conductor_radius_m)

    V_phasors = np.array([
        # voltage_kV is treated as LINE-LINE kV; divide by sqrt(3) to get
        # phase (line-to-ground) voltage before solving for charges.
        (c.voltage_kV * 1000.0 / np.sqrt(3)) * np.exp(1j * phase_angle_rad(c.phase))
        for c in conductors
    ])

    try:
        q = np.linalg.solve(P, V_phasors)
    except np.linalg.LinAlgError:
        # Singular matrix fallback (e.g. degenerate geometry) - use
        # pseudo-inverse to avoid a hard crash.
        q = np.linalg.pinv(P) @ V_phasors
    return q


def compute_e_field_at_points(conductors: List[Conductor],
                               x_pts: np.ndarray, y_pts: np.ndarray,
                               conductor_radius_m: float = 0.015) -> np.ndarray:
    """
    Compute the RMS resultant electric field (kV/m) at arbitrary field
    points using the Method of Images: each real conductor charge q_i
    at height y_i is paired with an equal-and-opposite image charge
    -q_i at -y_i, enforcing E=0 (ground = equipotential) at y=0.

    E field from an infinite line charge at perpendicular distance r:
        E = q / (2 * pi * eps0 * r)   [V/m], directed radially.

    Total field = complex superposition of Ex, Ey contributions from
    every real conductor AND every image conductor.

    Returns:
        numpy array (same shape as x_pts) of E field magnitude, kV/m
    """
    x_pts = np.asarray(x_pts, dtype=float)
    y_pts = np.asarray(y_pts, dtype=float)

    q = solve_conductor_charges(conductors, conductor_radius_m)
    k = 1.0 / (2 * np.pi * EPS0)

    Ex = np.zeros(x_pts.shape, dtype=complex)
    Ey = np.zeros(x_pts.shape, dtype=complex)

    for c, qi in zip(conductors, q):
        # --- Real conductor contribution ---
        dx = x_pts - c.x
        dy = y_pts - c.y_sagged
        r2 = dx ** 2 + dy ** 2
        r2 = np.where(r2 < MIN_DISTANCE_M ** 2, MIN_DISTANCE_M ** 2, r2)
        r = np.sqrt(r2)
        E_mag = k * qi / r
        Ex += E_mag * (dx / r)
        Ey += E_mag * (dy / r)

        # --- Image conductor contribution (charge = -qi, mirrored below ground) ---
        dy_im = y_pts + c.y_sagged
        r2_im = dx ** 2 + dy_im ** 2
        r2_im = np.where(r2_im < MIN_DISTANCE_M ** 2, MIN_DISTANCE_M ** 2, r2_im)
        r_im = np.sqrt(r2_im)
        E_mag_im = k * (-qi) / r_im
        Ex += E_mag_im * (dx / r_im)
        Ey += E_mag_im * (dy_im / r_im)

    E_result = np.sqrt(np.abs(Ex) ** 2 + np.abs(Ey) ** 2)  # V/m
    return E_result / 1000.0  # Convert V/m -> kV/m


def compute_e_field_1d(conductors: List[Conductor], x_range: np.ndarray,
                        y_height: float = 1.0,
                        conductor_radius_m: float = 0.015) -> np.ndarray:
    """Convenience wrapper: E field along a horizontal line at fixed height."""
    y_pts = np.full_like(x_range, y_height, dtype=float)
    return compute_e_field_at_points(conductors, x_range, y_pts, conductor_radius_m)


def compute_e_field_grid(conductors: List[Conductor], x_range: np.ndarray,
                          y_range: np.ndarray,
                          conductor_radius_m: float = 0.015) -> np.ndarray:
    """Convenience wrapper: E field over a 2D (X, Y) meshgrid."""
    Xg, Yg = np.meshgrid(x_range, y_range)
    return compute_e_field_at_points(conductors, Xg, Yg, conductor_radius_m)


# ---------------------------------------------------------------------------
# Tower preset library
# ---------------------------------------------------------------------------
def get_tower_presets() -> dict:
    """
    Returns a dictionary of standard TNB-style tower configurations.
    Each conductor entry: x [m], y_base [m], phase, circuit, current_A,
    voltage_kV (line-to-line), bundle_offsets.

    NOTE: Geometry and loading values are representative engineering
    approximations for simulation/demo purposes, not exact TNB
    as-built drawings.
    """
    presets = {
        "132kV Double Circuit Lattice": {
            "description": "Double circuit lattice tower, vertical phase "
                            "configuration, single conductor per phase.",
            "conductor_radius_m": 0.0135,
            "row_width_m": 24.0,
            "conductors": [
                # Circuit 1 (left side of tower centreline)
                Conductor(x=-3.0, y_base=24.0, phase="A", circuit=1, current_A=600, voltage_kV=132),
                Conductor(x=-3.0, y_base=20.0, phase="B", circuit=1, current_A=600, voltage_kV=132),
                Conductor(x=-3.0, y_base=16.0, phase="C", circuit=1, current_A=600, voltage_kV=132),
                # Circuit 2 (right side of tower centreline)
                Conductor(x=3.0, y_base=24.0, phase="A", circuit=2, current_A=600, voltage_kV=132),
                Conductor(x=3.0, y_base=20.0, phase="B", circuit=2, current_A=600, voltage_kV=132),
                Conductor(x=3.0, y_base=16.0, phase="C", circuit=2, current_A=600, voltage_kV=132),
            ],
        },
        "275kV Monopole": {
            "description": "Single circuit monopole (steel pole), horizontal "
                            "flat phase configuration, twin-bundle conductors.",
            "conductor_radius_m": 0.02,
            "row_width_m": 30.0,
            "conductors": [
                Conductor(x=-6.0, y_base=28.0, phase="A", circuit=1, current_A=1200,
                          voltage_kV=275, bundle_offsets=[(-0.2, 0), (0.2, 0)]),
                Conductor(x=0.0, y_base=28.0, phase="B", circuit=1, current_A=1200,
                          voltage_kV=275, bundle_offsets=[(-0.2, 0), (0.2, 0)]),
                Conductor(x=6.0, y_base=28.0, phase="C", circuit=1, current_A=1200,
                          voltage_kV=275, bundle_offsets=[(-0.2, 0), (0.2, 0)]),
            ],
        },
        "500kV Quadruple Bundle": {
            "description": "Single circuit lattice tower, horizontal flat "
                            "configuration, quadruple-bundle conductors per phase.",
            "conductor_radius_m": 0.0165,
            "row_width_m": 40.0,
            "conductors": [
                Conductor(x=-11.0, y_base=32.0, phase="A", circuit=1, current_A=2000,
                          voltage_kV=500,
                          bundle_offsets=[(-0.23, -0.23), (0.23, -0.23), (0.23, 0.23), (-0.23, 0.23)]),
                Conductor(x=0.0, y_base=32.0, phase="B", circuit=1, current_A=2000,
                          voltage_kV=500,
                          bundle_offsets=[(-0.23, -0.23), (0.23, -0.23), (0.23, 0.23), (-0.23, 0.23)]),
                Conductor(x=11.0, y_base=32.0, phase="C", circuit=1, current_A=2000,
                          voltage_kV=500,
                          bundle_offsets=[(-0.23, -0.23), (0.23, -0.23), (0.23, 0.23), (-0.23, 0.23)]),
            ],
        },
    }
    return presets


def translate_conductors(conductors: List[Conductor], dx: float) -> List[Conductor]:
    """
    Shift every conductor's X position by dx metres. Used to place
    multiple independent transmission lines side by side (in parallel)
    on the same shared X/Y/Z coordinate system, so their fields can be
    superposed exactly like any other set of conductors (Biot-Savart and
    the Method of Images are both linear in the individual conductor
    contributions, so simple concatenation of translated conductor lists
    is physically correct for total-field superposition).

    Returns a NEW list; does not mutate the input.
    """
    out = []
    for c in conductors:
        new_c = Conductor(
            x=c.x + dx, y_base=c.y_base, phase=c.phase, circuit=c.circuit,
            current_A=c.current_A, voltage_kV=c.voltage_kV,
            bundle_offsets=list(c.bundle_offsets), radius_m=c.radius_m,
        )
        new_c.y_sagged = c.y_sagged
        out.append(new_c)
    return out


def apply_phase_swap(conductors: List[Conductor], arrangement: str) -> List[Conductor]:
    """
    For double-circuit towers, re-assign the phase labels of circuit 2
    according to the chosen phase-cancellation arrangement.

    Arrangements:
        "ABC-ABC" : both circuits carry identical phase order (worst case
                    for magnetic field cancellation - fields tend to add)
        "ABC-CBA" : circuit 2 phase order reversed relative to circuit 1
                    (promotes magnetic field cancellation between
                    circuits, commonly used in real double-circuit
                    designs to reduce ROW EMF)

    Returns a NEW list of Conductor objects; does not mutate the input.
    """
    swap_map = {"A": "C", "B": "B", "C": "A"}  # simple reversal mapping
    out = []
    for c in conductors:
        new_c = Conductor(
            x=c.x, y_base=c.y_base, phase=c.phase, circuit=c.circuit,
            current_A=c.current_A, voltage_kV=c.voltage_kV,
            bundle_offsets=list(c.bundle_offsets),
        )
        new_c.y_sagged = c.y_sagged
        if arrangement == "ABC-CBA" and c.circuit == 2:
            new_c.phase = swap_map[c.phase]
        out.append(new_c)
    return out
