#!/usr/bin/env python3
"""Structurally validate a SWIFT planetary HDF5 initial-condition file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = {
    "Header": [],
    "PartType0": ["Coordinates", "Velocities", "Masses", "ParticleIDs", "SmoothingLengths", "InternalEnergies", "MaterialIDs"],
}


def validate(path: Path) -> dict:
    try:
        import h5py
    except ImportError as exc:
        raise SystemExit("h5py is required to inspect SWIFT HDF5 files") from exc
    errors = []
    with h5py.File(path, "r") as handle:
        for group, datasets in REQUIRED.items():
            if group not in handle:
                errors.append(f"missing group: {group}")
                continue
            for dataset in datasets:
                if dataset not in handle[group]:
                    errors.append(f"missing dataset: {group}/{dataset}")
        count = int(handle["PartType0/Masses"].shape[0]) if "PartType0/Masses" in handle else 0
        if count:
            for dataset in REQUIRED["PartType0"]:
                if dataset in handle["PartType0"] and handle[f"PartType0/{dataset}"].shape[0] != count:
                    errors.append(f"particle-count mismatch: PartType0/{dataset}")
    return {"file": str(path), "particle_count": count, "valid": not errors, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("file", type=Path)
    args = parser.parse_args(); result = validate(args.file)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()

