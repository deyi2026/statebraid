import unittest

from statebraid.compat.llama_cpp import probe_llama_cpp_server


class FakeTransport:
    def __init__(self, *, props=None, slots=None, error=None):
        self.props = props
        self.slots = slots
        self.error = error

    def get_json(self, path):
        if self.error is not None:
            raise self.error
        if path == "/props":
            return self.props
        if path == "/slots":
            return self.slots
        raise AssertionError(path)

    def post_json(self, path, payload):
        raise AssertionError("compat probe must not execute model work")


class LlamaCppCompatibilityTest(unittest.TestCase):
    def test_valid_slot_surface_is_mechanically_compatible(self):
        report = probe_llama_cpp_server(
            transport=FakeTransport(
                props={"build_info": "b999-465e49b9", "total_slots": 2},
                slots=[{"id": 0}, {"id": 1}],
            )
        )
        self.assertTrue(report.reachable)
        self.assertTrue(report.compatible)
        self.assertEqual(report.slot_count, 2)
        self.assertEqual(report.total_slots, 2)
        self.assertTrue(report.reference_source_match)
        self.assertTrue(report.reference_qualified)
        self.assertFalse(report.namespace_isolation)
        self.assertTrue(report.single_domain_only)
        self.assertFalse(report.runtime_qualified)
        self.assertEqual(report.integration_level, "partial")
        self.assertIn("prefix_lookup", report.declared_capabilities)

    def test_missing_or_malformed_slots_fail_closed(self):
        offline = probe_llama_cpp_server(
            transport=FakeTransport(error=OSError("offline"))
        )
        self.assertFalse(offline.compatible)
        self.assertFalse(offline.reachable)
        malformed = probe_llama_cpp_server(
            transport=FakeTransport(props=[], slots=[{"id": 0}])
        )
        self.assertFalse(malformed.compatible)
        invalid_ids = probe_llama_cpp_server(
            transport=FakeTransport(
                props={"build_info": "b999-465e49b9"},
                slots=[{"id": "zero"}],
            )
        )
        self.assertFalse(invalid_ids.compatible)

    def test_different_commit_is_fail_closed_and_not_reference_qualified(self):
        report = probe_llama_cpp_server(
            transport=FakeTransport(
                props={"build_info": "b10000-deadbee", "total_slots": 1},
                slots=[{"id": 0}],
            )
        )
        self.assertFalse(report.compatible)
        self.assertFalse(report.reference_source_match)
        self.assertFalse(report.reference_qualified)
        self.assertIn("differs", " ".join(report.issues))

    def test_total_slots_must_match_slot_surface(self):
        report = probe_llama_cpp_server(
            transport=FakeTransport(
                props={"build_info": "b999-465e49b9", "total_slots": 2},
                slots=[{"id": 0}],
            )
        )
        self.assertFalse(report.compatible)
        self.assertIn("total_slots", " ".join(report.issues))


if __name__ == "__main__":
    unittest.main()
