import json
import tempfile
import unittest
from pathlib import Path

from nbody.run_delivery import load_config, run
from nbody.run_ensemble import _wilson_interval, run_ensemble
from nbody.instability_ensemble.validate_campaign import validate


ROOT = Path(__file__).resolve().parents[2]


class NBodyTests(unittest.TestCase):
    def test_inflation_is_validation_only(self):
        source = ROOT / "nbody/configs/collision_logger_validation.json"
        cfg = json.loads(source.read_text())
        cfg["evidence_class"] = "exploratory"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):
                load_config(path)

    def test_collision_logger_smoke_run(self):
        config = ROOT / "nbody/configs/collision_logger_validation.json"
        with tempfile.TemporaryDirectory() as tmp:
            summary = run(config, Path(tmp))
            self.assertEqual(summary["evidence_class"], "pipeline_validation")
            self.assertGreater(summary["collisions_with_earth"], 0)
            self.assertTrue((Path(tmp) / "collisions.csv").exists())

    def test_post_instability_generator_smoke_run(self):
        source = ROOT / "nbody/configs/post_instability_injection_pilot.json"
        cfg = json.loads(source.read_text())
        cfg["duration_yr"] = 0.02
        cfg["output_samples"] = 2
        cfg["source"]["n_particles"] = 4
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pilot.json"
            path.write_text(json.dumps(cfg))
            summary = run(path, Path(tmp) / "run")
            self.assertEqual(summary["source_generator"], "perihelion_injection")
            self.assertEqual(summary["earth_radius_multiplier"], 1.0)

    def test_ensemble_aggregation(self):
        source = ROOT / "nbody/configs/collision_logger_validation.json"
        cfg = json.loads(source.read_text())
        cfg["seeds"] = [410006, 410007]
        cfg["source"]["n_particles"] = 4
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ensemble.json"
            path.write_text(json.dumps(cfg))
            summary = run_ensemble(path, Path(tmp) / "ensemble")
            self.assertEqual(summary["run_count"], 2)
            self.assertEqual(summary["test_particles_total"], 8)
            self.assertTrue((Path(tmp) / "ensemble/ensemble_summary.json").exists())

    def test_wilson_interval_contains_observed_fraction(self):
        low, high = _wilson_interval(3, 10)
        self.assertLessEqual(low, 0.3)
        self.assertGreaterEqual(high, 0.3)

    def test_run9_campaign_definition(self):
        config = ROOT / "nbody/instability_ensemble/configs/literature_anchored_campaign.json"
        with tempfile.TemporaryDirectory() as tmp:
            summary = validate(config, Path(tmp))
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["backreaction_enabled"])
            self.assertEqual(summary["seed_count"], 8)

    def test_run9_backreaction_smoke(self):
        source = ROOT / "nbody/instability_ensemble/configs/local_smoke.json"
        config = json.loads(source.read_text())
        config["duration_yr"] = 0.04
        config["output_samples"] = 2
        config["source"]["n_particles"] = 4
        config["source"]["particle_mass_msun"] = (
            config["source"]["total_disk_mass_earth"] * 3.0034896e-6 / 4
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run9_smoke.json"
            path.write_text(json.dumps(config))
            summary = run(path, Path(tmp) / "run")
            self.assertTrue(summary["reservoir_backreaction"])
            self.assertEqual(summary["source_generator"], "outer_reservoir")


if __name__ == "__main__":
    unittest.main()
