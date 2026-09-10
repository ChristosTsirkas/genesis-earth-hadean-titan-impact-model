#!/usr/bin/env python3
"""Generate a reproducible SWIFT planetary-impact run matrix."""

from __future__ import annotations

import argparse
import csv
import json
import math
from itertools import product
from pathlib import Path


G = 6.67430e-11
M_EARTH = 5.972e24
R_EARTH = 6.371e6
M_TITAN = 1.345e23
R_TITAN = 2.575e6


def mutual_escape_speed(mass_kg: float, radius_m: float) -> float:
    return math.sqrt(2.0 * G * (M_EARTH + mass_kg) / (R_EARTH + radius_m))


def generate(config: dict) -> list[dict]:
    rows = []
    run_id = 0
    for mass_scale, speed_ratio, angle, water_fraction, particles in product(
        config["impactor_mass_titan"], config["speed_over_mutual_escape"],
        config["impact_angles_deg"], config["water_mass_fractions"],
        config["particle_counts"],
    ):
        mass = mass_scale * M_TITAN
        radius = R_TITAN * mass_scale ** (1.0 / 3.0)
        escape = mutual_escape_speed(mass, radius)
        rows.append({
            "run_id": f"sph_{run_id:04d}",
            "evidence_class": "pipeline_validation" if particles <= 100_000 else "hpc_resolution_study",
            "impactor_mass_kg": mass,
            "impactor_radius_m": radius,
            "water_mass_fraction": water_fraction,
            "impact_angle_deg": angle,
            "contact_impact_parameter": math.sin(math.radians(angle)),
            "mutual_escape_speed_m_s": escape,
            "impact_speed_m_s": speed_ratio * escape,
            "particle_count": int(particles),
            "initial_conditions": f"initial_conditions/sph_{run_id:04d}.hdf5",
        })
        run_id += 1
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text())
    rows = generate(cfg)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "impact_matrix.json").write_text(json.dumps(rows, indent=2) + "\n")
    with (args.output / "impact_matrix.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"runs": len(rows), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()

