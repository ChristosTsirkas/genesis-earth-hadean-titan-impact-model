#!/usr/bin/env python3
"""
quench_chemistry_network.py
===========================

Stage 5 — bounded redox and prebiotic quench chemistry.

This patch replaces unconstrained continuous source terms with finite,
stoichiometrically capped reaction extents. Every reaction is limited by the
available reactants at the start of each time step, so the solver cannot create
more H2, N2, CO, CN, HCN, or FeO than permitted by the delivered feedstocks.

Tracked species
---------------
NH3, N2, H2, CO2, CO, H2O, Fe, FeO, CN, HCN, H2S, HS

Core reactions
--------------
R1: 2 NH3 -> N2 + 3 H2
R2: Fe + H2O -> FeO + H2
R3: Fe + CO2 -> FeO + CO
R4: NH3 + CO -> CN + H2O
R5: CN + H2 -> HCN + H
R6: HCN -> thermal destruction products
R7: H2S -> HS availability proxy

Limiting-reagent rule
---------------------
For Fe + H2O, stoichiometric extent is computed from

    xi_max = min(
        Fe_mass / M_Fe,
        H2O_mass / M_H2O
    )

which is the dimensionally correct implementation of a finite
min(Fe_mass, H2O_mass)-style cap. Directly taking min() of kilogram masses
without dividing by molar mass would be chemically incorrect because Fe and
H2O have different molar masses.

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

R_GAS = 8.31446261815324

G = 6.67430e-11
M_E = 5.972e24
R_E = 6.371e6
AREA_E = 4.0 * math.pi * R_E**2
G_SURF = G * M_E / R_E**2

YEAR_S = 365.25 * 86400.0

DEFAULT_QUENCH_THRESHOLD_K = 1500.0

# Molar masses [kg/mol].
MOLAR_MASS = {
    "NH3": 17.03052e-3,
    "N2": 28.0134e-3,
    "H2": 2.01588e-3,
    "CO2": 44.0095e-3,
    "CO": 28.0101e-3,
    "H2O": 18.01528e-3,
    "Fe": 55.845e-3,
    "FeO": 71.844e-3,
    "CN": 26.0174e-3,
    "HCN": 27.0253e-3,
    "H2S": 34.0809e-3,
    "HS": 33.073e-3,
}

SPECIES = tuple(
    MOLAR_MASS.keys()
)

IDX = {
    name: i
    for i, name in enumerate(SPECIES)
}


def h2_pressure_bar(h2_moles: float) -> float:
    """Return the hydrostatic-equivalent H2 surface pressure in bar."""
    h2_mass_kg = max(float(h2_moles), 0.0) * MOLAR_MASS["H2"]
    pressure_pa = h2_mass_kg * G_SURF / AREA_E
    return pressure_pa / 1.0e5


def arrhenius_probability(
    prefactor_s_inv: float,
    activation_energy_j_mol: float,
    temperature_k: float,
    dt_s: float,
) -> float:
    """
    Convert a first-order Arrhenius rate into a bounded reacted fraction.

        k = A exp(-Ea/RT)
        p = 1 - exp(-k dt)

    p is clipped to [0,1], so even very large k*dt cannot over-consume a
    reactant inventory.
    """
    temperature = float(
        np.clip(
            temperature_k,
            1.0,
            1.0e5,
        )
    )
    dt = max(
        float(dt_s),
        0.0,
    )

    exponent = float(
        np.clip(
            -activation_energy_j_mol
            / (
                R_GAS
                * temperature
            ),
            -700.0,
            0.0,
        )
    )

    rate = (
        prefactor_s_inv
        * math.exp(
            exponent
        )
    )

    probability = (
        1.0
        - math.exp(
            -min(
                rate * dt,
                700.0,
            )
        )
    )

    return float(
        np.clip(
            probability,
            0.0,
            1.0,
        )
    )


def redox_factor(
    delta_iw: float,
) -> float:
    """Bounded reducing-condition modifier relative to the IW buffer."""
    argument = float(
        np.clip(
            1.5 * delta_iw,
            -60.0,
            60.0,
        )
    )

    return float(
        np.clip(
            1.0
            / (
                1.0
                + math.exp(
                    argument
                )
            ),
            0.0,
            1.0,
        )
    )


def load_atmosphere(
    path: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Load the Stage-3/4 timeline.

    A pressure proxy is derived from the remaining N + water inventories because
    the reduced atmosphere model does not solve a full multi-species pressure
    profile.
    """
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

    if len(rows) < 2:
        raise ValueError(
            "Atmosphere timeline requires at least two rows."
        )

    time_years = np.array(
        [
            float(
                row["time_years"]
            )
            for row in rows
        ],
        dtype=float,
    )

    temperature_k = np.array(
        [
            float(
                row["temperature_K"]
            )
            for row in rows
        ],
        dtype=float,
    )

    nitrogen_kg = np.array(
        [
            float(
                row["N_kg"]
            )
            for row in rows
        ],
        dtype=float,
    )

    water_kg = np.array(
        [
            float(
                row["water_kg"]
            )
            for row in rows
        ],
        dtype=float,
    )

    time_s = (
        time_years
        * YEAR_S
    )

    pressure_pa = (
        (
            nitrogen_kg
            + water_kg
        )
        * G_SURF
        / AREA_E
    )

    if np.any(
        ~np.isfinite(
            time_s
        )
    ):
        raise FloatingPointError(
            "Non-finite atmosphere time array."
        )

    if np.any(
        np.diff(
            time_s
        )
        <= 0.0
    ):
        raise ValueError(
            "Atmosphere time grid must be strictly increasing."
        )

    return (
        time_s,
        temperature_k,
        pressure_pa,
    )


