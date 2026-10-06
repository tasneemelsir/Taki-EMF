"""
earth.py
========
Earth-return / ground-model options for the "Taki" EMF Dashboard.

------------------------------------------------------------------------
WHY THIS EXISTS
------------------------------------------------------------------------
Taki originally computed the magnetic field from free-space Biot-Savart
with no earth-return path at all, while computing the ELECTRIC field with
the method of images (which implicitly assumes a perfectly conducting
ground). The two solvers therefore made *different* assumptions about the
same ground, and neither was selectable.

That inconsistency showed up immediately in code-to-code verification
against Fikry et al. (2022), whose reference solver reports conducting and
non-conducting ground separately and differs by roughly a factor of two
between them.

------------------------------------------------------------------------
THE THREE MODELS, AND HOW MUCH TO TRUST EACH
------------------------------------------------------------------------
FREE_SPACE and PERFECT_CONDUCTOR are the two EXACT limits of earth
resistivity:

    FREE_SPACE        rho -> infinity   no image, no earth return
    PERFECT_CONDUCTOR rho -> 0          mirror image at -h, current
                                        reversed

Real earth always lies between them. That is the useful property: running
both gives a defensible upper and lower bound on the field without having
to defend a particular resistivity value. For screening work, bracketing
is often more honest than a single number.

COMPLEX_IMAGE is the finite-resistivity case, using the complex-depth
approximation (Deri et al.): the earth-return image sits at depth
(h + 2p), where

    p = sqrt(rho / (j * omega * mu0))

is the complex penetration depth. This is a standard and widely used
approximation, but Taki's implementation of it has NOT yet been validated
against reference data, so it is flagged accordingly and is not the
default. Treat its output as indicative until that validation exists.

------------------------------------------------------------------------
WHICH QUANTITY EACH MODEL AFFECTS
------------------------------------------------------------------------
B field: all three models differ, because the earth-return current is a
         real additional source.

E field: the method of images already assumes a perfectly conducting
         ground. PERFECT_CONDUCTOR is therefore the physically consistent
         choice and reproduces Taki's existing E-field behaviour exactly.
         FREE_SPACE removes the image (a poor model for E over real soil,
         offered only for completeness and consistency of the UI).
"""

import numpy as np

from .physics import MU0

# ---------------------------------------------------------------------------
# Model identifiers
# ---------------------------------------------------------------------------
FREE_SPACE = "free_space"
PERFECT_CONDUCTOR = "perfect_conductor"
COMPLEX_IMAGE = "complex_image"

DEFAULT_MODEL = PERFECT_CONDUCTOR

#: Typical earth resistivities [ohm-m], for the UI's resistivity picker.
TYPICAL_RESISTIVITY = {
    "Wet organic soil": 10.0,
    "Moist soil / farmland": 100.0,
    "Dry soil": 1000.0,
    "Bedrock": 10000.0,
}

MODEL_INFO = {
    FREE_SPACE: {
        "label": "Free space (no earth return)",
        "short": "No earth return",
        "limit": "rho -> infinity",
        "validated": True,
        "description": (
            "No ground image. The exact limit of infinitely resistive earth, "
            "and the behaviour of Taki's original B-field solver. Gives the "
            "LOWER bound on magnetic field for most geometries."
        ),
        "caution": (
            "Applied to the E field this removes the ground plane entirely, "
            "which is not a realistic soil model — it is offered only so the "
            "two solvers can be driven from one consistent setting."
        ),
    },
    PERFECT_CONDUCTOR: {
        "label": "Perfectly conducting earth",
        "short": "Conducting earth",
        "limit": "rho -> 0",
        "validated": True,
        "description": (
            "Mirror image at -h carrying reversed current. The exact limit of "
            "zero-resistivity earth, and the assumption already built into "
            "Taki's method-of-images E-field solver. Gives the UPPER bound on "
            "magnetic field for most geometries."
        ),
        "caution": "",
    },
    COMPLEX_IMAGE: {
        "label": "Finite resistivity (complex image)",
        "short": "Finite resistivity",
        "limit": "0 < rho < infinity",
        "validated": False,
        "description": (
            "Earth-return image placed at complex depth (h + 2p), with "
            "p = sqrt(rho / (j*omega*mu0)) after Deri et al. Interpolates "
            "between the two exact limits as resistivity varies."
        ),
        "caution": (
            "NOT YET VALIDATED against reference data in Taki. Use the two "
            "exact limits to bracket the answer for any result that will be "
            "reported or certified."
        ),
    },
}


