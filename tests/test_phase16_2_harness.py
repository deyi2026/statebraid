import runpy
import unittest
from pathlib import Path
from typing import Any, Callable, cast


class Phase162HarnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        harness = Path(__file__).resolve().parents[1] / "bench" / "phase16_2_lfl_ab.py"
        namespace = runpy.run_path(str(harness), run_name="statebraid_phase162_harness")
        cls.canonical_call = staticmethod(
            cast(Callable[[Any], str], namespace["_canonical_call"])
        )

    def test_json_argument_key_order_is_not_counted_as_a_distinct_call(self) -> None:
        left = {
            "name": "read_file",
            "arguments": '{"path":"a.py","start_line":1}',
        }
        right = {
            "name": "read_file",
            "arguments": '{ "start_line" : 1, "path" : "a.py" }',
        }
        self.assertEqual(self.canonical_call(left), self.canonical_call(right))

    def test_malformed_argument_string_remains_distinguishable(self) -> None:
        left = {"name": "read_file", "arguments": "not-json-a"}
        right = {"name": "read_file", "arguments": "not-json-b"}
        self.assertNotEqual(self.canonical_call(left), self.canonical_call(right))


if __name__ == "__main__":
    unittest.main()