def initial_moles_from_masses(
    nh3_mass_kg: float,
    co2_mass_kg: float,
    h2o_mass_kg: float,
    fe_mass_kg: float,
    h2s_mass_kg: float,
) -> np.ndarray:
    """Create a non-negative finite initial mole vector from feedstock masses."""
    masses = {
        "NH3": nh3_mass_kg,
        "CO2": co2_mass_kg,
        "H2O": h2o_mass_kg,
        "Fe": fe_mass_kg,
        "H2S": h2s_mass_kg,
    }

    state = np.zeros(
        len(SPECIES),
        dtype=float,
    )

    for name, mass_kg in masses.items():
        mass_kg = float(
            np.clip(
                mass_kg,
                0.0,
                1.0e40,
            )
        )

        state[IDX[name]] = (
            mass_kg
            / MOLAR_MASS[name]
        )

    return state


def apply_reaction_extent(
    state: np.ndarray,
    reactants: dict[str, float],
    products: dict[str, float],
    requested_extent_mol: float,
) -> float:
    """
    Apply one reaction with strict stoichiometric limiting-reagent enforcement.

    reactants/products map species -> stoichiometric coefficient.

    The actually executed extent is

        xi = min(
            requested_extent,
            n_reactant / nu_reactant for every reactant
        ).

    Therefore, no reaction can consume more feedstock than physically exists.
    """
    if requested_extent_mol <= 0.0:
        return 0.0

    limits = [
        state[IDX[name]]
        / coefficient
        for name, coefficient in reactants.items()
        if coefficient > 0.0
    ]

    if not limits:
        return 0.0

    max_extent = max(
        0.0,
        min(
            limits
        ),
    )

    extent = float(
        np.clip(
            requested_extent_mol,
            0.0,
            max_extent,
        )
    )

    if extent <= 0.0:
        return 0.0

    for name, coefficient in reactants.items():
        state[IDX[name]] -= (
            coefficient
            * extent
        )

    for name, coefficient in products.items():
        state[IDX[name]] += (
            coefficient
            * extent
        )

    # Eliminate tiny negative roundoff without hiding a genuine violation.
    if np.any(
        state
        < -1.0e-12
    ):
        raise AssertionError(
            f"Negative species inventory after reaction: {state.tolist()}"
        )

    state[:] = np.maximum(
        state,
        0.0,
    )

    return extent


