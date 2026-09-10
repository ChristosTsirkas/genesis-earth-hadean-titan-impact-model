#!/usr/bin/env python3
"""Validate the declared Run-9 resonant-chain campaign before execution."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from nbody.run_delivery import portable_path


M_EARTH_MSUN = 5.972e24 / 1.98847e30


def validate(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    bodies = {body["name"]: body for body in config["massive_bodies"]}
    names = config["resonant_chain_names"]
    expected = [float(value) for value in config["expected_period_ratios"]]
    if len(names) != len(expected) + 1:
        raise ValueError("A resonant chain needs one fewer period ratio than bodies")

    rows: list[dict[str, Any]] = []
    period_ratio_ok = True
    for inner_name, outer_name, expected_ratio in zip(names, names[1:], expected):
        actual_ratio = (float(bodies[outer_name]["a_au"]) / float(bodies[inner_name]["a_au"])) ** 1.5
        accepted = math.isclose(actual_ratio, expected_ratio, rel_tol=0.0, abs_tol=1e-10)
        period_ratio_ok &= accepted
        rows.append({
            "inner_body": inner_name,
            "outer_body": outer_name,
            "expected_period_ratio": expected_ratio,
            "actual_period_ratio": actual_ratio,
            "accepted": accepted,
        })

    source = config["source"]
    represented_mass_earth = (
        int(source["n_particles"]) * float(source["particle_mass_msun"]) / M_EARTH_MSUN
    )
    declared_mass_earth = float(source["total_disk_mass_earth"])
    disk_mass_ok = math.isclose(represented_mass_earth, declared_mass_earth, rel_tol=1e-6)
    outer_a = float(bodies[names[-1]]["a_au"])
    separated_disk = float(source["a_min_au"]) > outer_a
    backreaction_ok = bool(source.get("backreaction")) and float(source["particle_mass_msun"]) > 0.0
    status = period_ratio_ok and disk_mass_ok and separated_disk and backreaction_ok

    summary = {
        "status": "PASS" if status else "FAIL",
        "config": portable_path(config_path),
        "evidence_class": config["evidence_class"],
        "seed_count": len(config["seeds"]),
        "duration_per_seed_yr": config["duration_yr"],
        "disk_particles": source["n_particles"],
        "declared_disk_mass_earth": declared_mass_earth,
        "represented_disk_mass_earth": represented_mass_earth,
        "disk_inner_edge_au": source["a_min_au"],
        "outermost_planet_a_au": outer_a,
        "period_ratio_template_ok": period_ratio_ok,
        "disk_mass_ok": disk_mass_ok,
        "disk_planet_separation_ok": separated_disk,
        "backreaction_enabled": backreaction_ok,
        "claim_boundary": (
            "Passing validates campaign construction only. Resonant-angle libration, instability, "
            "delivery probability, numerical convergence and Earth-Moon encounter outcomes require execution."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "period_ratios.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "campaign_validation.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = validate(args.config, args.output)
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