def is_validated(model: str) -> bool:
    """Whether this model's implementation has been checked against a limit."""
    return bool(MODEL_INFO.get(model, {}).get("validated", False))


def complex_depth(resistivity_ohm_m: float, freq_Hz: float = 50.0) -> complex:
    """
    Complex penetration depth p = sqrt(rho / (j*omega*mu0)) [m].

    For rho = 100 ohm-m at 50 Hz this is roughly 356 - 356j m, i.e. the
    earth-return image sits several hundred metres down — which is why
    finite-resistivity earth behaves much more like free space than like
    a perfect conductor for overhead lines.
    """
    omega = 2.0 * np.pi * freq_Hz
    if resistivity_ohm_m <= 0:
        return 0.0 + 0.0j
    return np.sqrt(resistivity_ohm_m / (1j * omega * MU0))


def image_depth(y: float, model: str, resistivity_ohm_m: float = 100.0,
                freq_Hz: float = 50.0):
    """
    Y-coordinate of the earth-return image for a source at height `y`.

    Returns None when the model has no image (free space). The returned
    value may be complex for COMPLEX_IMAGE; callers must do the distance
    arithmetic in complex and take the magnitude at the end.
    """
    if model == FREE_SPACE:
        return None
    if model == PERFECT_CONDUCTOR:
        return -y
    if model == COMPLEX_IMAGE:
        p = complex_depth(resistivity_ohm_m, freq_Hz)
        return -(y + 2.0 * p)
    raise ValueError(f"Unknown ground model: {model!r}")


def b_field_image_contribution(x_pts, y_pts, wx: float, wy: float,
                               current_phasor: complex, model: str,
                               resistivity_ohm_m: float = 100.0,
                               freq_Hz: float = 50.0,
                               min_distance_m: float = 1e-3):
    """
    Complex (Bx, By) contribution in TESLA from the earth-return image of
    a single sub-conductor at (wx, wy) carrying `current_phasor`.

    Returns (0, 0) arrays for FREE_SPACE. The image carries the NEGATIVE
    of the source current, which is what enforces the boundary condition
    at a conducting ground plane.

    Args:
        x_pts, y_pts    : field-point coordinate arrays (broadcastable)
        wx, wy          : sub-conductor position [m]
        current_phasor  : complex current [A]
        model           : one of the module's model identifiers
        resistivity_ohm_m, freq_Hz : used by COMPLEX_IMAGE only
        min_distance_m  : singularity floor

    Returns:
        (Bx, By) complex arrays [T]
    """
    x_pts = np.asarray(x_pts, dtype=float)
    y_pts = np.asarray(y_pts, dtype=float)

    y_img = image_depth(wy, model, resistivity_ohm_m, freq_Hz)
    if y_img is None:
        zeros = np.zeros(np.broadcast(x_pts, y_pts).shape, dtype=complex)
        return zeros, zeros.copy()

    # Image current is the negative of the source current.
    i_img = -current_phasor

    dx = x_pts - wx
    dy = y_pts - y_img            # may be complex for COMPLEX_IMAGE
    r2 = dx * dx + dy * dy
    # Floor the magnitude, not the (possibly complex) value itself.
    r2 = np.where(np.abs(r2) < min_distance_m ** 2, min_distance_m ** 2, r2)
    r = np.sqrt(r2)

    b_mag = (MU0 * i_img) / (2.0 * np.pi * r)
    # Unit vector tangential to the circular field around the image.
    bx = b_mag * (-dy / r)
    by = b_mag * (dx / r)
    return bx, by


def describe(model: str, resistivity_ohm_m: float = 100.0) -> str:
    """One-line description for reports and figure subtitles."""
    info = MODEL_INFO.get(model)
    if info is None:
        return f"Unknown ground model ({model})"
    if model == COMPLEX_IMAGE:
        return f"{info['label']}, rho = {resistivity_ohm_m:.0f} ohm-m"
    return info["label"]
