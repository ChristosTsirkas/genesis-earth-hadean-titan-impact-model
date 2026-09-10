#!/usr/bin/env python3
"""Compute transparent first-pass mass diagnostics from a SWIFT snapshot.

This is not a replacement for an iterative friends-of-friends/remnant finder.
It reports material totals and a two-body specific-energy bound estimate around
a caller-supplied remnant center, velocity and mass.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


G = 6.67430e-11


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--centre-m", nargs=3, type=float, required=True)
    parser.add_argument("--velocity-m-s", nargs=3, type=float, required=True)
    parser.add_argument("--remnant-mass-kg", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        import h5py
    except ImportError as exc:
        raise SystemExit("h5py is required to inspect SWIFT snapshots") from exc
    with h5py.File(args.snapshot, "r") as handle:
        group = handle["PartType0"]
        coordinates = np.asarray(group["Coordinates"], dtype=float)
        velocities = np.asarray(group["Velocities"], dtype=float)
        masses = np.asarray(group["Masses"], dtype=float)
        materials = np.asarray(group["MaterialIDs"], dtype=int)
    r = np.linalg.norm(coordinates - np.asarray(args.centre_m), axis=1)
    v2 = np.sum((velocities - np.asarray(args.velocity_m_s)) ** 2, axis=1)
    energy = 0.5 * v2 - G * args.remnant_mass_kg / np.maximum(r, 1.0)
    bound = energy < 0.0
    totals = {}
    for material in np.unique(materials):
        mask = materials == material
        totals[str(int(material))] = {
            "total_mass_kg": float(masses[mask].sum()),
            "bound_mass_kg": float(masses[mask & bound].sum()),
        }
    result = {
        "snapshot": str(args.snapshot),
        "particle_count": int(len(masses)),
        "bound_mass_kg": float(masses[bound].sum()),
        "unbound_mass_kg": float(masses[~bound].sum()),
        "materials": totals,
        "claim_boundary": "Two-body energy diagnostic only; iterative remnant and disk classification remains required.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

