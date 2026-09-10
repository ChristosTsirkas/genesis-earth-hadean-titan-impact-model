#!/usr/bin/env python3
"""
delivery_monte_carlo.py
=======================

Stage 1 — local CPU orbital-delivery Monte Carlo for Paper I.

This module is a reduced analytical specification engine, not a substitute for a
full Nice-model N-body simulation. It generates locally scattered heliocentric
orbits, evaluates whether they become Earth-crossing, computes the relative
approach speed at infinity, applies Safronov gravitational focusing, and retains
only encounter-plane trajectories that intersect the focused collision
cross-section.

Locked Paper-I impact-speed relation
------------------------------------
The final contact/surface impact speed is computed exactly as requested:

    v_i = sqrt(v_inf^2 + v_esc_mut^2)

with

    v_esc_mut = 9550 m/s.

The fixed 9.55 km/s value is the Titan-mass reference mutual escape-speed
normalization from Version 4. If impactor mass/radius are later varied strongly,
the physically exact mutual escape speed should be recomputed in Stage 2.

Output
------
results/manual/valid_impact_vectors.csv

Dependencies
------------
numpy
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# ------------------------------- constants ----------------------------------

G = 6.67430e-11                     # m^3 kg^-1 s^-2
M_SUN = 1.98847e30                  # kg
M_EARTH = 5.972e24                  # kg
R_EARTH = 6.371e6                   # m
AU = 1.495978707e11                 # m

# Version-4 reference mutual escape speed for Earth + Titan-mass impactor.
V_ESC_MUT = 9_550.0                 # m/s — deliberately locked by specification

# Present-day circular Earth orbital speed used as the local target velocity.
V_EARTH = math.sqrt(G * M_SUN / AU)


@dataclass(frozen=True)
class DeliveryConfig:
    """Configuration for one reproducible local Monte-Carlo run."""

    n_objects: int = 10_000
    seed: int = 4100

    # Generic outer-system source interval.
    a_min_au: float = 15.0
    a_max_au: float = 45.0
    e_sigma: float = 0.08
    inc_sigma_deg: float = 8.0

    # Reduced scattering kernel. These are Paper-I surrogate parameters, not
    # fitted outputs of a dedicated Nice-model N-body calculation.
    delta_inv_a_sigma: float = 0.20
    delta_e_sigma: float = 0.45
    delta_inc_sigma_deg: float = 12.0

    # Earth-crossing radial window.
    q_max_au: float = 1.05
    aphelion_min_au: float = 0.95

    # Hypothesized late event timing.
    target_age_ga: float = 4.10
    epoch_sigma_ga: float = 0.08
    formation_age_ga: float = 4.567

    # Local encounter-plane sampling radius. We first generate orbital
    # Earth-crossing candidates, then sample a local miss distance inside this
    # finite encounter window and retain only focused physical collisions.
    encounter_window_re: float = 5.0


def sample_population(
    cfg: DeliveryConfig,
    rng: np.random.Generator,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    """Sample initial outer-system orbital elements and random orbital phase."""
    log_a = rng.uniform(
        math.log(cfg.a_min_au),
        math.log(cfg.a_max_au),
        cfg.n_objects,
    )
    a0 = np.exp(log_a)

    e0 = np.clip(
        rng.rayleigh(cfg.e_sigma, cfg.n_objects),
        0.0,
        0.95,
    )
    i0 = np.abs(
        rng.normal(0.0, cfg.inc_sigma_deg, cfg.n_objects)
    )

    relative_phase = rng.uniform(
        0.0,
        2.0 * math.pi,
        cfg.n_objects,
    )
    return a0, e0, i0, relative_phase


def scatter_orbits(
    a0: np.ndarray,
    e0: np.ndarray,
    i0: np.ndarray,
    cfg: DeliveryConfig,
    rng: np.random.Generator,
) -> tuple[np.ndarray, ...]:
    """
    Apply a vectorized local migration/scattering surrogate.

    Inverse semimajor axis is perturbed because orbital energy is proportional
    to -1/a. Bound solutions require 1/a > 0.
    """
    inv_a0 = 1.0 / np.clip(a0, 1.0e-12, None)
    inv_a1 = inv_a0 + rng.normal(
        0.0,
        cfg.delta_inv_a_sigma,
        len(a0),
    )

    bound = np.asarray(inv_a1 > 0.0, dtype=bool)
    a1 = np.full_like(a0, np.nan)
    a1[bound] = 1.0 / inv_a1[bound]

    e1 = np.clip(
        e0 + rng.normal(0.0, cfg.delta_e_sigma, len(e0)),
        0.0,
        0.999999,
    )
    i1 = np.abs(
        i0 + rng.normal(0.0, cfg.delta_inc_sigma_deg, len(i0))
    )

    q = a1 * (1.0 - e1)
    aphelion = a1 * (1.0 + e1)
    return a1, e1, i1, q, aphelion, bound


def earth_crossing_mask(
    q_au: np.ndarray,
    aphelion_au: np.ndarray,
    bound: np.ndarray,
    cfg: DeliveryConfig,
) -> np.ndarray:
    """
    Require the osculating radial interval to straddle Earth's orbital radius.

    This is stricter than checking perihelion alone:
        q <= 1 AU <= Q
    with a small Paper-I radial tolerance.
    """
    finite = np.isfinite(q_au) & np.isfinite(aphelion_au)
    return (
        bound
        & finite
        & (q_au > 0.0)
        & (q_au <= cfg.q_max_au)
        & (aphelion_au >= cfg.aphelion_min_au)
    )


def heliocentric_speed_at_1au(a_au: np.ndarray) -> np.ndarray:
    """
    Evaluate heliocentric speed at 1 AU using vis-viva:

        v^2 = GM_sun (2/r - 1/a).
    """
    a_m = np.clip(a_au * AU, 1.0, None)
    radicand = G * M_SUN * (2.0 / AU - 1.0 / a_m)
    return np.sqrt(np.clip(radicand, 0.0, None))


def approach_speed_at_infinity(
    object_speed: np.ndarray,
    inclination_deg: np.ndarray,
    relative_phase: np.ndarray,
) -> np.ndarray:
    """
    Compute a local geocentric approach speed.

    The heliocentric velocity-vector separation is represented by an in-plane
    phase angle modulated by inclination. The expression is a direct vector
    magnitude:

        |v_obj - v_E|^2
        = v_obj^2 + v_E^2 - 2 v_obj v_E cos(psi).
    """
    inclination = np.radians(inclination_deg)
    cos_psi = np.cos(relative_phase) * np.cos(inclination)
    cos_psi = np.clip(cos_psi, -1.0, 1.0)

    rel2 = (
        object_speed**2
        + V_EARTH**2
        - 2.0 * object_speed * V_EARTH * cos_psi
    )
    return np.sqrt(np.clip(rel2, 0.0, None))


def safonov_focusing(
    v_inf: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Apply Safronov gravitational focusing with the locked 9.55-km/s speed.

    Focused collision radius:
        R_coll = R_E sqrt(1 + v_esc_mut^2 / v_inf^2)

    Focusing factor:
        F_g = 1 + v_esc_mut^2 / v_inf^2

    Final impact speed:
        v_i = sqrt(v_inf^2 + v_esc_mut^2)
    """
    safe_v_inf = np.clip(v_inf, 1.0, None)

    focusing_factor = 1.0 + (V_ESC_MUT / safe_v_inf) ** 2
    collision_radius = R_EARTH * np.sqrt(focusing_factor)

    # Explicitly execute the required impact-speed formula.
    v_i = np.sqrt(v_inf**2 + V_ESC_MUT**2)

    return focusing_factor, collision_radius, v_i


