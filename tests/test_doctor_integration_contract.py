import io
import json
import unittest
from contextlib import redirect_stdout

from statebraid.doctor import main
from statebraid.integration import integration_contract_metadata


class DoctorIntegrationContractTest(unittest.TestCase):
    def test_machine_readable_harness_boundary_matches_package_metadata(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["integration", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload, integration_contract_metadata())
        self.assertEqual(payload["integration_contract_version"], "0.1")
        self.assertEqual(
            payload["backend_selection"], "external-harness-or-gateway-owned"
        )
        for forbidden in (
            "goal",
            "selected_evidence",
            "working_state",
            "checkpoint_meaning",
            "tool_relevance",
            "completion_state",
            "fold_decision",
            "retry_desirability",
            "cache_tag",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertIn(forbidden, payload["forbidden_semantic_fields"])


if __name__ == "__main__":
    unittest.main()
