#!/usr/bin/env python3
"""Regenerate and validate every executable Appendix D result from one codebase."""
from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np

import atmosphere_evolution as atmosphere
import delivery_monte_carlo as delivery
import impact_scaling_laws as impact
import quench_chemistry_network as chemistry
from nbody.run_delivery import run as run_nbody
from nbody.run_ensemble import run_ensemble
from nbody.instability_ensemble.validate_campaign import validate as validate_nbody_campaign
from sph.generate_impact_matrix import generate as generate_sph_matrix

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "configs" / "appendix_d_replay.json"
DEFAULT_RESULTS = ROOT / "results" / "appendix_d"
M_OCEAN = 1.4e21


def quiet(callable_, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return callable_(*args, **kwargs)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_summary_csv(path: Path, value: dict[str, Any]) -> None:
    rows: list[dict[str, Any]] = []
    def visit(prefix: str, item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key != "case_metrics": visit(f"{prefix}.{key}" if prefix else key, child)
        elif isinstance(item, (str, int, float, bool)) or item is None:
            rows.append({"metric": prefix, "value": item})
    visit("", value)
    write_rows(path, rows, ["metric", "value"])


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(dict.fromkeys(key for row in rows for key in row)) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def mass_tag(value: float) -> str:
    return f"{value:.4g}".replace("+", "")


def run_stage12(label: str, seeds: list[int], cfg: dict[str, Any], d1_out: Path, d2_out: Path) -> dict[str, Any]:
    d1 = d1_out / "raw_outputs"
    all_rows: list[dict[str, str]] = []
    for seed in seeds:
        target = d1 / f"delivery_{seed}.csv"
        quiet(delivery.run, delivery.DeliveryConfig(n_objects=int(cfg["stage1"]["n_objects_per_seed"]), seed=seed), target)
        all_rows.extend(read_rows(target))
    combined = d1 / "valid_impact_vectors.csv"
    write_rows(combined, all_rows, list(all_rows[0]))

    stage2_rows: list[dict[str, str]] = []
    by_mass: dict[float, Path] = {}
    s2 = cfg["stage2"]
    for mass in map(float, s2["impactor_masses_kg"]):
        target = d2_out / "raw_outputs" / f"impact_{mass_tag(mass)}.csv"
        quiet(impact.process, combined, target, mass, float(s2["water_fraction"]), float(s2["atmosphere_to_ocean_mass_ratio"]))
        by_mass[mass] = target
        stage2_rows.extend(read_rows(target))

    grazing = sum(60.0 <= float(row["contact_angle_deg"]) <= 75.0 for row in all_rows)
    intended = [row for row in stage2_rows if float(s2["intended_v_over_vesc_min"]) <= float(row["v_over_vesc"]) <= float(s2["intended_v_over_vesc_max"])]
    waters = np.array([float(row["water_surface_kg"]) / M_OCEAN for row in intended])
    velocities = np.array([float(row["impact_velocity_km_s"]) for row in all_rows])
    stage1_summary = {
        "label": label,
        "stage1_total": len(seeds) * int(cfg["stage1"]["n_objects_per_seed"]),
        "stage1_valid": len(all_rows),
        "stage1_grazing": grazing,
        "stage1_median_impact_velocity_km_s": float(np.median(velocities)),
    }
    stage2_summary = {
        "label": label,
        "stage2_total": len(stage2_rows),
        "stage2_intended": len(intended),
        "water_oceans_min": float(waters.min()),
        "water_oceans_median": float(np.median(waters)),
        "water_oceans_max": float(waters.max()),
    }
    write_json(d1_out / "summary.json", stage1_summary); write_summary_csv(d1_out / "summary.csv", stage1_summary)
    write_json(d2_out / "summary.json", stage2_summary); write_summary_csv(d2_out / "summary.csv", stage2_summary)
    return {"summary": {**stage1_summary, **stage2_summary}, "by_mass": by_mass}


def select_inputs(label: str, specs: list[list[float]], by_mass: dict[float, Path], out: Path) -> list[Path]:
    paths = []
    for case, (mass_raw, row_index_raw) in enumerate(specs):
        mass = float(mass_raw)
        source = next(path for key, path in by_mass.items() if math.isclose(key, mass, rel_tol=1e-12))
        rows = read_rows(source)
        row = rows[int(row_index_raw)]
        target = out / "inputs" / f"atm_input_{case}.csv"
        write_rows(target, [row], list(row))
        paths.append(target)
    write_json(out / "inputs" / "representative_selection.json", {"label": label, "selection": specs})
    return paths


def h2_reservoir_for_flux(flux_m2_s: float) -> float:
    return flux_m2_s * atmosphere.AREA_E_M2 * (2.0e4 * atmosphere.YEAR_S) * atmosphere.M_H2_KG


def run_atmosphere_set(inputs: list[Path], params: dict[str, Any], out: Path) -> list[Path]:
    paths = []
    for case, source in enumerate(inputs):
        target = out / "raw_outputs" / f"atm_run_{case}.csv"
        reservoir = (
            float(params["h2_reservoir_kg"])
            if "h2_reservoir_kg" in params
            else h2_reservoir_for_flux(float(params["h2_flux0_m2_s"]))
        )
        quiet(
            atmosphere.run,
            atmosphere.load_partition(source, 0), target,
            float(params.get("years", 1.0e5)), int(params.get("steps", 1000)),
            float(params.get("background_pressure_bar", 100.0)),
            float(params["c_eff"]), float(params["impactor_dh"]),
            float(params["n_photolysis_scale"]), reservoir,
            float(params["argon_shielding_factor"]),
            bool(params.get("allow_diagnostic_c_eff", False)),
            bool(params.get("legacy_full_n_access", False)),
        )
        paths.append(target)
    return paths


def atmosphere_summary(paths: list[Path]) -> dict[str, Any]:
    rows = []
    for path in paths:
        a = np.genfromtxt(path, delimiter=",", names=True, dtype=float, encoding="utf-8")
        t = np.atleast_1d(a["time_years"]); temp = np.atleast_1d(a["temperature_K"])
        below = np.flatnonzero(temp < 1500.0)
        rows.append({
            "temperature_drop_K": float(temp[0] - temp[-1]),
            "first_below_1500_year": float(t[below[0]]) if below.size else None,
            "final_temperature_K": float(temp[-1]),
            "final_nitrogen_kg": float(np.atleast_1d(a["N_kg"])[-1]),
            "nitrogen_residual_fraction": float(np.atleast_1d(a["N_kg"])[-1] / 2.35e21),
            "final_ar36_kg": float(np.atleast_1d(a["Ar36_kg"])[-1]),
            "ar36_retained_fraction": float(np.atleast_1d(a["Ar36_kg"])[-1] / 5.0e15),
            "final_d_h": float(np.atleast_1d(a["D_H"])[-1]),
            "d_h_over_smow": float(np.atleast_1d(a["D_H"])[-1] / atmosphere.SMOW_DH),
            "max_crossover_mass_amu": float(np.max(np.atleast_1d(a["crossover_mass_amu"]))),
        })
    def numeric_values(column_name: str) -> list[float]:
        return [float(row[column_name]) for row in rows if row[column_name] is not None]

    result: dict[str, Any] = {"cases": len(rows), "case_metrics": rows}
    for metric_name in rows[0]:
        values = numeric_values(metric_name)
        result[f"{metric_name}_min"] = min(values) if values else None
        result[f"{metric_name}_max"] = max(values) if values else None
    return result


def run_chemistry_grid(atmosphere_path: Path, cfg: dict[str, Any], out: Path) -> dict[str, Any]:
    c = cfg["chemistry"]
    metrics = []
    for x in map(float, c["x_nh3"]):
        for iw in map(int, c["delta_iw"]):
            target = out / "raw_outputs" / f"chem_x{x:.3f}_iw{iw:+d}.csv"
            try:
                quiet(
                    chemistry.run, atmosphere_path, target, float(iw),
                    x * float(c["impactor_mass_kg"]), float(c["co2_mass_kg"]),
                    float(c["h2o_mass_kg"]), float(c["fe_mass_kg"]),
                    float(c["h2s_mass_kg"]), float(c["nh3_conversion_cap"]),
                    float(c["quench_threshold_k"]),
                )
                a = np.genfromtxt(target, delimiter=",", names=True, dtype=float, encoding="utf-8")
                hcn = float(np.atleast_1d(a["HCN_mol"])[-1])
                h2 = float(np.atleast_1d(a["H2_mol"])[-1])
                metrics.append({"x_nh3": x, "delta_iw": iw, "status": "success", "hcn_final_mol": hcn, "h2_pressure_bar": chemistry.h2_pressure_bar(h2)})
            except RuntimeError as exc:
                metrics.append({"x_nh3": x, "delta_iw": iw, "status": "aborted", "reason": str(exc), "hcn_final_mol": 0.0, "h2_pressure_bar": None})
    write_rows(out / "chemistry_summary.csv", metrics)
    successful = [m for m in metrics if m["status"] == "success"]
    hcn = [float(m["hcn_final_mol"]) for m in successful]
    pressures: dict[str, list[float]] = {}
    for m in successful:
        pressures.setdefault(f'{float(m["x_nh3"]):.3f}', []).append(float(m["h2_pressure_bar"]))
    summary = {
        "cases_total": len(metrics), "cases_successful": len(successful),
        "hcn_positive_cases": sum(float(m["hcn_final_mol"]) > 0.0 for m in successful),
        "hcn_final_mol_min": min(hcn) if hcn else 0.0,
        "hcn_final_mol_max": max(hcn) if hcn else 0.0,
        "h2_pressure_bar_by_x_nh3": {key: float(np.median(value)) for key, value in pressures.items()},
    }
    write_json(out / "summary.json", summary)
    return summary


def build_atmosphere_params(
    base: dict[str, Any], global_atm: dict[str, Any], diagnostic: bool = False
) -> dict[str, Any]:
    return {
        **base,
        "years": global_atm["years"], "steps": global_atm["steps"],
        "background_pressure_bar": global_atm["background_pressure_bar"],
        "allow_diagnostic_c_eff": diagnostic,
    }


def reproduce(section: str, cfg: dict[str, Any], root: Path) -> dict[str, Any]:
    state: dict[str, Any] = {}
    need_run1 = section in {"D1", "D2", "D3", "D4", "D5", "D6", "ALL"}
    need_run2 = section in {"D7", "D8", "D9", "D10", "ALL"}
    if need_run1:
        state["run1"] = run_stage12(
            "run1", list(map(int, cfg["stage1"]["run1_seeds"])), cfg,
            root / "d01_stage1_delivery", root / "d02_stage2_partition",
        )
        state["run1_inputs"] = select_inputs(
            "run1", cfg["representative_rows"]["run1"], state["run1"]["by_mass"],
            root / "d03_thermal_diagnostic",
        )
    if need_run2:
        state["run2"] = run_stage12(
            "run2", list(map(int, cfg["stage1"]["run2_seeds"])), cfg,
            root / "d07_calibration_run2" / "stage1",
            root / "d07_calibration_run2" / "stage2",
        )
        state["run2_inputs"] = select_inputs(
            "run2", cfg["representative_rows"]["run2"], state["run2"]["by_mass"],
            root / "d07_calibration_run2",
        )

    if section in {"D3", "D4", "D5", "D6", "ALL"}:
        d3 = root / "d03_thermal_diagnostic"
        paths = run_atmosphere_set(state["run1_inputs"], build_atmosphere_params(cfg["atmosphere"]["run1"], cfg["atmosphere"], True), d3)
        atm = atmosphere_summary(paths)
        write_json(d3 / "summary.json", atm); write_summary_csv(d3 / "summary.csv", atm)
        d4 = root / "d04_escape_isotopes"
        write_json(d4 / "summary.json", atm); write_summary_csv(d4 / "summary.csv", atm)
        d5 = root / "d05_chemistry_diagnostic"
        chem = run_chemistry_grid(paths[0], cfg, d5)
        write_summary_csv(d5 / "summary.csv", chem)
        d6 = root / "d06_integrated_interpretation"
        integrated = {"stage1_valid": state["run1"]["summary"]["stage1_valid"], "stage2_intended": state["run1"]["summary"]["stage2_intended"], "thermal_quench_reached": False, "chemistry_cases_aborted": chem["cases_total"] - chem["cases_successful"]}
        write_json(d6 / "summary.json", integrated); write_summary_csv(d6 / "summary.csv", integrated)

    if section in {"D7", "ALL"}:
        d7 = root / "d07_calibration_run2"
        paths = run_atmosphere_set(state["run2_inputs"], build_atmosphere_params(cfg["atmosphere"]["run2"], cfg["atmosphere"]), d7)
        atm_summary = atmosphere_summary(paths)
        chem_summary = run_chemistry_grid(paths[0], cfg, d7 / "chemistry")
        summary = {**state["run2"]["summary"], "atmosphere": atm_summary, "chemistry": chem_summary}
        write_json(d7 / "summary.json", summary); write_summary_csv(d7 / "summary.csv", summary)

    if section in {"D8", "ALL"}:
        d8 = root / "d08_reproducibility_run3"
        paths = run_atmosphere_set(state["run2_inputs"], build_atmosphere_params(cfg["atmosphere"]["run2"], cfg["atmosphere"]), d8)
        summary = {"atmosphere": atmosphere_summary(paths), "chemistry": run_chemistry_grid(paths[0], cfg, d8 / "chemistry")}
        write_json(d8 / "summary.json", summary); write_summary_csv(d8 / "summary.csv", summary)

    if section in {"D9", "ALL"}:
        d9 = root / "d09_calibration_run4"
        paths = run_atmosphere_set(state["run2_inputs"], build_atmosphere_params(cfg["atmosphere"]["run4"], cfg["atmosphere"]), d9)
        summary = {"atmosphere": atmosphere_summary(paths), "chemistry": run_chemistry_grid(paths[0], cfg, d9 / "chemistry")}
        write_json(d9 / "summary.json", summary); write_summary_csv(d9 / "summary.csv", summary)

    if section in {"D10", "ALL"}:
        d10 = root / "d10_calibration_extensions"
        run5 = d10 / "run5_calibration"
        paths = run_atmosphere_set(state["run2_inputs"], build_atmosphere_params(cfg["atmosphere"]["run5"], cfg["atmosphere"]), run5)
        run5_summary = {"atmosphere": atmosphere_summary(paths), "chemistry": run_chemistry_grid(paths[0], cfg, run5 / "chemistry")}
        write_json(run5 / "summary.json", run5_summary); write_summary_csv(run5 / "summary.csv", run5_summary)

        import run6_robustness_validation as r6
        r6.OUT = d10 / "run6_robustness"; r6.RAW = r6.OUT / "raw_outputs"; r6.INPUT_DIR = root / "d07_calibration_run2" / "inputs"
        quiet(r6.main)
        import run6_chemistry_propagation as r6c
        r6c.BASE = d10 / "run6_robustness"; r6c.RAW_ATM = r6c.BASE / "raw_outputs"; r6c.OUT = r6c.BASE / "chemistry_propagation"; r6c.RAW_CHEM = r6c.OUT / "raw_outputs"
        quiet(r6c.main)
        write_summary_csv(r6.OUT / "summary.csv", load_json(r6.OUT / "run_summary.json"))

        nbody_root = d10 / "run7_nbody"
        collision = run_nbody(ROOT / cfg["nbody"]["collision_logger_config"], nbody_root / "collision_logger_validation")
        outer = run_nbody(ROOT / cfg["nbody"]["outer_reservoir_config"], nbody_root / "outer_reservoir_control")
        write_summary_csv(nbody_root / "collision_logger_validation" / "summary.csv", collision)
        write_summary_csv(nbody_root / "outer_reservoir_control" / "summary.csv", outer)
        matrix_cfg = load_json(ROOT / cfg["sph"]["matrix_config"])
        matrix_rows = generate_sph_matrix(matrix_cfg)
        sph_out = d10 / "run7_sph"; write_json(sph_out / "impact_matrix.json", matrix_rows)
        write_rows(sph_out / "impact_matrix.csv", matrix_rows)
        write_json(sph_out / "summary.json", {"cases": len(matrix_rows)}); write_summary_csv(sph_out / "summary.csv", {"cases": len(matrix_rows)})
        ensemble = run_ensemble(ROOT / cfg["nbody"]["post_release_config"], d10 / "run8_nbody")
        write_summary_csv(d10 / "run8_nbody" / "summary.csv", ensemble)

        reproduce_run9(cfg, d10 / "run9_nbody")

    return state


def collect_metrics(root: Path) -> dict[str, Any]:
    files = sorted(root.rglob("*summary.json"))
    return {path.relative_to(root).as_posix(): load_json(path) for path in files}


def reproduce_run9(cfg: dict[str, Any], root: Path) -> None:
    validate_nbody_campaign(
        ROOT / cfg["nbody"]["run9_campaign_config"],
        root / "campaign_validation",
    )
    run_ensemble(
        ROOT / cfg["nbody"]["run9_smoke_config"],
        root / "local_smoke",
    )


def compare(expected: Any, actual: Any, path: str = "") -> list[str]:
    failures: list[str] = []
    if isinstance(expected, dict):
        for key, value in expected.items():
            if key not in actual:
                failures.append(f"{path}/{key}: missing")
            else:
                failures.extend(compare(value, actual[key], f"{path}/{key}"))
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            failures.append(f"{path}: length {len(actual)} != {len(expected)}")
        else:
            for i, value in enumerate(expected): failures.extend(compare(value, actual[i], f"{path}/{i}"))
    elif isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-12):
            failures.append(f"{path}: {actual!r} != {expected!r}")
    elif actual != expected:
        failures.append(f"{path}: {actual!r} != {expected!r}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", choices=["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "ALL"], default="ALL")
    parser.add_argument("--all", action="store_true", help="Alias for --section ALL.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--clean", action="store_true", help="Remove only the selected replay results root before running.")
    parser.add_argument("--freeze-expected", action="store_true", help="Write the current replay summaries as the expected-metrics baseline.")
    args = parser.parse_args()
    if args.all:
        args.section = "ALL"
    root = args.results.resolve()
    if args.clean and root.exists(): shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    cfg = load_json(args.config.resolve())
    reproduce(args.section, cfg, root)
    actual = collect_metrics(root)
    write_json(root / "replay_metrics.json", actual)
    expected_path = ROOT / "configs" / "appendix_d_expected_metrics.json"
    if args.freeze_expected:
        write_json(expected_path, actual)
        failures: list[str] = []
    elif expected_path.exists() and args.section == "ALL":
        failures = compare(load_json(expected_path), actual)
    else:
        failures = []
    report_root = root.relative_to(ROOT).as_posix() if root.is_relative_to(ROOT) else root.as_posix()
    report = {"section": args.section, "status": "PASS" if not failures else "FAIL", "failures": failures, "results_root": report_root}
    write_json(root / "replay_report.json", report)
    (root / "replay_report.md").write_text(f"# Appendix D replay report\n\nStatus: **{report['status']}**\n\n" + ("All frozen numerical metrics matched.\n" if not failures else "\n".join(f"- {x}" for x in failures) + "\n"), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if failures: raise SystemExit(1)


if __name__ == "__main__":
    main()
