#!/usr/bin/env python3
"""
impact_scaling_laws.py
======================

Stage 2 — analytical grazing-impact partitioning.

This module explicitly bypasses high-resolution 3-D SPH. It consumes valid
Stage-1 impact vectors and evaluates them with a reduced analytical scaling
framework.

Key constraints
---------------
- Only Moon-survival search geometries in theta = 60°..75° are retained.
- All high-obliquity expressions are clipped with numpy to prevent singular,
  negative, or overflow states.
- The gross water inventory X_H2O * M_i is partitioned into

    eta_vector = [
        eta_escape,
        eta_vapor_plume,
        eta_mantle_dissolution,
        eta_surface_retained,
        eta_reaccretion
    ]

- eta_surface_retained is constrained to 0.01..0.10.
- eta_vector is forced to strict mass conservation, sum(eta_vector) == 1.0
  to floating-point roundoff, with an exact final residual assignment.

Scientific limitation
---------------------
The literature does not supply one unique closed-form Stewart/Lock/Schlichting
equation for all five reservoirs in a Titan-mass grazing collision. The
ground-velocity/loss kernel is literature-motivated; the five-way partition is
an explicit analytical closure for Paper I and requires future SPH calibration.

Dependencies: numpy
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np

G = 6.67430e-11

M_E = 5.972e24
R_E = 6.371e6

M_I_REF = 1.345e23
R_I_REF = 2.575e6

X_H2O_DEFAULT = 0.50

THETA_MIN_DEG = 60.0
THETA_MAX_DEG = 75.0

EPS = np.finfo(float).eps


def radius_from_mass(
    impactor_mass_kg: float,
) -> float:
    """
    Scale impactor radius at constant Titan-reference mean density.

        R_i = R_Titan (M_i/M_Titan)^(1/3)
    """
    if not np.isfinite(impactor_mass_kg) or impactor_mass_kg <= 0.0:
        raise ValueError(
            "impactor_mass_kg must be finite and > 0."
        )

    ratio = np.clip(
        impactor_mass_kg / M_I_REF,
        1.0e-12,
        1.0e12,
    )
    return R_I_REF * ratio ** (1.0 / 3.0)


def mutual_escape_velocity(
    impactor_mass_kg: float,
    impactor_radius_m: float,
) -> float:
    """
    Exact mutual escape velocity at first contact:

        v_esc,mut =
        sqrt[2G(M_E + M_i)/(R_E + R_i)].
    """
    denominator = np.clip(
        R_E + impactor_radius_m,
        1.0,
        None,
    )
    radicand = (
        2.0
        * G
        * (M_E + impactor_mass_kg)
        / denominator
    )
    return float(
        np.sqrt(
            np.clip(
                radicand,
                0.0,
                None,
            )
        )
    )


def clipped_impact_geometry(
    theta_deg: float,
) -> tuple[float, float, float]:
    """
    Return clipped geometry variables.

    theta is measured from the local surface normal.

        b_contact = sin(theta)
        normal component     = cos(theta)
        tangential component = sin(theta)

    Clipping keeps all values finite near grazing incidence.
    """
    theta = float(
        np.clip(
            theta_deg,
            THETA_MIN_DEG,
            THETA_MAX_DEG,
        )
    )

    theta_rad = math.radians(theta)

    b_contact = float(
        np.clip(
            math.sin(theta_rad),
            0.0,
            1.0 - 1.0e-12,
        )
    )
    normal = float(
        np.clip(
            math.cos(theta_rad),
            1.0e-12,
            1.0,
        )
    )
    tangential = float(
        np.clip(
            math.sin(theta_rad),
            0.0,
            1.0,
        )
    )

    return b_contact, normal, tangential


def ground_velocity_ratio(
    phi_rad: np.ndarray,
    radius_ratio: float,
) -> np.ndarray:
    """
    Evaluate the reduced Schlichting/Yalinewich ground-velocity scaling.

    The rational polynomial is protected from small denominators and the
    logarithmic radius-ratio term is clipped before exponentiation.
    """
    safe_radius_ratio = float(
        np.clip(
            radius_ratio,
            1.0e-8,
            10.0,
        )
    )

    x = np.sin(
        np.clip(
            phi_rad,
            0.0,
            math.pi,
        )
        / 2.0
    )

    numerator = (
        14.2 * x**2
        - 25.3 * x
        + 11.3
    )
    denominator = (
        x**2
        - 2.5 * x
        + 1.9
    )

    # Preserve denominator sign while preventing division by values too close
    # to zero.
    denominator = np.where(
        np.abs(denominator) < 1.0e-10,
        np.copysign(
            1.0e-10,
            denominator,
        ),
        denominator,
    )

    rational = numerator / denominator

    ln_ratio = (
        rational
        + 2.0 * math.log(safe_radius_ratio)
    )

    return np.exp(
        np.clip(
            ln_ratio,
            -50.0,
            20.0,
        )
    )


def integrated_surface_loss_index(
    impact_velocity_m_s: float,
    impactor_radius_m: float,
    atmosphere_to_ocean_mass_ratio: float,
    n_phi: int = 2048,
) -> float:
    """
    Integrate a smooth local surface-loss kernel over the target sphere.

    Output is a bounded analytical loss index in [0,1].
    """
    if impact_velocity_m_s <= 0.0:
        raise ValueError(
            "impact_velocity_m_s must be > 0."
        )

    n_phi = int(
        np.clip(
            n_phi,
            256,
            16384,
        )
    )

    phi = np.linspace(
        0.0,
        math.pi,
        n_phi,
        dtype=float,
    )

    vg = (
        impact_velocity_m_s
        * ground_velocity_ratio(
            phi,
            impactor_radius_m / R_E,
        )
    )

    vesc_target = math.sqrt(
        2.0 * G * M_E / R_E
    )

    velocity_ratio = np.clip(
        vg / max(vesc_target, 1.0),
        0.0,
        1.0e6,
    )

    # Smooth bounded transition from negligible to strong local loss.
    logistic_argument = np.clip(
        10.0 * (velocity_ratio - 0.65),
        -60.0,
        60.0,
    )
    local_loss = (
        1.0
        / (
            1.0
            + np.exp(
                -logistic_argument
            )
        )
    )

    area_weight = np.sin(phi)

    numerator = np.trapezoid(
        local_loss * area_weight,
        phi,
    )
    denominator = np.trapezoid(
        area_weight,
        phi,
    )

    base = (
        numerator
        / max(
            float(denominator),
            1.0e-30,
        )
    )

    ratio = float(
        np.clip(
            atmosphere_to_ocean_mass_ratio,
            1.0e-8,
            1.0e8,
        )
    )

    # Reduced surface-condition modifier.
    ocean_boost = (
        1.0
        + 0.45
        / (1.0 + ratio)
    )

    return float(
        np.clip(
            base * ocean_boost,
            0.0,
            1.0,
        )
    )


def surface_retained_fraction(
    loss_index: float,
    normal_component: float,
    v_over_vesc: float,
) -> float:
    """
    Constrain eta_surface_retained to the requested 1%-10% range.

    Low loss and lower energetic severity permit the upper end of the interval;
    strong loss pushes the solution toward 1%.
    """
    severity = float(
        np.clip(
            (v_over_vesc - 1.0) / 1.5,
            0.0,
            1.0,
        )
    )

    raw = (
        0.10
        - 0.065 * loss_index
        - 0.020 * severity
        + 0.010 * normal_component
    )

    return float(
        np.clip(
            raw,
            0.01,
            0.10,
        )
    )


def partition_vector(
    impact_velocity_m_s: float,
    theta_deg: float,
    impactor_mass_kg: float,
    impactor_radius_m: float,
    atmosphere_to_ocean_mass_ratio: float,
) -> np.ndarray:
    """
    Construct a rigorously bounded five-component water partition vector.

    Mass conservation algorithm
    ---------------------------
    1. Compute surface-retained fraction and clip it to [0.01, 0.10].
    2. Build positive weights for the other four reservoirs.
    3. Normalize those four weights to exactly (1 - eta_surface).
    4. Set eta_reaccretion as the exact residual after the other four values.

    The final assertion guarantees non-negative components and a unity sum.
    """
    b_contact, normal, tangential = clipped_impact_geometry(
        theta_deg
    )

    vesc_mut = mutual_escape_velocity(
        impactor_mass_kg,
        impactor_radius_m,
    )

    v_over_vesc = float(
        np.clip(
            impact_velocity_m_s
            / max(vesc_mut, 1.0),
            0.0,
            10.0,
        )
    )

    loss_index = integrated_surface_loss_index(
        impact_velocity_m_s,
        impactor_radius_m,
        atmosphere_to_ocean_mass_ratio,
    )

    eta_surface = surface_retained_fraction(
        loss_index,
        normal,
        v_over_vesc,
    )

    remaining = float(
        np.clip(
            1.0 - eta_surface,
            0.90,
            0.99,
        )
    )

    # Positive raw weights for escape, plume, mantle, reaccretion.
    # High tangentiality boosts plume/reaccretion; normal coupling boosts mantle.
    energetic_excess = float(
        np.clip(
            v_over_vesc - 1.0,
            0.0,
            3.0,
        )
    )

    raw_other = np.array(
        [
            # escape
            0.20
            + 0.55 * loss_index
            + 0.20 * energetic_excess * tangential,

            # vapor plume
            0.20
            + 0.50 * tangential
            + 0.12 * energetic_excess,

            # mantle dissolution
            0.08
            + 0.55 * normal**2
            / (1.0 + energetic_excess),

            # reaccretion
            0.18
            + 0.35 * tangential
            * (1.0 - loss_index),
        ],
        dtype=float,
    )

    raw_other = np.nan_to_num(
        raw_other,
        nan=0.0,
        posinf=1.0e6,
        neginf=0.0,
    )

    raw_other = np.clip(
        raw_other,
        1.0e-15,
        1.0e15,
    )

    raw_sum = float(
        np.sum(raw_other)
    )

    if not np.isfinite(raw_sum) or raw_sum <= 0.0:
        raise FloatingPointError(
            "Invalid raw partition normalization."
        )

    normalized_other = (
        raw_other
        / raw_sum
        * remaining
    )

    eta_escape = float(
        np.clip(
            normalized_other[0],
            0.0,
            remaining,
        )
    )
    eta_plume = float(
        np.clip(
            normalized_other[1],
            0.0,
            remaining,
        )
    )
    eta_mantle = float(
        np.clip(
            normalized_other[2],
            0.0,
            remaining,
        )
    )

    # The final component is assigned as the exact residual. This removes any
    # accumulated normalization roundoff and guarantees strict mass closure.
    eta_reaccretion = (
        1.0
        - eta_escape
        - eta_plume
        - eta_mantle
        - eta_surface
    )

    eta_reaccretion = float(
        np.clip(
            eta_reaccretion,
            0.0,
            1.0,
        )
    )

    eta = np.array(
        [
            eta_escape,
            eta_plume,
            eta_mantle,
            eta_surface,
            eta_reaccretion,
        ],
        dtype=float,
    )

    # One final exact residual correction after clipping.
    eta[-1] = (
        1.0
        - float(
            np.sum(
                eta[:-1]
            )
        )
    )

    if np.any(~np.isfinite(eta)):
        raise FloatingPointError(
            "Non-finite eta_vector component."
        )

    if np.any(eta < -1.0e-14):
        raise AssertionError(
            f"Negative eta_vector component: {eta.tolist()}"
        )

    if not (
        0.01 - 1.0e-15
        <= float(eta[3])
        <= 0.10 + 1.0e-15
    ):
        raise AssertionError(
            f"eta_surface_retained outside 1%-10%: {float(eta[3])}"
        )

    if not math.isclose(
        float(np.sum(eta)),
        1.0,
        rel_tol=0.0,
        abs_tol=2.0e-15,
    ):
        raise AssertionError(
            f"Mass conservation failed: sum={np.sum(eta)!r}"
        )

    return eta


def process(
    input_csv: Path,
    output_csv: Path,
    impactor_mass_kg: float,
    water_fraction: float,
    atmosphere_to_ocean_mass_ratio: float,
) -> None:
    """Process Stage-1 vectors and emit only the 60°-75° grazing family."""
    water_fraction = float(
        np.clip(
            water_fraction,
            0.0,
            1.0,
        )
    )

    if not input_csv.exists():
        raise FileNotFoundError(
            input_csv
        )

    with input_csv.open(
        "r",
        encoding="utf-8",
    ) as fh:
        rows = list(
            csv.DictReader(fh)
        )

    impactor_radius_m = radius_from_mass(
        impactor_mass_kg
    )

    vesc_mut = mutual_escape_velocity(
        impactor_mass_kg,
        impactor_radius_m,
    )

    gross_water_kg = (
        water_fraction
        * impactor_mass_kg
    )

    output_rows: list[dict] = []

    for row in rows:
        try:
            theta_deg = float(
                row["contact_angle_deg"]
            )
            impact_velocity_km_s = float(
                row["impact_velocity_km_s"]
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            continue

        if not np.isfinite(theta_deg):
            continue

        # Enforce strict Moon-survival search window.
        if not (
            THETA_MIN_DEG
            <= theta_deg
            <= THETA_MAX_DEG
        ):
            continue

        impact_velocity_m_s = float(
            np.clip(
                impact_velocity_km_s
                * 1000.0,
                1.0,
                1.0e6,
            )
        )

        eta = partition_vector(
            impact_velocity_m_s,
            theta_deg,
            impactor_mass_kg,
            impactor_radius_m,
            atmosphere_to_ocean_mass_ratio,
        )

        partition_masses = (
            gross_water_kg
            * eta
        )

        # Strict mass-conservation check in kilograms.
        if not math.isclose(
            float(
                np.sum(
                    partition_masses
                )
            ),
            gross_water_kg,
            rel_tol=1.0e-14,
            abs_tol=max(
                1.0,
                gross_water_kg
                * 1.0e-14,
            ),
        ):
            raise AssertionError(
                "Water partition mass conservation failed."
            )

        b_contact, _, _ = clipped_impact_geometry(
            theta_deg
        )

        output_rows.append({
            **row,
            "impactor_mass_kg": impactor_mass_kg,
            "impactor_radius_m": impactor_radius_m,
            "mutual_escape_km_s": vesc_mut / 1000.0,
            "v_over_vesc": impact_velocity_m_s / vesc_mut,
            "b_contact": b_contact,
            "x_H2O": water_fraction,
            "eta_escape": eta[0],
            "eta_vapor_plume": eta[1],
            "eta_mantle_dissolution": eta[2],
            "eta_surface_retained": eta[3],
            "eta_reaccretion": eta[4],
            "water_escape_kg": partition_masses[0],
            "water_vapor_plume_kg": partition_masses[1],
            "water_mantle_kg": partition_masses[2],
            "water_surface_kg": partition_masses[3],
            "water_reaccretion_kg": partition_masses[4],
        })

    output_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if output_rows:
        fieldnames = list(
            output_rows[0].keys()
        )
        with output_csv.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=fieldnames,
            )
            writer.writeheader()
            writer.writerows(
                output_rows
            )
    else:
        # Still emit a valid empty CSV header so downstream scripts fail
        # cleanly and predictably instead of reading malformed text.
        minimal_header = [
            "contact_angle_deg",
            "impact_velocity_km_s",
            "eta_escape",
            "eta_vapor_plume",
            "eta_mantle_dissolution",
            "eta_surface_retained",
            "eta_reaccretion",
            "water_surface_kg",
            "water_vapor_plume_kg",
        ]
        with output_csv.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as fh:
            csv.writer(fh).writerow(
                minimal_header
            )

    print("=== Stage 2 patched analytical scaling engine ===")
    print(f"Input Stage-1 rows      : {len(rows):,}")
    print(f"Accepted 60-75 deg rows : {len(output_rows):,}")
    print(f"Impactor mass           : {impactor_mass_kg:.6e} kg")
    print(f"Gross water fraction    : {water_fraction:.3f}")
    print(f"Output                  : {output_csv}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "results/manual/valid_impact_vectors.csv"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "results/manual/impact_partitions.csv"
        ),
    )
    parser.add_argument(
        "--impactor-mass",
        type=float,
        default=M_I_REF,
    )
    parser.add_argument(
        "--water-fraction",
        type=float,
        default=X_H2O_DEFAULT,
    )
    parser.add_argument(
        "--atm-ocean-ratio",
        type=float,
        default=0.05,
    )

    args = parser.parse_args()

    process(
        args.input,
        args.output,
        args.impactor_mass,
        args.water_fraction,
        args.atm_ocean_ratio,
    )


if __name__ == "__main__":
    main()
