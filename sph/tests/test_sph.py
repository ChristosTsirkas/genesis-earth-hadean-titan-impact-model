import json
import math
import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np

from sph.generate_impact_matrix import generate
from sph.validate_swift_ic import validate


ROOT = Path(__file__).resolve().parents[2]


class SPHMatrixTests(unittest.TestCase):
    def test_matrix_geometry_and_count(self):
        cfg = json.loads((ROOT / "sph/configs/impact_matrix.json").read_text())
        rows = generate(cfg)
        expected = math.prod(len(cfg[key]) for key in cfg)
        self.assertEqual(len(rows), expected)
        self.assertTrue(all(60.0 <= row["impact_angle_deg"] <= 75.0 for row in rows))
        self.assertTrue(all(0.0 < row["contact_impact_parameter"] < 1.0 for row in rows))
        self.assertTrue(all(row["impact_speed_m_s"] > 0.0 for row in rows))

    def test_swift_ic_structure_validator(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "minimal_ic.hdf5"
            with h5py.File(path, "w") as handle:
                handle.create_group("Header")
                hydro = handle.create_group("PartType0")
                hydro.create_dataset("Coordinates", data=np.zeros((2, 3)))
                hydro.create_dataset("Velocities", data=np.zeros((2, 3)))
                hydro.create_dataset("Masses", data=np.ones(2))
                hydro.create_dataset("ParticleIDs", data=np.arange(2))
                hydro.create_dataset("SmoothingLengths", data=np.ones(2))
                hydro.create_dataset("InternalEnergies", data=np.ones(2))
                hydro.create_dataset("MaterialIDs", data=np.zeros(2, dtype=int))
            result = validate(path)
            self.assertTrue(result["valid"])
            self.assertEqual(result["particle_count"], 2)


if __name__ == "__main__":
    unittest.main()
