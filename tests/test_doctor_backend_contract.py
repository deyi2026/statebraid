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
        self.assertEqual(len(report["known_adapters"]), 2)
        adapters = {item["name"]: item for item in report["known_adapters"]}
        mlx = adapters["mlx-lm"]
        self.assertEqual(mlx["integration_level"], "generation-safe-managed")
        self.assertIn("generation_safety", mlx["capabilities"])
        self.assertEqual(mlx["observation_profile"]["mode"], "passive")
        self.assertTrue(mlx["observation_profile"]["may_mutate_backend_state"])
        self.assertTrue(mlx["qualification_profile"]["runtime_qualified"])
        llama = adapters["llama.cpp"]
        self.assertEqual(llama["integration_level"], "partial")
        self.assertEqual(
            llama["capabilities"],
            ["generation_safety", "hit_attribution", "prefix_lookup"],
        )
        self.assertNotIn("namespace_isolation", llama["capabilities"])
        self.assertEqual(
            llama["observation_profile"]["mode"], "execution_coupled"
        )
        self.assertTrue(llama["observation_profile"]["may_mutate_backend_state"])
        self.assertFalse(llama["qualification_profile"]["runtime_qualified"])
        self.assertEqual(
            llama["qualification_profile"]["source_revision"],
            "465e49b9cea78a68b9c244ffb48d0ee24a82873d",
        )


if __name__ == "__main__":
    unittest.main()
