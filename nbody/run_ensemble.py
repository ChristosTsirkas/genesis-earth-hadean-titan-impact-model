#!/usr/bin/env python3
"""Run and aggregate a deterministic multi-seed REBOUND ensemble."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from nbody.run_delivery import portable_path, run


def _config_digest(config: dict[str, Any]) -> str:
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if trials <= 0:
        return math.nan, math.nan
    p = successes / trials
    denominator = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denominator
    half_width = z * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)) / denominator
    return max(0.0, center - half_width), min(1.0, center + half_width)


def run_ensemble(config_path: Path, output_dir: Path, seeds: list[int] | None = None) -> dict[str, Any]:
    master = json.loads(config_path.read_text(encoding="utf-8"))
    declared_seeds = seeds if seeds is not None else [int(value) for value in master.pop("seeds")]
    if not declared_seeds or len(set(declared_seeds)) != len(declared_seeds):
        raise ValueError("Ensemble seeds must be a non-empty set of unique integers")

    output_dir.mkdir(parents=True, exist_ok=True)
    config_dir = output_dir / "configs"
    config_dir.mkdir(exist_ok=True)
    summaries: list[dict[str, Any]] = []
    combined_collisions: list[dict[str, Any]] = []

    for seed in declared_seeds:
        run_name = f"seed_{seed}"
        seed_config = dict(master)
        seed_config["seed"] = seed
        seed_config_path = config_dir / f"{run_name}.json"
        seed_config_path.write_text(json.dumps(seed_config, indent=2) + "\n", encoding="utf-8")
        run_dir = output_dir / run_name
        summary = run(seed_config_path, run_dir)
        summary["run_name"] = run_name
        summaries.append(summary)

        with (run_dir / "collisions.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                combined_collisions.append({"run_name": run_name, "seed": seed, **row})

    total_particles = sum(int(item["test_particles_initial"]) for item in summaries)
    total_collisions = sum(int(item["collisions_with_earth"]) for item in summaries)
    total_grazing = sum(int(item["grazing_60_75"]) for item in summaries)
    ci_low, ci_high = _wilson_interval(total_collisions, total_particles)
    grazing_low, grazing_high = _wilson_interval(total_grazing, total_collisions)
    duration = float(master["duration_yr"])

    if master["source"]["generator"] == "perihelion_injection":
        claim_boundary = (
            "This post-release transport pilot conditions on injected high-eccentricity orbits. "
            "It is not a self-consistent giant-planet instability, an absolute source-to-Earth "
            "delivery probability, or evidence for a Titan-mass impact."
        )
    else:
        claim_boundary = (
            "This ensemble inherits the evidence class and scientific-use boundary declared in "
            "its configuration. A short pipeline-validation run does not measure an instability "
            "timescale or an absolute source-to-Earth delivery probability."
        )

    aggregate = {
        "config": portable_path(config_path),
        "config_sha256": _config_digest(master),
        "evidence_class": master["evidence_class"],
        "scientific_use": master["scientific_use"],
        "source_generator": master["source"]["generator"],
        "seeds": declared_seeds,
        "run_count": len(summaries),
        "duration_per_run_yr": duration,
        "test_particles_per_run": int(master["source"]["n_particles"]),
        "test_particles_total": total_particles,
        "particle_years": total_particles * duration,
        "earth_collisions_total": total_collisions,
        "grazing_60_75_total": total_grazing,
        "collision_fraction_per_integrated_particle": total_collisions / total_particles,
        "collision_fraction_wilson_95": [ci_low, ci_high],
        "grazing_fraction_of_collisions": total_grazing / total_collisions if total_collisions else None,
        "grazing_fraction_wilson_95": [grazing_low, grazing_high] if total_collisions else None,
        "max_abs_relative_energy_error": max(abs(float(item["relative_energy_error"])) for item in summaries),
        "claim_boundary": claim_boundary,
    }

    with (output_dir / "runs.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "run_name", "seed", "duration_yr", "test_particles_initial",
            "collisions_with_earth", "grazing_60_75", "relative_energy_error",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in summaries:
            writer.writerow({key: item[key] for key in fields})

    with (output_dir / "collisions.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "run_name", "seed", "particle", "time_yr", "contact_distance_au",
            "contact_speed_km_s", "v_inf_km_s", "impact_angle_deg", "grazing_60_75",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(combined_collisions)

    (output_dir / "ensemble_summary.json").write_text(
        json.dumps(aggregate, indent=2) + "\n", encoding="utf-8"
    )
    return aggregate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", help="Optional comma-separated override")
    args = parser.parse_args()
    seeds = [int(value) for value in args.seeds.split(",")] if args.seeds else None
    print(json.dumps(run_ensemble(args.config, args.output, seeds), indent=2))


if __name__ == "__main__":
    main()