def finite_rate_step(
    state: np.ndarray,
    temperature_k: float,
    pressure_pa: float,
    dt_s: float,
    delta_iw: float,
    remaining_nh3_decomposition_extent_mol: float,
    quench_threshold_k: float = DEFAULT_QUENCH_THRESHOLD_K,
) -> tuple[float, float, float]:
    """Advance one finite-feedstock chemistry step coupled to the Stage-3 P-T path."""
    if dt_s <= 0.0:
        return 0.0, 0.0, 0.0

    temperature_k = float(np.clip(temperature_k, 1.0, 1.0e5))
    quench_threshold_k = float(np.clip(quench_threshold_k, 300.0, 5000.0))
    quench_active = temperature_k < quench_threshold_k

    redox = redox_factor(delta_iw)
    total_moles = max(float(np.sum(state)), 1.0e-30)
    mole_fraction = state / total_moles
    pressure_modifier = float(
        np.clip(pressure_pa / (pressure_pa + 1.0e7), 0.0, 1.0)
    )

    p1 = arrhenius_probability(2.0e2, 1.60e5, temperature_k, dt_s) * (
        0.30 + 0.70 * redox
    )
    requested_r1 = min(
        0.5 * state[IDX["NH3"]] * p1,
        max(remaining_nh3_decomposition_extent_mol, 0.0),
    )
    xi1 = apply_reaction_extent(
        state,
        reactants={"NH3": 2.0},
        products={"N2": 1.0, "H2": 3.0},
        requested_extent_mol=requested_r1,
    )
    h2_from_nh3 = 3.0 * xi1
    n2_from_nh3 = xi1

    fe_mass_kg = state[IDX["Fe"]] * MOLAR_MASS["Fe"]
    h2o_mass_kg = state[IDX["H2O"]] * MOLAR_MASS["H2O"]
    _finite_mass_minimum = min(fe_mass_kg, h2o_mass_kg)
    max_r2_extent = min(
        fe_mass_kg / MOLAR_MASS["Fe"],
        h2o_mass_kg / MOLAR_MASS["H2O"],
    )
    p2 = (
        arrhenius_probability(1.0e1, 7.5e4, temperature_k, dt_s)
        * redox
        * float(np.clip(mole_fraction[IDX["H2O"]], 0.0, 1.0))
    )
    xi2 = apply_reaction_extent(
        state,
        reactants={"Fe": 1.0, "H2O": 1.0},
        products={"FeO": 1.0, "H2": 1.0},
        requested_extent_mol=max_r2_extent * p2,
    )
    h2_from_fe_h2o = xi2

    p3 = (
        arrhenius_probability(5.0, 8.5e4, temperature_k, dt_s)
        * redox
        * float(np.clip(mole_fraction[IDX["CO2"]], 0.0, 1.0))
    )
    requested_r3 = min(
        float(state[IDX["Fe"]]),
        float(state[IDX["CO2"]]),
    ) * p3
    apply_reaction_extent(
        state,
        reactants={"Fe": 1.0, "CO2": 1.0},
        products={"FeO": 1.0, "CO": 1.0},
        requested_extent_mol=requested_r3,
    )

    # CN/HCN synthesis is enabled only after the imported Stage-3 trajectory
    # crosses into the explicit quench window.
    if quench_active:
        p4 = (
            arrhenius_probability(5.0e-1, 8.0e4, temperature_k, dt_s)
            * redox
            * pressure_modifier
        )
        requested_r4 = min(
            float(state[IDX["NH3"]]),
            float(state[IDX["CO"]]),
        ) * p4
        apply_reaction_extent(
            state,
            reactants={"NH3": 1.0, "CO": 1.0},
            products={"CN": 1.0, "H2O": 1.0},
            requested_extent_mol=requested_r4,
        )

        p5 = (
            arrhenius_probability(2.0, 6.5e4, temperature_k, dt_s)
            * pressure_modifier
        )
        requested_r5 = min(
            float(state[IDX["CN"]]),
            float(state[IDX["H2"]]),
        ) * p5
        apply_reaction_extent(
            state,
            reactants={"CN": 1.0, "H2": 1.0},
            products={"HCN": 1.0},
            requested_extent_mol=requested_r5,
        )

    # Any inherited HCN is thermally destroyed only while above the quench
    # threshold. Newly synthesized HCN is therefore not instantaneously
    # annihilated in the same sub-1500-K chemistry window.
    if temperature_k >= quench_threshold_k and state[IDX["HCN"]] > 0.0:
        p6 = arrhenius_probability(2.0e3, 2.1e5, temperature_k, dt_s)
        requested_r6 = state[IDX["HCN"]] * p6
        apply_reaction_extent(
            state,
            reactants={"HCN": 1.0},
            products={},
            requested_extent_mol=requested_r6,
        )

    if quench_active:
        cool_factor = float(
            np.clip(
                1.0
                / (
                    1.0
                    + math.exp(
                        float(
                            np.clip((temperature_k - 700.0) / 100.0, -60.0, 60.0)
                        )
                    )
                ),
                0.0,
                1.0,
            )
        )
        p7 = (
            arrhenius_probability(1.0e-3, 3.0e4, max(temperature_k, 300.0), dt_s)
            * cool_factor
        )
        requested_r7 = state[IDX["H2S"]] * p7
        apply_reaction_extent(
            state,
            reactants={"H2S": 1.0},
            products={"HS": 1.0},
            requested_extent_mol=requested_r7,
        )

    return h2_from_nh3, h2_from_fe_h2o, n2_from_nh3


