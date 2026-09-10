#!/usr/bin/env python3
"""Run 6: local robustness and counterfactual validation around Calibration Run 5.

This script does not recalibrate any target. It holds all non-varied Run-5
parameters fixed and performs one-at-a-time (OAT) perturbations over the eight
preserved atmosphere cases, followed by explicit ablations/counterfactuals.
Outputs are generated under results/appendix_d/d10_calibration_extensions/run6_robustness/.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
from pathlib import Path
from typing import cast

import numpy as np

import atmosphere_evolution as atm

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "appendix_d" / "d10_run6"
RAW = OUT / "raw_outputs"
INPUT_DIR = ROOT / "results" / "appendix_d" / "d7_run2" / "raw_outputs"

BASE = {
    "c_eff": atm.DEFAULT_C_EFF_J_K,
    "impactor_dh": atm.DEFAULT_IMPACTOR_DH,
    "n_photolysis_scale": atm.DEFAULT_N_PHOTOLYSIS_SCALE,
    "h2_reservoir_kg": atm.DEFAULT_H2_RESERVOIR_KG,
    "argon_shielding_factor": atm.DEFAULT_ARGON_SHIELDING_FACTOR,
}
BASE_EXPOSURE = 1.0 - BASE["argon_shielding_factor"]

# OAT sweeps. The Ar variable is expressed as *exposure* because that is the
# dynamically active complement of shielding. C_eff is one-sided because the
# Run-5 baseline is already at the declared lower validation bound.
SWEEPS = {
    "argon_exposure_factor": [BASE_EXPOSURE * f for f in (0.5, 0.8, 1.0, 1.2, 1.5)],
    "impactor_dh": [BASE["impactor_dh"] * f for f in (0.95, 0.98, 1.0, 1.02, 1.05)],
    "n_photolysis_scale": [BASE["n_photolysis_scale"] * f for f in (0.8, 0.9, 1.0, 1.1, 1.2)],
    "h2_reservoir_kg": [BASE["h2_reservoir_kg"] * f for f in (0.8, 0.9, 1.0, 1.1, 1.2)],
    "c_eff": [2.5e25, 2.75e25, 3.125e25, 3.75e25, 5.0e25],
}

COUNTERFACTUALS = {
    "no_argon_shielding": {"argon_shielding_factor": 0.0},
    "complete_argon_shielding": {"argon_shielding_factor": 1.0},
    "no_atomic_n_access": {"n_photolysis_scale": 0.0},
    "no_h2_escape_reservoir": {"h2_reservoir_kg": 0.0},
    "smow_like_impactor_water": {"impactor_dh": atm.SMOW_DH},
    "double_heat_capacity": {"c_eff": 5.0e25},
}


def summarize_output(path: Path) -> dict[str, float | None]:
    arr = np.genfromtxt(path, delimiter=",", names=True, dtype=float, encoding="utf-8")
    temp = np.atleast_1d(arr["temperature_K"])
    time = np.atleast_1d(arr["time_years"])
    dh = np.atleast_1d(arr["D_H"])
    n = np.atleast_1d(arr["N_kg"])
    ar = np.atleast_1d(arr["Ar36_kg"])
    mc = np.atleast_1d(arr["crossover_mass_amu"])
    idx = np.flatnonzero(temp < 1500.0)
    return {
        "first_T_below_1500_yr": float(time[idx[0]]) if idx.size else None,
        "final_T_K": float(temp[-1]),
        "D_H_over_SMOW": float(dh[-1] / atm.SMOW_DH),
        "final_N_kg": float(n[-1]),
        "N_residual_fraction": float(n[-1] / 2.35e21),
        "final_Ar36_kg": float(ar[-1]),
        "Ar36_retained_fraction": float(ar[-1] / 5.0e15),
        "max_crossover_amu": float(np.max(mc)),
    }


def execute_case(label: str, case: int, overrides: dict[str, float]) -> dict[str, object]:
    params = dict(BASE)
    params.update(overrides)
    out_file = RAW / label / f"atm_case_{case}.csv"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    partition = atm.load_partition(INPUT_DIR / f"atm_input_{case}.csv", 0)
    with contextlib.redirect_stdout(io.StringIO()):
        atm.run(
            partition,
            out_file,
            years=1.0e5,
            steps=1000,
            background_pressure_bar=100.0,
            effective_heat_capacity_j_k=params["c_eff"],
            impactor_ratio=params["impactor_dh"],
            n_photolysis_scale=params["n_photolysis_scale"],
            h2_reservoir_mass_kg=params["h2_reservoir_kg"],
            argon_shielding_factor=params["argon_shielding_factor"],
        )
    row: dict[str, object] = dict(summarize_output(out_file))
    row["label"] = label
    row["case"] = case
    row.update(params)
    row["argon_exposure_factor"] = 1.0 - params["argon_shielding_factor"]
    return row


def numeric_values(rows: list[dict[str, object]], key: str) -> list[float]:
    """Return a numeric result column, excluding optional missing values."""
    return [cast(float, row[key]) for row in rows if row[key] is not None]


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []

    # Explicit baseline reproduction.
    for case in range(8):
        rows.append(execute_case("baseline_run5", case, {}))

    for param, values in SWEEPS.items():
        for idx, value in enumerate(values):
            if param == "argon_exposure_factor":
                overrides = {"argon_shielding_factor": 1.0 - value}
            else:
                overrides = {param: value}
            label = f"oat_{param}_{idx:02d}"
            for case in range(8):
                rows.append(execute_case(label, case, overrides))

    for name, overrides in COUNTERFACTUALS.items():
        label = f"counterfactual_{name}"
        for case in range(8):
            rows.append(execute_case(label, case, overrides))

    fields = list(rows[0].keys())
    with (OUT / "case_results.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # Aggregate each label across the eight preserved atmosphere cases.
    aggregate = []
    labels = list(dict.fromkeys(str(r["label"]) for r in rows))
    for label in labels:
        rr = [r for r in rows if r["label"] == label]
        first = rr[0]
        cooling_times = numeric_values(rr, "first_T_below_1500_yr")
        aggregate.append({
            "label": label,
            "c_eff": first["c_eff"],
            "impactor_dh": first["impactor_dh"],
            "n_photolysis_scale": first["n_photolysis_scale"],
            "h2_reservoir_kg": first["h2_reservoir_kg"],
            "argon_shielding_factor": first["argon_shielding_factor"],
            "argon_exposure_factor": first["argon_exposure_factor"],
            "first_T_below_1500_yr_min": min(cooling_times) if cooling_times else None,
            "first_T_below_1500_yr_max": max(cooling_times) if cooling_times else None,
            "final_T_K_min": min(numeric_values(rr, "final_T_K")),
            "final_T_K_max": max(numeric_values(rr, "final_T_K")),
            "D_H_over_SMOW_min": min(numeric_values(rr, "D_H_over_SMOW")),
            "D_H_over_SMOW_max": max(numeric_values(rr, "D_H_over_SMOW")),
            "N_residual_fraction_min": min(numeric_values(rr, "N_residual_fraction")),
            "N_residual_fraction_max": max(numeric_values(rr, "N_residual_fraction")),
            "Ar36_retained_fraction_min": min(numeric_values(rr, "Ar36_retained_fraction")),
            "Ar36_retained_fraction_max": max(numeric_values(rr, "Ar36_retained_fraction")),
            "max_crossover_amu_min": min(numeric_values(rr, "max_crossover_amu")),
            "max_crossover_amu_max": max(numeric_values(rr, "max_crossover_amu")),
        })

    with (OUT / "aggregate_results.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(aggregate[0].keys()))
        w.writeheader()
        w.writerows(aggregate)

    baseline = next(a for a in aggregate if a["label"] == "baseline_run5")
    manifest = {
        "run": "Run 6 - OAT robustness and counterfactual validation",
        "purpose": "Test local parameter sensitivity without recalibration.",
        "baseline": BASE,
        "baseline_argon_exposure_factor": BASE_EXPOSURE,
        "sweeps": SWEEPS,
        "counterfactuals": COUNTERFACTUALS,
        "cases_per_setting": 8,
        "integration_years": 1.0e5,
        "integration_steps": 1000,
        "baseline_reproduction": baseline,
        "interpretive_rule": "No new empirical pass/fail tolerances are invented here; report response surfaces and explicit ablations.",
    }
    (OUT / "run_summary.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Wrote {len(rows)} case runs across {len(aggregate)} settings to {OUT}")


if __name__ == "__main__":
    main()
