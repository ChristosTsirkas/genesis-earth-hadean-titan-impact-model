#!/usr/bin/env python3
"""Run 6b: propagate thermal robustness cases through the Stage-5 chemistry grid.

Uses atmosphere case 0 for each C_eff setting, matching the existing Run-5
practice of applying the full 4x4 chemistry grid to a representative Titan-mass
cooling trajectory. No chemistry parameter is recalibrated.
"""
from __future__ import annotations

import contextlib
import csv
import io
from pathlib import Path

import numpy as np

import quench_chemistry_network as chem

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "results" / "appendix_d" / "d10_run6"
RAW_ATM = BASE / "raw_outputs"
OUT = BASE / "chemistry_propagation"
RAW_CHEM = OUT / "raw_outputs"

THERMAL_LABELS = [
    "oat_c_eff_00",
    "oat_c_eff_01",
    "oat_c_eff_02",
    "oat_c_eff_03",
    "oat_c_eff_04",
]
X_NH3 = [0.005, 0.010, 0.025, 0.050]
DELTA_IW = [-3, -2, -1, 0]
M_IMPACTOR_KG = 1.345e23


def final_metrics(path: Path) -> dict[str, float]:
    a = np.genfromtxt(path, delimiter=",", names=True, dtype=float, encoding="utf-8")
    temp = np.atleast_1d(a["temperature_K"])
    time_s = np.atleast_1d(a["time_s"])
    hcn = np.atleast_1d(a["HCN_mol"])
    h2 = np.atleast_1d(a["H2_mol"])
    idx = np.flatnonzero(temp < 1500.0)
    return {
        "first_quench_year": float(time_s[idx[0]] / chem.YEAR_S),
        "HCN_final_mol": float(hcn[-1]),
        "H2_final_mol": float(h2[-1]),
        "H2_pressure_bar": float(chem.h2_pressure_bar(h2[-1])),
    }


def main() -> None:
    RAW_CHEM.mkdir(parents=True, exist_ok=True)
    rows = []
    failures = []
    for thermal_label in THERMAL_LABELS:
        atmosphere = RAW_ATM / thermal_label / "atm_case_0.csv"
        for x in X_NH3:
            for iw in DELTA_IW:
                output = RAW_CHEM / thermal_label / f"chem_x{x:.3f}_iw{iw:+d}.csv"
                output.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        chem.run(
                            atmosphere,
                            output,
                            delta_iw=float(iw),
                            nh3_mass_kg=x * M_IMPACTOR_KG,
                            co2_mass_kg=4.4e18,
                            h2o_mass_kg=1.0e21,
                            fe_mass_kg=5.6e18,
                            h2s_mass_kg=3.4e15,
                            nh3_conversion_cap=0.85,
                            quench_threshold_k=1500.0,
                        )
                    m = final_metrics(output)
                    rows.append({"thermal_label": thermal_label, "x_NH3": x, "delta_IW": iw, **m})
                except RuntimeError as exc:
                    failures.append({"thermal_label": thermal_label, "x_NH3": x, "delta_IW": iw, "reason": str(exc)})

    if rows:
        with (OUT / "chemistry_results.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    if failures:
        with (OUT / "chemistry_failures.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(failures[0].keys()))
            w.writeheader(); w.writerows(failures)

    summary = []
    for label in THERMAL_LABELS:
        rr = [r for r in rows if r["thermal_label"] == label]
        ff = [r for r in failures if r["thermal_label"] == label]
        summary.append({
            "thermal_label": label,
            "successful_cases": len(rr),
            "failed_cases": len(ff),
            "first_quench_year": min((r["first_quench_year"] for r in rr), default=""),
            "HCN_positive_cases": sum(r["HCN_final_mol"] > 0 for r in rr),
            "HCN_final_mol_min": min((r["HCN_final_mol"] for r in rr), default=""),
            "HCN_final_mol_max": max((r["HCN_final_mol"] for r in rr), default=""),
        })
    with (OUT / "chemistry_summary.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0].keys()))
        w.writeheader(); w.writerows(summary)
    print(f"Chemistry propagation: {len(rows)} successes, {len(failures)} expected/diagnostic failures")


if __name__ == "__main__":
    main()
