import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from statebraid.compat.llama_cpp import LlamaCppCompatibilityReport
from statebraid.doctor import main


class DoctorLlamaCppTest(unittest.TestCase):
    def test_json_probe_reports_partial_single_domain_contract(self):
        report = LlamaCppCompatibilityReport(
            reachable=True,
            compatible=True,
            slots_endpoint=True,
            slot_count=2,
            total_slots=2,
            build_info="b999-465e49b9",
            source_commit="465e49b9",
            reference_source_match=True,
            issues=("single-domain only",),
        )
        output = io.StringIO()
        with patch("statebraid.doctor.probe_llama_cpp_server", return_value=report) as probe:
            with redirect_stdout(output):
                exit_code = main(["llama-cpp", "--url", "http://llama:8080", "--json"])
        self.assertEqual(exit_code, 0)
        probe.assert_called_once_with("http://llama:8080")
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["integration_level"], "partial")
        self.assertFalse(payload["namespace_isolation"])
        self.assertTrue(payload["single_domain_only"])
        self.assertFalse(payload["runtime_qualified"])
        self.assertTrue(payload["reference_qualified"])
        self.assertIn("generation_safety", payload["declared_capabilities"])

    def test_incompatible_probe_exits_two(self):
        report = LlamaCppCompatibilityReport(
            reachable=False,
            compatible=False,
            slots_endpoint=False,
            slot_count=0,
            total_slots=None,
            build_info=None,
            source_commit=None,
            reference_source_match=False,
            issues=("offline",),
        )
        with patch("statebraid.doctor.probe_llama_cpp_server", return_value=report):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["llama-cpp"]), 2)


if __name__ == "__main__":
    unittest.main()
