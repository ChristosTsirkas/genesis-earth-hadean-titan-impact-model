#!/usr/bin/env python3
"""Run reproducible REBOUND delivery or collision-logger experiments.

The module deliberately separates pipeline validation from physical delivery
experiments.  A run is never promoted beyond the ``evidence_class`` declared in
its JSON configuration.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np

try:
    import rebound
except ImportError as exc:  # pragma: no cover - dependency error path
    raise SystemExit("REBOUND is required: python -m pip install rebound") from exc


AU_M = 1.495978707e11
YR_S = 365.25 * 86400.0
AU_YR_TO_KM_S = AU_M / YR_S / 1000.0
R_EARTH_AU = 6.371e6 / AU_M
M_EARTH_MSUN = 5.972e24 / 1.98847e30
V_ESC_MUT_KM_S = 9.55
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def portable_path(path: Path) -> str:
    """Record repository-relative paths so replay reports survive relocation."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


@dataclass
class EncounterMinimum:
    distance_au: float = math.inf
    speed_km_s: float = math.nan
    time_yr: float = math.nan


def load_config(path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if cfg["evidence_class"] not in {"pipeline_validation", "exploratory", "production_candidate"}:
        raise ValueError("Invalid evidence_class")
    if cfg.get("earth_radius_multiplier", 1.0) != 1.0 and cfg["evidence_class"] != "pipeline_validation":
        raise ValueError("An inflated Earth radius is allowed only for pipeline_validation")
    return cfg


def add_massive_bodies(sim: "rebound.Simulation", cfg: dict[str, Any]) -> None:
    sim.add(m=1.0, name="Sun")
    for body in cfg["massive_bodies"]:
        kwargs = {
            "m": float(body["mass_msun"]),
            "a": float(body["a_au"]),
            "e": float(body.get("e", 0.0)),
            "inc": math.radians(float(body.get("inc_deg", 0.0))),
            "Omega": math.radians(float(body.get("Omega_deg", 0.0))),
            "omega": math.radians(float(body.get("omega_deg", 0.0))),
            "M": math.radians(float(body.get("M_deg", 0.0))),
            "name": body["name"],
        }
        primary_name = body.get("primary")
        if primary_name:
            kwargs["primary"] = sim.particles[primary_name]
        if "radius_au" in body:
            kwargs["r"] = float(body["radius_au"])
        elif body["name"] == "Earth":
            kwargs["r"] = R_EARTH_AU * float(cfg.get("earth_radius_multiplier", 1.0))
        sim.add(**kwargs)


def add_outer_reservoir(sim: "rebound.Simulation", cfg: dict[str, Any], rng: np.random.Generator) -> list[str]:
    source = cfg["source"]
    particle_mass = float(source.get("particle_mass_msun", 0.0))
    names: list[str] = []
    for idx in range(int(source["n_particles"])):
        name = f"tp_{idx:06d}"
        sim.add(
            m=particle_mass,
            a=float(rng.uniform(source["a_min_au"], source["a_max_au"])),
            e=float(rng.uniform(source["e_min"], source["e_max"])),
            inc=math.radians(float(rng.rayleigh(source["inc_sigma_deg"]))),
            Omega=float(rng.uniform(0.0, 2.0 * math.pi)),
            omega=float(rng.uniform(0.0, 2.0 * math.pi)),
            M=float(rng.uniform(0.0, 2.0 * math.pi)),
            name=name,
        )
        names.append(name)
    return names


def add_perihelion_injection(
    sim: "rebound.Simulation", cfg: dict[str, Any], rng: np.random.Generator
) -> list[str]:
    """Add a post-release, high-eccentricity transport kernel.

    This generator does not manufacture a Nice-model instability.  It samples
    bodies *after* release from an outer reservoir, with semimajor axis ``a``
    and perihelion ``q`` declared independently in the configuration.  The
    resulting ensemble is useful for testing the transport and encounter
    stages while keeping the missing instability trigger explicit.
    """
    source = cfg["source"]
    names: list[str] = []
    for idx in range(int(source["n_particles"])):
        a_au = float(rng.uniform(source["a_min_au"], source["a_max_au"]))
        q_au = float(rng.uniform(source["q_min_au"], source["q_max_au"]))
        if not 0.0 < q_au < a_au:
            raise ValueError("perihelion_injection requires 0 < q < a")
        name = f"injected_{idx:06d}"
        sim.add(
            m=0.0,
            a=a_au,
            e=1.0 - q_au / a_au,
            inc=math.radians(float(rng.rayleigh(source["inc_sigma_deg"]))),
            Omega=float(rng.uniform(0.0, 2.0 * math.pi)),
            omega=float(rng.uniform(0.0, 2.0 * math.pi)),
            M=float(rng.uniform(0.0, 2.0 * math.pi)),
            name=name,
        )
        names.append(name)
    return names


def add_logger_validation_particles(
    sim: "rebound.Simulation", cfg: dict[str, Any], rng: np.random.Generator
) -> list[str]:
    earth = sim.particles["Earth"]
    source = cfg["source"]
    radius = R_EARTH_AU * float(cfg["earth_radius_multiplier"])
    names: list[str] = []
    for idx in range(int(source["n_particles"])):
        name = f"validation_{idx:04d}"
        miss = float(rng.uniform(0.0, source["max_impact_parameter_radii"])) * radius
        azimuth = float(rng.uniform(0.0, 2.0 * math.pi))
        distance = float(source["start_distance_radii"]) * radius
        speed = float(source["relative_speed_au_yr"])
        sim.add(
            m=0.0,
            x=earth.x + distance,
            y=earth.y + miss * math.cos(azimuth),
            z=earth.z + miss * math.sin(azimuth),
            vx=earth.vx - speed,
            vy=earth.vy,
            vz=earth.vz,
            name=name,
        )
        names.append(name)
    return names


def relative_state(particle_state, earth_state) -> tuple[np.ndarray, np.ndarray]:
    relative_position = np.array([
        particle_state.x - earth_state.x,
        particle_state.y - earth_state.y,
        particle_state.z - earth_state.z,
    ])
    relative_velocity = np.array([
        particle_state.vx - earth_state.vx,
        particle_state.vy - earth_state.vy,
        particle_state.vz - earth_state.vz,
    ])
    return relative_position, relative_velocity


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    cfg = load_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(cfg["seed"]))

    sim = rebound.Simulation()
    sim.units = ("yr", "AU", "Msun")
    add_massive_bodies(sim, cfg)
    sim.N_active = sim.N
    sim.testparticle_type = 1 if cfg["source"].get("backreaction", False) else 0
    if sim.testparticle_type == 1 and float(cfg["source"].get("particle_mass_msun", 0.0)) <= 0.0:
        raise ValueError("Back-reacting reservoir particles require particle_mass_msun > 0")

    generator = cfg["source"]["generator"]
    if generator == "outer_reservoir":
        test_names = add_outer_reservoir(sim, cfg, rng)
    elif generator == "perihelion_injection":
        test_names = add_perihelion_injection(sim, cfg, rng)
    elif generator == "collision_logger_validation":
        test_names = add_logger_validation_particles(sim, cfg, rng)
    else:
        raise ValueError(f"Unknown source generator: {generator}")

    sim.integrator = cfg["integrator"]
    if cfg["integrator"].lower() in {"whfast", "mercurius", "leapfrog"}:
        sim.dt = float(cfg["dt_yr"])
    # MERCURIUS requires REBOUND's direct collision search.  IAS15 uses the
    # line search in the synthetic logger test so fast crossings are detected
    # between output steps.
    collision_search = cfg.get(
        "collision_search",
        "direct" if cfg["integrator"].lower() == "mercurius" else "line",
    )
    if collision_search not in {"direct", "line", "tree", "linetree"}:
        raise ValueError(f"Unknown collision search: {collision_search}")
    sim.collision = collision_search
    sim.move_to_com()
    earth_index = next(
        idx for idx in range(sim.N_active) if sim.particles[idx].name == "Earth"
    )

    initial_energy = float(sim.energy())
    collisions: list[dict[str, Any]] = []
    removed: set[str] = set()

    def resolve_collision(sim_pointer, collision):
        local = sim_pointer.contents
        p1 = local.particles[collision.p1]
        p2 = local.particles[collision.p2]
        names = {p1.name, p2.name}
        if "Earth" not in names:
            return 0
        earth_particle = p1 if p1.name == "Earth" else p2
        impactor = p2 if p1.name == "Earth" else p1
        if not impactor.name.startswith(("tp_", "validation_", "injected_")):
            return 0
        relative_position, relative_velocity = relative_state(impactor, earth_particle)
        contact_distance = float(np.linalg.norm(relative_position))
        contact_speed = float(np.linalg.norm(relative_velocity) * AU_YR_TO_KM_S)
        cosine = abs(float(np.dot(relative_position, relative_velocity))) / max(
            float(np.linalg.norm(relative_position) * np.linalg.norm(relative_velocity)),
            1e-30,
        )
        theta = math.degrees(math.acos(float(np.clip(cosine, 0.0, 1.0))))
        v_inf = math.sqrt(max(contact_speed**2 - V_ESC_MUT_KM_S**2, 0.0))
        collisions.append({
            "particle": impactor.name,
            "time_yr": float(local.t),
            "contact_distance_au": contact_distance,
            "contact_speed_km_s": contact_speed,
            "v_inf_km_s": v_inf,
            "impact_angle_deg": theta,
            "grazing_60_75": 60.0 <= theta <= 75.0,
        })
        minima[impactor.name] = EncounterMinimum(
            distance_au=contact_distance,
            speed_km_s=contact_speed,
            time_yr=float(local.t),
        )
        removed.add(impactor.name)
        # REBOUND expects 1 to remove p1 and 2 to remove p2.  Use the collision
        # indices, not Python proxy identity, because Particle proxies are not
        # guaranteed to be the same object across accesses.
        return 2 if p1.name == "Earth" else 1

    sim.collision_resolve = resolve_collision
    minima = {name: EncounterMinimum() for name in test_names}
    inner_crossers: set[str] = set()
    inner_threshold_raw = cfg.get("inner_crossing_threshold_au")
    inner_threshold = (
        float(cast(float, inner_threshold_raw))
        if inner_threshold_raw is not None
        else None
    )
    n_samples = int(cfg["output_samples"])
    for target_time in np.linspace(0.0, float(cfg["duration_yr"]), n_samples + 1)[1:]:
        sim.integrate(float(target_time), exact_finish_time=0)
        earth = sim.particles[earth_index]
        current_test_particles = {
            sim.particles[idx].name: sim.particles[idx]
            for idx in range(sim.N_active, sim.N)
        }
        for name in test_names:
            if name in removed:
                continue
            if name not in current_test_particles:
                continue
            particle = current_test_particles[name]
            r, v = relative_state(particle, earth)
            distance = float(np.linalg.norm(r))
            if distance < minima[name].distance_au:
                minima[name] = EncounterMinimum(
                    distance_au=distance,
                    speed_km_s=float(np.linalg.norm(v) * AU_YR_TO_KM_S),
                    time_yr=float(sim.t),
                )
            if inner_threshold is not None:
                orbit = particle.orbit(primary=sim.particles["Sun"])
                if orbit.a > 0.0 and orbit.a * (1.0 - orbit.e) <= inner_threshold:
                    inner_crossers.add(name)

    final_energy = float(sim.energy())
    with (output_dir / "collisions.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["particle", "time_yr", "contact_distance_au", "contact_speed_km_s", "v_inf_km_s", "impact_angle_deg", "grazing_60_75"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(collisions, key=lambda row: row["particle"]))
    with (output_dir / "closest_approaches.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["particle", "time_yr", "distance_au", "relative_speed_km_s", "collided"])
        for name in test_names:
            value = minima[name]
            writer.writerow([name, value.time_yr, value.distance_au, value.speed_km_s, name in removed])

    summary = {
        "config": "config_used.json",
        "evidence_class": cfg["evidence_class"],
        "scientific_use": cfg["scientific_use"],
        "rebound_version": rebound.__version__,
        "seed": cfg["seed"],
        "integrator": cfg["integrator"],
        "collision_search": collision_search,
        "duration_yr": cfg["duration_yr"],
        "source_generator": generator,
        "test_particles_initial": len(test_names),
        "collisions_with_earth": len(collisions),
        "grazing_60_75": sum(bool(row["grazing_60_75"]) for row in collisions),
        "earth_radius_multiplier": cfg.get("earth_radius_multiplier", 1.0),
        "reservoir_backreaction": sim.testparticle_type == 1,
        "inner_crossing_threshold_au": inner_threshold,
        "inner_crossers": len(inner_crossers),
        "relative_energy_error": (final_energy - initial_energy) / initial_energy,
        "claim_boundary": "Pipeline-validation and exploratory runs are not delivery probabilities.",
    }
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output_dir / "config_used.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.config, args.output), indent=2))


if __name__ == "__main__":
    main()