def sample_collision_cross_section(
    n: int,
    cfg: DeliveryConfig,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Sample encounter-plane miss distances with uniform area density.

    For a disk, b = b_max sqrt(U) gives uniform probability per unit area.
    Candidate encounters with b > R_coll are rejected.
    """
    b_max = cfg.encounter_window_re * R_EARTH
    return b_max * np.sqrt(rng.random(n))


def sample_contact_angle(
    collision_radius: np.ndarray,
    miss_distance: np.ndarray,
) -> np.ndarray:
    """
    Convert focused encounter-plane impact parameter to contact angle.

    With theta measured from the local surface normal:
        sin(theta) = b / R_coll.

    Values are clipped to [0,1] to prevent arcsin domain errors.
    """
    ratio = np.clip(
        miss_distance / np.clip(collision_radius, 1.0, None),
        0.0,
        1.0,
    )
    return np.degrees(np.arcsin(ratio))


def sample_impact_age(
    cfg: DeliveryConfig,
    n: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Sample a broad metastable-release epoch around the 4.1-Ga hypothesis."""
    elapsed_target = cfg.formation_age_ga - cfg.target_age_ga
    elapsed = rng.normal(
        elapsed_target,
        cfg.epoch_sigma_ga,
        n,
    )
    return cfg.formation_age_ga - elapsed


def importance_weight(
    q_au: np.ndarray,
    focusing_factor: np.ndarray,
    impact_age_ga: np.ndarray,
    cfg: DeliveryConfig,
) -> np.ndarray:
    """
    Construct a bounded relative feasibility weight.

    This is not an absolute Nice-model impact probability.
    """
    q_term = np.exp(
        -0.5 * ((q_au - 1.0) / 0.08) ** 2
    )
    epoch_term = np.exp(
        -0.5
        * ((impact_age_ga - cfg.target_age_ga) / cfg.epoch_sigma_ga) ** 2
    )

    raw = q_term * focusing_factor * epoch_term
    raw = np.nan_to_num(
        raw,
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )

    max_raw = float(np.max(raw)) if raw.size else 0.0
    if max_raw <= 0.0:
        return np.zeros_like(raw)

    return np.clip(raw / max_raw, 0.0, 1.0)


def run(
    cfg: DeliveryConfig,
    output: Path,
) -> None:
    """Execute the complete Stage-1 local Monte Carlo."""
    if cfg.n_objects <= 0:
        raise ValueError("n_objects must be > 0.")
    if cfg.encounter_window_re <= 1.0:
        raise ValueError("encounter_window_re must be > 1.")

    rng = np.random.default_rng(cfg.seed)

    a0, e0, i0, phase = sample_population(cfg, rng)
    a1, e1, i1, q, aphelion, bound = scatter_orbits(
        a0,
        e0,
        i0,
        cfg,
        rng,
    )

    orbit_intersects = earth_crossing_mask(
        q,
        aphelion,
        bound,
        cfg,
    )

    v_helio = np.zeros(cfg.n_objects, dtype=float)
    v_helio[orbit_intersects] = heliocentric_speed_at_1au(
        a1[orbit_intersects]
    )

    v_inf = np.zeros(cfg.n_objects, dtype=float)
    v_inf[orbit_intersects] = approach_speed_at_infinity(
        v_helio[orbit_intersects],
        i1[orbit_intersects],
        phase[orbit_intersects],
    )

    focusing = np.ones(cfg.n_objects, dtype=float)
    collision_radius = np.zeros(cfg.n_objects, dtype=float)
    v_impact = np.zeros(cfg.n_objects, dtype=float)

    fg, rc, vi = safonov_focusing(
        v_inf[orbit_intersects]
    )
    focusing[orbit_intersects] = fg
    collision_radius[orbit_intersects] = rc
    v_impact[orbit_intersects] = vi

    # Local encounter-plane collision filter.
    miss_distance = sample_collision_cross_section(
        cfg.n_objects,
        cfg,
        rng,
    )

    hits_cross_section = (
        orbit_intersects
        & (collision_radius > 0.0)
        & (miss_distance <= collision_radius)
        & np.isfinite(v_impact)
        & (v_impact > 0.0)
    )

    contact_angle = np.full(
        cfg.n_objects,
        np.nan,
        dtype=float,
    )
    contact_angle[hits_cross_section] = sample_contact_angle(
        collision_radius[hits_cross_section],
        miss_distance[hits_cross_section],
    )

    impact_age = sample_impact_age(
        cfg,
        cfg.n_objects,
        rng,
    )

    weights = np.zeros(cfg.n_objects, dtype=float)
    weights[hits_cross_section] = importance_weight(
        q[hits_cross_section],
        focusing[hits_cross_section],
        impact_age[hits_cross_section],
        cfg,
    )

    valid = (
        hits_cross_section
        & np.isfinite(contact_angle)
        & np.isfinite(weights)
        & (weights > 0.0)
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "object_id",
        "a_initial_AU",
        "e_initial",
        "i_initial_deg",
        "a_scattered_AU",
        "e_scattered",
        "i_scattered_deg",
        "perihelion_AU",
        "aphelion_AU",
        "v_infinity_km_s",
        "v_esc_mut_km_s",
        "impact_velocity_km_s",
        "focusing_factor",
        "collision_radius_m",
        "encounter_miss_distance_m",
        "contact_angle_deg",
        "inferred_impact_age_Ga",
        "importance_weight",
    ]

    with output.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=fieldnames,
        )
        writer.writeheader()

        for idx in np.flatnonzero(valid):
            writer.writerow({
                "object_id": int(idx),
                "a_initial_AU": a0[idx],
                "e_initial": e0[idx],
                "i_initial_deg": i0[idx],
                "a_scattered_AU": a1[idx],
                "e_scattered": e1[idx],
                "i_scattered_deg": i1[idx],
                "perihelion_AU": q[idx],
                "aphelion_AU": aphelion[idx],
                "v_infinity_km_s": v_inf[idx] / 1000.0,
                "v_esc_mut_km_s": V_ESC_MUT / 1000.0,
                "impact_velocity_km_s": v_impact[idx] / 1000.0,
                "focusing_factor": focusing[idx],
                "collision_radius_m": collision_radius[idx],
                "encounter_miss_distance_m": miss_distance[idx],
                "contact_angle_deg": contact_angle[idx],
                "inferred_impact_age_Ga": impact_age[idx],
                "importance_weight": weights[idx],
            })

    # Hard execution invariants.
    if np.any(valid):
        expected = np.sqrt(
            v_inf[valid] ** 2
            + V_ESC_MUT**2
        )
        if not np.allclose(
            v_impact[valid],
            expected,
            rtol=1.0e-13,
            atol=1.0e-9,
        ):
            raise AssertionError(
                "Safronov impact-speed invariant failed."
            )

    print("=== Stage 1 patched delivery Monte Carlo ===")
    print(f"Objects sampled          : {cfg.n_objects:,}")
    print(f"Orbital intersections    : {int(np.count_nonzero(orbit_intersects)):,}")
    print(f"Collision-cross-section  : {int(np.count_nonzero(hits_cross_section)):,}")
    print(f"Valid output vectors     : {int(np.count_nonzero(valid)):,}")
    print(f"Locked v_esc,mut         : {V_ESC_MUT/1000.0:.2f} km/s")
    print(f"Output                   : {output}")
    print(
        "NOTE: importance_weight remains a local analytical surrogate; "
        "it is not an absolute Solar-System collision probability."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )
    parser.add_argument(
        "--n",
        type=int,
        default=10_000,
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=4100,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "results/manual/valid_impact_vectors.csv"
        ),
    )
    args = parser.parse_args()

    run(
        DeliveryConfig(
            n_objects=args.n,
            seed=args.seed,
        ),
        args.output,
    )


if __name__ == "__main__":
    main()
