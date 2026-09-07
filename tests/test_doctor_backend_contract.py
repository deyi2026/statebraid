import io
import json
import unittest
from contextlib import redirect_stdout

from statebraid.doctor import main


class DoctorBackendContractTest(unittest.TestCase):
    def test_machine_readable_backend_contract(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["contract", "--json"])
        self.assertEqual(exit_code, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["backend_contract_version"], "0.2")
        self.assertIn("model execution", report["backend_owns"])
        self.assertIn(
            "exact namespace + token cache identity", report["statebraid_owns"]
        )
        self.assertEqual(len(report["known_adapters"]), 1)
        mlx = report["known_adapters"][0]
        self.assertEqual(mlx["name"], "mlx-lm")
        self.assertEqual(mlx["integration_level"], "generation-safe-managed")
        self.assertIn("generation_safety", mlx["capabilities"])


if __name__ == "__main__":
    unittest.main()
