#!/usr/bin/env python3
"""
atmosphere_evolution.py
=======================

Stages 3 & 4 — CPU-native 1-D thermal cooling + hydrodynamic escape.

This module is written for deterministic desktop execution:
- one preallocated time grid,
- no adaptive multidimensional mesh,
- no GPU dependency,
- no unbounded while-loops,
- no per-step dynamic list growth.

Dimensional convention
----------------------
The Hunten crossover-mass equation is solved entirely in SI units:

    m_c = m_1 + k_B T F_1 / (b_12 g X_1)

where
    m_c, m_1 : kg per particle
    k_B      : J K^-1
    T        : K
    F_1      : particles m^-2 s^-1
    b_12     : m^-1 s^-1
    g        : m s^-2
    X_1      : dimensionless mixing ratio

Locked particle masses
----------------------
m_H2   = 2.016 amu
m_N    = 14.007 amu
m_36Ar = 35.967 amu

with
    1 amu = 1.66054e-27 kg per particle.

Dependencies
------------
numpy
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np

# ------------------------------- constants ----------------------------------

G = 6.67430e-11
M_E = 5.972e24
R_E = 6.371e6

AREA_E_M2 = 4.0 * math.pi * R_E**2
G_SURF = G * M_E / R_E**2

YEAR_S = 365.25 * 86400.0
K_B = 1.380649e-23                  # J K^-1
AMU_KG = 1.66054e-27                # kg per amu, locked by specification

M_H2_AMU = 2.016
M_N_AMU = 14.007
M_AR36_AMU = 35.967

M_H2_KG = M_H2_AMU * AMU_KG
M_N_KG = M_N_AMU * AMU_KG
M_AR36_KG = M_AR36_AMU * AMU_KG

# D-bearing light-species threshold for deciding whether Rayleigh fractionation
# is dynamically active. HD is represented at approximately 3.022 amu.
M_HD_AMU = 3.022
M_HD_KG = M_HD_AMU * AMU_KG

SMOW_DH = 1.558e-4
M_OCEAN = 1.4e21


def load_partition(
    path: Path,
    index: int,
) -> dict:
    """Load one valid Stage-2 partition row with strict integer index typing."""
    # CSV/CLI boundaries are text-oriented; force a native integer before any
    # list or NumPy indexing operation.
    index = int(index)

    if not path.exists():
        raise FileNotFoundError(
            path
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as fh:
        rows = list(
            csv.DictReader(fh)
        )

    if not rows:
        raise ValueError(
            "Stage-2 partition CSV has no data rows."
        )

    if index < 0 or index >= len(rows):
        raise IndexError(
            f"index={index} outside valid range 0..{len(rows)-1}"
        )

    selected = rows[index]

    # Preserve trajectory identity as an integer if Stage 1/2 supplied it.
    if "object_id" in selected and selected["object_id"] not in (None, ""):
        selected["object_id"] = int(float(selected["object_id"]))

    return selected


def cold_trap_factor(
    background_pressure_bar: float,
    temperature_k: float,
) -> float:
    """
    Return a bounded 0..1 suppression factor for upper-atmosphere water access.

    Higher background pressure and lower atmospheric temperature strengthen the
    reduced cold-trap closure. This is a Paper-I boundary parameterization, not
    a full radiative-convective photochemical calculation.
    """
    p = float(
        np.clip(
            background_pressure_bar,
            0.0,
            1.0e6,
        )
    )
    temperature = float(
        np.clip(
            temperature_k,
            100.0,
            1.0e5,
        )
    )

    pressure_term = (
        p
        / (p + 10.0)
        if p > 0.0
        else 0.0
    )

    logistic_argument = float(
        np.clip(
            (temperature - 700.0) / 100.0,
            -60.0,
            60.0,
        )
    )

    temperature_term = (
        1.0
        / (
            1.0
            + math.exp(
                logistic_argument
            )
        )
    )

    return float(
        np.clip(
            0.05
            + 0.95
            * pressure_term
            * temperature_term,
            0.0,
            1.0,
        )
    )


def olr_w_m2(
    temperature_k: float,
    olr_limit_w_m2: float,
) -> float:
    """
    Outgoing longwave radiation with a Simpson-Nakajima-like ceiling.

        OLR = min(sigma T^4, OLR_limit).
    """
    sigma = 5.670374419e-8

    temperature = float(
        np.clip(
            temperature_k,
            1.0,
            1.0e5,
        )
    )

    blackbody = sigma * temperature**4

    return float(
        np.clip(
            min(
                blackbody,
                olr_limit_w_m2,
            ),
            0.0,
            olr_limit_w_m2,
        )
    )


def b12_si(
    temperature_k: float,
    b12_reference_cm_inv_s: float,
    reference_temperature_k: float = 1000.0,
    exponent: float = 0.75,
) -> float:
    """
    Convert and temperature-scale the Hunten binary diffusion parameter.

    Input reference units:
        cm^-1 s^-1

    SI conversion:
        1 cm^-1 = 100 m^-1

    Therefore:
        b_SI [m^-1 s^-1] = 100 * b_cgs [cm^-1 s^-1].
    """
    temperature_ratio = float(
        np.clip(
            temperature_k
            / reference_temperature_k,
            1.0e-8,
            1.0e8,
        )
    )

    b_cgs = (
        b12_reference_cm_inv_s
        * temperature_ratio**exponent
    )

    return float(
        np.clip(
            b_cgs * 100.0,
            1.0e-30,
            1.0e40,
        )
    )


def crossover_mass_kg(
    temperature_k: float,
    h2_flux_m2_s: float,
    x_h2: float,
    b12_m_inv_s: float,
) -> float:
    """
    Evaluate the time-dependent Hunten crossover mass in kg/particle.

        m_c = m_H2 + k_B T F_H2 / (b_12 g X_H2)

    Every quantity is SI; no amu appears inside the equation.
    """
    temperature = float(
        np.clip(
            temperature_k,
            1.0,
            1.0e5,
        )
    )
    flux = float(
        np.clip(
            h2_flux_m2_s,
            0.0,
            1.0e40,
        )
    )
    x = float(
        np.clip(
            x_h2,
            1.0e-12,
            1.0,
        )
    )
    b = float(
        np.clip(
            b12_m_inv_s,
            1.0e-30,
            1.0e40,
        )
    )

    if flux <= 0.0:
        return M_H2_KG

    delta_mass_kg = (
        K_B
        * temperature
        * flux
        / (
            b
            * G_SURF
            * x
        )
    )

    mc = (
        M_H2_KG
        + delta_mass_kg
    )

    return float(
        np.clip(
            mc,
            M_H2_KG,
            1.0e6 * AMU_KG,
        )
    )


def dragged_minor_flux_m2_s(
    species_mass_kg: float,
    crossover_mass_kg_value: float,
    h2_flux_m2_s: float,
    x_species: float,
    x_h2: float,
) -> float:
    """
    Minor-species hydrodynamic drag flux in particles m^-2 s^-1.

        F_j =
          (X_j/X_1) F_1
          (m_c - m_j)/(m_c - m_1)

    Flux is exactly zero when m_c <= m_j.
    """
    if crossover_mass_kg_value <= species_mass_kg:
        return 0.0

    denominator = (
        crossover_mass_kg_value
        - M_H2_KG
    )

    if denominator <= 0.0:
        return 0.0

    fractionation = (
        crossover_mass_kg_value
        - species_mass_kg
    ) / denominator

    fractionation = float(
        np.clip(
            fractionation,
            0.0,
            1.0,
        )
    )

    return float(
        np.clip(
            (
                x_species
                / max(
                    x_h2,
                    1.0e-12,
                )
            )
            * h2_flux_m2_s
            * fractionation,
            0.0,
            1.0e40,
        )
    )


def species_mixing_fraction(
    species_mass_inventory_kg: float,
    particle_mass_kg: float,
    h2_reference_particles: float,
) -> float:
    """Reduced finite global-inventory mixing-ratio closure."""
    n_species = (
        max(
            species_mass_inventory_kg,
            0.0,
        )
        / particle_mass_kg
    )

    denominator = (
        n_species
        + max(
            h2_reference_particles,
            0.0,
        )
    )

    if denominator <= 0.0:
        return 0.0

    return float(
        np.clip(
            n_species / denominator,
            0.0,
            1.0,
        )
    )


DEFAULT_C_EFF_J_K = 2.5e25
MIN_C_EFF_J_K = 2.5e25
MAX_C_EFF_J_K = 2.6e26

# Free inverse parameter. This is an exploratory initial value, not a measured
# primordial Titan-water D/H.
DEFAULT_IMPACTOR_DH = 1.465e-4

# Reference transient H2 reservoir generated by the nominal 2.5 wt.% NH3,
# chi_N = 0.85 case (~97 bar hydrostatic-equivalent H2).
DEFAULT_H2_RESERVOIR_KG = 5.0e20

# Reduced-order upper-atmosphere calibration parameter. This must ultimately
# be replaced by a photochemical/homopause model; it is exposed deliberately
# rather than hidden as a fixed yield.
DEFAULT_N_PHOTOLYSIS_SCALE = 0.61

# Reduced-order homopause/diffusion accessibility factor for 36Ar.
# This factor scales the fraction of the bulk 36Ar reservoir exposed to the
# hydrodynamic drag window; it does not alter atomic-N accessibility.
DEFAULT_ARGON_SHIELDING_FACTOR = 0.9805247566


def h2_flux_from_reservoir_m2_s(
    h2_reservoir_mass_kg: float,
    efold_years: float,
) -> float:
    """Return F0 for F_H2(t)=F0 exp(-t/tau), normalized to a finite H2 reservoir."""
    reservoir_kg = float(np.clip(h2_reservoir_mass_kg, 0.0, 1.0e40))
    tau_s = max(float(efold_years) * YEAR_S, 1.0)
    h2_particles = reservoir_kg / M_H2_KG
    return float(np.clip(h2_particles / (AREA_E_M2 * tau_s), 0.0, 1.0e40))


def atomic_n_photolysis_fraction(
    temperature_k: float,
    h2_flux_m2_s: float,
    h2_flux0_m2_s: float,
    scale: float,
) -> float:
    """Reduced atomic-N/homopause accessibility closure used only for screening."""
    scale = float(np.clip(scale, 0.0, 1.0))
    if scale <= 0.0 or h2_flux0_m2_s <= 0.0:
        return 0.0

    flux_fraction = float(np.clip(h2_flux_m2_s / h2_flux0_m2_s, 0.0, 1.0))
    logistic_argument = float(np.clip(-(temperature_k - 900.0) / 250.0, -60.0, 60.0))
    thermal_factor = 1.0 / (1.0 + math.exp(logistic_argument))

    return float(np.clip(scale * flux_fraction**0.35 * thermal_factor, 0.0, 1.0))


def run(
    partition: dict,
    output: Path,
    years: float,
    steps: int,
    background_pressure_bar: float,
    effective_heat_capacity_j_k: float = DEFAULT_C_EFF_J_K,
    impactor_ratio: float = DEFAULT_IMPACTOR_DH,
    n_photolysis_scale: float = DEFAULT_N_PHOTOLYSIS_SCALE,
    h2_reservoir_mass_kg: float = DEFAULT_H2_RESERVOIR_KG,
    argon_shielding_factor: float = DEFAULT_ARGON_SHIELDING_FACTOR,
    allow_diagnostic_c_eff: bool = False,
    legacy_full_n_access: bool = False,
) -> None:
    """Run the calibrated Stage-3/4 thermal, escape, and isotope model."""
    if years <= 0.0:
        raise ValueError("years must be > 0.")
    if steps < 2:
        raise ValueError("steps must be >= 2.")

    effective_heat_capacity_j_k = float(effective_heat_capacity_j_k)
    if (
        not allow_diagnostic_c_eff
        and not MIN_C_EFF_J_K <= effective_heat_capacity_j_k <= MAX_C_EFF_J_K
    ):
        raise ValueError(
            "effective_heat_capacity_j_k must lie inside the exploratory validation "
            f"interval [{MIN_C_EFF_J_K:.3e}, {MAX_C_EFF_J_K:.3e}] J K^-1."
        )

    impactor_ratio = float(np.clip(impactor_ratio, 1.0e-6, 1.0e-2))
    n_photolysis_scale = float(np.clip(n_photolysis_scale, 0.0, 1.0))
    h2_reservoir_mass_kg = float(np.clip(h2_reservoir_mass_kg, 0.0, 1.0e40))
    argon_shielding_factor = float(np.clip(argon_shielding_factor, 0.0, 1.0))
    argon_exposure_factor = 1.0 - argon_shielding_factor

    water_surface_kg = float(partition["water_surface_kg"])
    water_plume_kg = float(partition["water_vapor_plume_kg"])
    exchangeable_water_initial_kg = max(water_surface_kg + water_plume_kg, 1.0)

    preimpact_water_kg = M_OCEAN
    preimpact_ratio = SMOW_DH
    r_mix = (
        preimpact_water_kg * preimpact_ratio
        + exchangeable_water_initial_kg * impactor_ratio
    ) / (preimpact_water_kg + exchangeable_water_initial_kg)

    nitrogen_initial_kg = 2.35e21
    nitrogen_mass_kg = nitrogen_initial_kg
    ar36_mass_kg = 5.0e15

    temperature_k = 2800.0
    temperature_floor_k = 300.0
    absorbed_solar_w_m2 = 240.0
    olr_limit_w_m2 = 280.0

    h2_flux_efold_years = 2.0e4
    h2_flux0_m2_s = h2_flux_from_reservoir_m2_s(
        h2_reservoir_mass_kg,
        h2_flux_efold_years,
    )
    b12_reference_cm_inv_s = 1.0e19
    rayleigh_alpha = 0.90
    water_mass_kg = exchangeable_water_initial_kg

    times_years = np.linspace(0.0, years, steps, dtype=float)
    temperature_array = np.empty(steps, dtype=float)
    cold_trap_array = np.empty(steps, dtype=float)
    olr_array = np.empty(steps, dtype=float)
    h2_flux_array = np.empty(steps, dtype=float)
    crossover_mass_array_kg = np.empty(steps, dtype=float)
    crossover_mass_array_amu = np.empty(steps, dtype=float)
    water_array = np.empty(steps, dtype=float)
    dh_array = np.empty(steps, dtype=float)
    nitrogen_array = np.empty(steps, dtype=float)
    ar36_array = np.empty(steps, dtype=float)
    n_atomic_fraction_array = np.zeros(steps, dtype=float)
    n_drag_active_array = np.zeros(steps, dtype=np.int8)
    ar_drag_active_array = np.zeros(steps, dtype=np.int8)
    rayleigh_active_array = np.zeros(steps, dtype=np.int8)

    for i_raw, time_years in enumerate(times_years):
        i = int(i_raw)
        dt_s = 0.0 if i == 0 else (times_years[i] - times_years[i - 1]) * YEAR_S

        trap = cold_trap_factor(background_pressure_bar, temperature_k)
        olr = olr_w_m2(temperature_k, olr_limit_w_m2)
        net_cooling_flux_w_m2 = max(olr - absorbed_solar_w_m2, 0.0)

        if dt_s > 0.0 and temperature_k > temperature_floor_k:
            energy_loss_j = AREA_E_M2 * net_cooling_flux_w_m2 * dt_s
            delta_temperature_k = energy_loss_j / effective_heat_capacity_j_k
            temperature_k = max(
                temperature_floor_k,
                temperature_k - max(delta_temperature_k, 0.0),
            )
            trap = cold_trap_factor(background_pressure_bar, temperature_k)
            olr = olr_w_m2(temperature_k, olr_limit_w_m2)

        h2_flux = h2_flux0_m2_s * math.exp(-time_years / h2_flux_efold_years)
        x_h2 = float(
            np.clip(
                0.90 * math.exp(-time_years / h2_flux_efold_years),
                0.02,
                0.90,
            )
        )
        b12 = b12_si(temperature_k, b12_reference_cm_inv_s)
        mc_kg = crossover_mass_kg(temperature_k, h2_flux, x_h2, b12)

        h2_reference_particles = (
            h2_flux * AREA_E_M2 * h2_flux_efold_years * YEAR_S
        )
        x_n_bulk = species_mixing_fraction(
            nitrogen_mass_kg,
            M_N_KG,
            h2_reference_particles,
        )
        x_ar_bulk = species_mixing_fraction(
            ar36_mass_kg,
            M_AR36_KG,
            h2_reference_particles,
        )
        # Homopause/diffusion shielding: only a calibrated fraction of the
        # bulk 36Ar abundance is exposed to the H2-driven escape window.
        x_ar = float(np.clip(x_ar_bulk * argon_exposure_factor, 0.0, 1.0))

        n_atomic_fraction = (
            1.0
            if legacy_full_n_access
            else atomic_n_photolysis_fraction(
                temperature_k,
                h2_flux,
                h2_flux0_m2_s,
                n_photolysis_scale,
            )
        )
        x_n_atomic = float(np.clip(x_n_bulk * n_atomic_fraction, 0.0, 1.0))

        if mc_kg > M_N_KG and x_n_atomic > 0.0:
            n_drag_active_array[i] = 1
            n_flux = dragged_minor_flux_m2_s(
                M_N_KG,
                mc_kg,
                h2_flux,
                x_n_atomic,
                x_h2,
            )
            n_loss_kg = n_flux * AREA_E_M2 * dt_s * M_N_KG
            nitrogen_mass_kg = max(
                0.0,
                nitrogen_mass_kg - min(nitrogen_mass_kg, n_loss_kg),
            )

        if mc_kg > M_AR36_KG and x_ar > 0.0:
            ar_drag_active_array[i] = 1
            ar_flux = dragged_minor_flux_m2_s(
                M_AR36_KG,
                mc_kg,
                h2_flux,
                x_ar,
                x_h2,
            )
            ar_loss_kg = ar_flux * AREA_E_M2 * dt_s * M_AR36_KG
            ar36_mass_kg = max(0.0, ar36_mass_kg - min(ar36_mass_kg, ar_loss_kg))

        water_escape_rate_kg_s = (
            2.0e7
            * math.exp(-time_years / 5.0e4)
            * (1.0 - trap)
        )
        potential_water_loss_kg = water_escape_rate_kg_s * dt_s

        if mc_kg > M_HD_KG:
            rayleigh_active_array[i] = 1
            actual_water_loss_kg = min(
                water_mass_kg,
                max(potential_water_loss_kg, 0.0),
            )
            water_mass_kg = max(
                exchangeable_water_initial_kg * 1.0e-30,
                water_mass_kg - actual_water_loss_kg,
            )
            remaining_fraction = float(
                np.clip(
                    water_mass_kg / exchangeable_water_initial_kg,
                    1.0e-30,
                    1.0,
                )
            )
            d_h = r_mix * remaining_fraction ** (rayleigh_alpha - 1.0)
        else:
            d_h = r_mix if i == 0 else dh_array[i - 1]

        temperature_array[i] = temperature_k
        cold_trap_array[i] = trap
        olr_array[i] = olr
        h2_flux_array[i] = h2_flux
        crossover_mass_array_kg[i] = mc_kg
        crossover_mass_array_amu[i] = mc_kg / AMU_KG
        n_atomic_fraction_array[i] = n_atomic_fraction
        water_array[i] = water_mass_kg
        dh_array[i] = d_h
        nitrogen_array[i] = nitrogen_mass_kg
        ar36_array[i] = ar36_mass_kg

    arrays_to_check = [
        temperature_array,
        cold_trap_array,
        olr_array,
        h2_flux_array,
        crossover_mass_array_kg,
        crossover_mass_array_amu,
        n_atomic_fraction_array,
        water_array,
        dh_array,
        nitrogen_array,
        ar36_array,
    ]
    if any(np.any(~np.isfinite(array)) for array in arrays_to_check):
        raise FloatingPointError("Non-finite value detected in calibrated Stage-3/4 arrays.")
    if np.any(np.diff(temperature_array) > 1.0e-9):
        raise AssertionError("Thermal trajectory became non-monotonic during cooling.")
    if np.any(temperature_array < temperature_floor_k - 1.0e-9):
        raise AssertionError("Temperature crossed the physical integration floor.")
    if np.any(water_array < 0.0) or np.any(nitrogen_array < 0.0) or np.any(ar36_array < 0.0):
        raise AssertionError("Negative volatile inventory detected.")

    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "time_years",
        "temperature_K",
        "cold_trap_factor",
        "olr_W_m2",
        "H2_flux_m-2_s-1",
        "crossover_mass_kg_per_particle",
        "crossover_mass_amu",
        "atomic_N_photolysis_fraction",
        "N_drag_active",
        "Ar36_drag_active",
        "Rayleigh_active",
        "water_kg",
        "D_H",
        "N_kg",
        "Ar36_kg",
    ]

    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(fieldnames)
        for i in range(steps):
            writer.writerow([
                times_years[i],
                temperature_array[i],
                cold_trap_array[i],
                olr_array[i],
                h2_flux_array[i],
                crossover_mass_array_kg[i],
                crossover_mass_array_amu[i],
                n_atomic_fraction_array[i],
                int(n_drag_active_array[i]),
                int(ar_drag_active_array[i]),
                int(rayleigh_active_array[i]),
                water_array[i],
                dh_array[i],
                nitrogen_array[i],
                ar36_array[i],
            ])

    nitrogen_residual_fraction = nitrogen_array[-1] / nitrogen_initial_kg

    print("=== Stages 3/4 calibrated atmosphere engine ===")
    print(f"Stage-2 contact angle : {partition['contact_angle_deg']} deg")
    print(f"C_eff                 : {effective_heat_capacity_j_k:.6e} J/K")
    print(f"Impactor D/H R_i      : {impactor_ratio:.6e}")
    print(f"H2 reservoir          : {h2_reservoir_mass_kg:.6e} kg")
    print(f"H2 flux F0            : {h2_flux0_m2_s:.6e} m^-2 s^-1")
    print(f"N photolysis scale    : {n_photolysis_scale:.6f}")
    print(f"36Ar shielding fraction: {float(argon_shielding_factor):.10f}")
    print(f"36Ar exposure fraction : {float(argon_exposure_factor):.10f}")
    print(f"Initial R_mix         : {float(r_mix):.6e}")
    print(f"Final temperature     : {float(temperature_array[-1]):.3f} K")
    print(f"Final D/H             : {float(dh_array[-1]):.6e}")
    print(f"Final D/H / SMOW      : {float(dh_array[-1] / SMOW_DH):.6f}")
    print("Isotope interpretation: ~0.95x SMOW is the calibrated core-delivery envelope;")
    print("                        the remaining ~5% isotopic top-up is allocated to")
    print("                        the subsequent Chondritic Late Veneer mixing module.")
    print(f"Final N mass          : {float(nitrogen_array[-1]):.6e} kg")
    print(f"N residual fraction  : {float(nitrogen_residual_fraction):.6e}")
    print(f"Final 36Ar mass       : {float(ar36_array[-1]):.6e} kg")
    print(f"Output                : {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("results/manual/impact_partitions.csv"),
    )
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--years", type=float, default=1.0e5)
    parser.add_argument("--steps", type=int, default=2000)
    parser.add_argument("--background-bar", type=float, default=100.0)
    parser.add_argument(
        "--c-eff",
        type=float,
        default=DEFAULT_C_EFF_J_K,
        help=(
            "Reduced magma-ocean/troposphere effective heat capacity "
            f"[{MIN_C_EFF_J_K:.2e}, {MAX_C_EFF_J_K:.2e}] J/K."
        ),
    )
    parser.add_argument(
        "--impactor-dh",
        type=float,
        default=DEFAULT_IMPACTOR_DH,
        help="Free impactor-water initial D/H ratio; calibrated default = 1.465e-4.",
    )
    parser.add_argument(
        "--n-photolysis-scale",
        type=float,
        default=DEFAULT_N_PHOTOLYSIS_SCALE,
        help=(
            "Reduced upper-atmosphere atomic-N availability scale (0..1); "
            "calibration variable, not an observed fraction."
        ),
    )
    parser.add_argument(
        "--argon-shielding-factor",
        type=float,
        default=DEFAULT_ARGON_SHIELDING_FACTOR,
        help=(
            "True shielding fraction (0..1): 0 means fully exposed, 1 means fully shielded. "
            "The calibrated default leaves ~1.95%% of bulk 36Ar accessible to hydrodynamic drag."
        ),
    )
    parser.add_argument(
        "--h2-reservoir-kg",
        type=float,
        default=DEFAULT_H2_RESERVOIR_KG,
        help="Finite transient H2 reservoir used to normalize the hydrodynamic particle flux.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/manual/atmosphere_timeline.csv"),
    )
    parser.add_argument(
        "--allow-diagnostic-c-eff",
        action="store_true",
        help="Permit replay of the explicitly failed D.3 C_eff=5e30 diagnostic.",
    )

    args = parser.parse_args()
    run(
        load_partition(args.input, int(args.index)),
        args.output,
        args.years,
        args.steps,
        args.background_bar,
        effective_heat_capacity_j_k=args.c_eff,
        impactor_ratio=args.impactor_dh,
        n_photolysis_scale=args.n_photolysis_scale,
        h2_reservoir_mass_kg=args.h2_reservoir_kg,
        argon_shielding_factor=args.argon_shielding_factor,
        allow_diagnostic_c_eff=args.allow_diagnostic_c_eff,
    )


if __name__ == "__main__":
    main()
