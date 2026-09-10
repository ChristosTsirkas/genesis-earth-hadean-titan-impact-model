#!/usr/bin/env python3
"""Compare a fresh replay against the bundled immutable reference outputs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


IGNORED_NAMES = {"comparison_report.json"}
NBODY_RAW_RTOL = 1e-6


def coerce_csv_value(value: str) -> Any:
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return value


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [
            {key: coerce_csv_value(value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, default=str))


def compare_values(reference: Any, generated: Any, path: str, differences: list[str], rtol: float, atol: float) -> None:
    if isinstance(reference, dict) and isinstance(generated, dict):
        for key in sorted(reference.keys() | generated.keys()):
            if key not in reference:
                differences.append(f"{path}.{key}: generated-only key")
            elif key not in generated:
                differences.append(f"{path}.{key}: missing key")
            else:
                compare_values(reference[key], generated[key], f"{path}.{key}", differences, rtol, atol)
        return
    if isinstance(reference, list) and isinstance(generated, list):
        if len(reference) != len(generated):
            differences.append(f"{path}: length {len(generated)} != {len(reference)}")
            return
        for index, (ref_item, gen_item) in enumerate(zip(reference, generated)):
            compare_values(ref_item, gen_item, f"{path}[{index}]", differences, rtol, atol)
        return
    if isinstance(reference, (int, float)) and isinstance(generated, (int, float)):
        effective_rtol = (
            max(rtol, NBODY_RAW_RTOL)
            if path.startswith("d10_calibration_extensions/run8_nbody/")
            and "/closest_approaches.csv" in path
            else rtol
        )
        if not math.isclose(float(reference), float(generated), rel_tol=effective_rtol, abs_tol=atol):
            differences.append(f"{path}: {generated!r} != {reference!r}")
        return
    if reference != generated:
        differences.append(f"{path}: {generated!r} != {reference!r}")


def compare_trees(reference_root: Path, generated_root: Path, rtol: float, atol: float) -> dict[str, Any]:
    generated_files = {
        path.relative_to(generated_root)
        for path in generated_root.rglob("*")
        if path.is_file() and path.name not in IGNORED_NAMES
    }
    reference_files = {
        path.relative_to(reference_root)
        for path in reference_root.rglob("*")
        if path.is_file() and path.name not in IGNORED_NAMES
    }
    missing = sorted(path.as_posix() for path in reference_files - generated_files)
    unexpected = sorted(path.as_posix() for path in generated_files - reference_files)
    differences: list[str] = []
    checked = 0
    for relative_path in sorted(reference_files & generated_files):
        reference_path = reference_root / relative_path
        generated_path = generated_root / relative_path
        if relative_path.suffix == ".json":
            compare_values(
                json.loads(reference_path.read_text(encoding="utf-8")),
                json.loads(generated_path.read_text(encoding="utf-8")),
                relative_path.as_posix(),
                differences,
                rtol,
                atol,
            )
        elif relative_path.suffix == ".csv":
            compare_values(
                read_csv_rows(reference_path),
                read_csv_rows(generated_path),
                relative_path.as_posix(),
                differences,
                rtol,
                atol,
            )
        elif relative_path.suffix in {".md", ".txt"}:
            reference_text = reference_path.read_text(encoding="utf-8").replace("\r\n", "\n")
            generated_text = generated_path.read_text(encoding="utf-8").replace("\r\n", "\n")
            if reference_text != generated_text:
                differences.append(f"{relative_path}: text content differs")
        else:
            if reference_path.read_bytes() != generated_path.read_bytes():
                differences.append(f"{relative_path}: byte content differs")
        checked += 1
    return {
        "status": "PASS" if not missing and not unexpected and not differences else "FAIL",
        "reference_root": reference_root.as_posix(),
        "generated_root": generated_root.as_posix(),
        "files_checked": checked,
        "missing_files": missing,
        "unexpected_files": unexpected,
        "differences": differences[:200],
        "difference_count": len(differences),
        "relative_tolerance": rtol,
        "absolute_tolerance": atol,
        "run8_closest_approach_relative_tolerance": NBODY_RAW_RTOL,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, default=Path("results_cached/appendix_d"))
    parser.add_argument("--generated", type=Path, default=Path("results/appendix_d"))
    parser.add_argument("--rtol", type=float, default=1e-10)
    parser.add_argument("--atol", type=float, default=1e-12)
    parser.add_argument("--report", type=Path, default=Path("results/comparison_report.json"))
    args = parser.parse_args()
    report = compare_trees(args.reference, args.generated, args.rtol, args.atol)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