def run(
    input_path: Path,
    output: Path,
    delta_iw: float,
    nh3_mass_kg: float,
    co2_mass_kg: float,
    h2o_mass_kg: float,
    fe_mass_kg: float,
    h2s_mass_kg: float,
    nh3_conversion_cap: float,
    quench_threshold_k: float = DEFAULT_QUENCH_THRESHOLD_K,
) -> None:
    """Execute the finite-feedstock network using the complete Stage-3 P-T trajectory."""
    time_s, temperature_k, pressure_pa = load_atmosphere(input_path)
    quench_threshold_k = float(np.clip(quench_threshold_k, 300.0, 5000.0))

    quench_mask = temperature_k < quench_threshold_k
    if not np.any(quench_mask):
        raise RuntimeError(
            "Stage-3 P-T trajectory never entered the chemistry quench window "
            f"T < {quench_threshold_k:.1f} K. Stage 5 aborted to prevent "
            "downstream thermal contamination."
        )
    first_quench_index = int(np.flatnonzero(quench_mask)[0])

    state = initial_moles_from_masses(
        nh3_mass_kg,
        co2_mass_kg,
        h2o_mass_kg,
        fe_mass_kg,
        h2s_mass_kg,
    )
    initial_state = state.copy()
    nh3_conversion_cap = float(np.clip(nh3_conversion_cap, 0.0, 1.0))
    max_r1_extent_total = 0.5 * initial_state[IDX["NH3"]] * nh3_conversion_cap
    cumulative_r1_extent = 0.0

    n_steps = len(time_s)
    history = np.empty((n_steps, len(SPECIES)), dtype=float)
    cumulative_h2_from_nh3 = np.zeros(n_steps, dtype=float)
    cumulative_h2_from_fe_h2o = np.zeros(n_steps, dtype=float)
    cumulative_n2_from_nh3 = np.zeros(n_steps, dtype=float)
    quench_active_array = np.asarray(quench_mask, dtype=np.int8)

    total_h2_nh3 = 0.0
    total_h2_fe = 0.0
    total_n2_nh3 = 0.0
    history[0] = state

    for i_raw in range(1, n_steps):
        i = int(i_raw)
        dt_s = time_s[i] - time_s[i - 1]
        if not np.isfinite(dt_s) or dt_s <= 0.0:
            raise ValueError(f"Invalid chemistry timestep at index {i}: {dt_s}")

        remaining_r1_extent = max(max_r1_extent_total - cumulative_r1_extent, 0.0)
        h2_nh3, h2_fe, n2_nh3 = finite_rate_step(
            state,
            float(temperature_k[i]),
            float(pressure_pa[i]),
            dt_s,
            delta_iw,
            remaining_r1_extent,
            quench_threshold_k,
        )

        cumulative_r1_extent += n2_nh3
        total_h2_nh3 += h2_nh3
        total_h2_fe += h2_fe
        total_n2_nh3 += n2_nh3
        cumulative_h2_from_nh3[i] = total_h2_nh3
        cumulative_h2_from_fe_h2o[i] = total_h2_fe
        cumulative_n2_from_nh3[i] = total_n2_nh3
        history[i] = state

    cumulative_h2_from_nh3[0] = 0.0
    cumulative_h2_from_fe_h2o[0] = 0.0
    cumulative_n2_from_nh3[0] = 0.0

    if np.any(~np.isfinite(history)):
        raise FloatingPointError("Non-finite chemistry inventory.")
    if np.any(history < -1.0e-12):
        raise AssertionError("Negative chemistry inventory.")

    initial_nh3_mol = float(initial_state[IDX["NH3"]])
    initial_fe_mol = float(initial_state[IDX["Fe"]])
    initial_h2o_mol = float(initial_state[IDX["H2O"]])
    max_n2_from_nh3 = initial_nh3_mol / 2.0 * nh3_conversion_cap
    max_h2_from_nh3 = 1.5 * initial_nh3_mol * nh3_conversion_cap
    max_h2_from_fe_h2o = min(initial_fe_mol, initial_h2o_mol)
    tolerance = 1.0 + 1.0e-12

    if total_n2_nh3 > max_n2_from_nh3 * tolerance:
        raise AssertionError("N2 production exceeded NH3 stoichiometric boundary.")
    if total_h2_nh3 > max_h2_from_nh3 * tolerance:
        raise AssertionError("H2 production from NH3 exceeded stoichiometric boundary.")
    if total_h2_fe > max_h2_from_fe_h2o * tolerance:
        raise AssertionError("H2 production from Fe+H2O exceeded limiting reagent.")

    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "time_s",
        "temperature_K",
        "pressure_Pa",
        "quench_active",
        *[f"{name}_mol" for name in SPECIES],
        "cumulative_H2_from_NH3_mol",
        "cumulative_H2_from_Fe_H2O_mol",
        "cumulative_N2_from_NH3_mol",
    ]

    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(fieldnames)
        for i in range(n_steps):
            writer.writerow([
                time_s[i],
                temperature_k[i],
                pressure_pa[i],
                int(quench_active_array[i]),
                *history[i],
                cumulative_h2_from_nh3[i],
                cumulative_h2_from_fe_h2o[i],
                cumulative_n2_from_nh3[i],
            ])

    final = history[-1]
    first_quench_time_years = float(time_s[first_quench_index] / YEAR_S)

    print("=== Stage 5 calibrated finite-feedstock network ===")
    print(f"Quench threshold        : {quench_threshold_k:.1f} K")
    print(f"First quench entry      : {first_quench_time_years:.3f} yr")
    print(f"Minimum input T         : {float(np.min(temperature_k)):.3f} K")
    print(f"Final H2 inventory      : {float(final[IDX['H2']]):.6e} mol")
    print(f"H2 from NH3 generated   : {total_h2_nh3:.6e} mol")
    print(f"H2 from Fe+H2O generated: {total_h2_fe:.6e} mol")
    print(f"N2 from NH3 generated   : {total_n2_nh3:.6e} mol")
    print(f"Final HCN               : {float(final[IDX['HCN']]):.6e} mol")
    print(f"Final HS availability   : {float(final[IDX['HS']]):.6e} mol-equivalent")
    print(f"H2 pressure equivalent  : {h2_pressure_bar(float(final[IDX['H2']])):.6f} bar")
    print(f"Output                  : {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("results/manual/atmosphere_timeline.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/manual/quench_network.csv"),
    )
    parser.add_argument("--delta-iw", type=float, default=-2.0)
    parser.add_argument("--nh3-mass-kg", type=float, default=3.36e21)
    parser.add_argument("--co2-mass-kg", type=float, default=4.4e18)
    parser.add_argument("--h2o-mass-kg", type=float, default=1.0e21)
    parser.add_argument("--fe-mass-kg", type=float, default=5.6e18)
    parser.add_argument("--h2s-mass-kg", type=float, default=3.4e15)
    parser.add_argument(
        "--nh3-conversion-cap",
        type=float,
        default=0.85,
        help="Maximum fraction of initial NH3 available to 2 NH3 -> N2 + 3 H2.",
    )
    parser.add_argument(
        "--quench-threshold-k",
        type=float,
        default=DEFAULT_QUENCH_THRESHOLD_K,
        help=(
            "Temperature below which CN/HCN finite-rate synthesis is enabled. "
            "Default = 1500 K."
        ),
    )

    args = parser.parse_args()
    run(
        args.input,
        args.output,
        args.delta_iw,
        args.nh3_mass_kg,
        args.co2_mass_kg,
        args.h2o_mass_kg,
        args.fe_mass_kg,
        args.h2s_mass_kg,
        args.nh3_conversion_cap,
        args.quench_threshold_k,
    )


if __name__ == "__main__":
    main()
