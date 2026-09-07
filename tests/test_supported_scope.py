import io
import json
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from statebraid import (
    BACKEND_CONTRACT_VERSION,
    COMPUTE_CONTRACT_VERSION,
    HARNESS_INTEGRATION_CONTRACT_VERSION,
    SUPPORT_SCOPE_VERSION,
)
from statebraid.doctor import main as doctor_main
from statebraid.integrations.mlx import REFERENCE_MLX_BASE_SHA, REFERENCE_PATCH_SHA256
from statebraid.support import (
    REFERENCE_ACTIVATION_DEFAULT,
    REFERENCE_CACHE_SHAPE,
    REFERENCE_DECODE_CONCURRENCY,
    REFERENCE_MODEL,
    REFERENCE_MODEL_LINEAGE,
    REFERENCE_KV_MODE,
    REFERENCE_PROMPT_CONCURRENCY,
    REFERENCE_THINKING_MODE,
    SUPPORT_SCOPE_VERSION as SUPPORT_SCOPE_VERSION_DIRECT,
    UNQUALIFIED_RUNTIME_FEATURES,
    support_scope,
)


ROOT = Path(__file__).resolve().parents[1]


class SupportedScopeContractTest(unittest.TestCase):
    def test_scope_version_is_additive_to_frozen_compute_contract(self) -> None:
        self.assertEqual(COMPUTE_CONTRACT_VERSION, "0.1")
        self.assertEqual(BACKEND_CONTRACT_VERSION, "0.2")
        self.assertEqual(HARNESS_INTEGRATION_CONTRACT_VERSION, "0.1")
        self.assertEqual(SUPPORT_SCOPE_VERSION, "0.1")
        self.assertEqual(SUPPORT_SCOPE_VERSION_DIRECT, SUPPORT_SCOPE_VERSION)
        core = support_scope()["core_contract"]
        self.assertEqual(core["backend_contract_version"], "0.2")
        self.assertEqual(core["harness_integration_contract_version"], "0.1")
        self.assertIn("model execution", core["backend_owns"])
        self.assertIn(
            "exact namespace + token cache identity", core["statebraid_owns"]
        )

    def test_reference_runtime_is_narrow_and_exact(self) -> None:
        scope = support_scope()
        reference = scope["reference_runtime"]
        self.assertEqual(reference["backend"], "mlx")
        self.assertEqual(reference["mlx_base_sha"], REFERENCE_MLX_BASE_SHA)
        self.assertEqual(reference["patch_sha256"], REFERENCE_PATCH_SHA256)
        self.assertEqual(reference["model"], REFERENCE_MODEL)
        self.assertEqual(reference["model_lineage"], "Qwen3.6-derived")
        self.assertEqual(reference["cache_shape"], "hybrid/non-trimmable")
        self.assertEqual(reference["generation_path"], "batch")
        self.assertEqual(reference["thinking_mode"], "model-native")
        self.assertEqual(reference["kv_mode"], "unquantized-kv")
        self.assertEqual(reference["prompt_concurrency"], 1)
        self.assertEqual(reference["decode_concurrency"], 1)
        self.assertFalse(reference["activation_default"])
        self.assertFalse(REFERENCE_ACTIVATION_DEFAULT)
        self.assertEqual(REFERENCE_CACHE_SHAPE, "hybrid/non-trimmable")
        self.assertEqual(REFERENCE_THINKING_MODE, "model-native")
        self.assertEqual(REFERENCE_KV_MODE, "unquantized-kv")
        self.assertEqual(REFERENCE_PROMPT_CONCURRENCY, 1)
        self.assertEqual(REFERENCE_DECODE_CONCURRENCY, 1)

    def test_scope_explicitly_rejects_blanket_family_and_unqualified_modes(self) -> None:
        text = "\n".join(UNQUALIFIED_RUNTIME_FEATURES).casefold()
        for required_boundary in (
            "all qwen",
            "trimmable-kv",
            "quantized-kv",
            "draft-model",
            "non-batch",
            "distributed",
            "concurrency",
            "multi-model",
            "linux/windows",
            "other than the qualified mlx reference",
        ):
            with self.subTest(required_boundary=required_boundary):
                self.assertIn(required_boundary, text)

    def test_scope_doctor_json_matches_package_metadata(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = doctor_main(["scope", "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload, support_scope())

    def test_authoritative_scope_document_matches_machine_metadata(self) -> None:
        doc = (ROOT / "docs" / "SUPPORTED_SCOPE_V0_1.md").read_text(encoding="utf-8")
        for value in (
            REFERENCE_MLX_BASE_SHA,
            REFERENCE_PATCH_SHA256,
            REFERENCE_MODEL,
            REFERENCE_MODEL_LINEAGE,
            REFERENCE_CACHE_SHAPE,
            "prompt concurrency = 1",
            "decode concurrency = 1",
            "default-off",
            "not a blanket Qwen-family support claim",
        ):
            with self.subTest(value=value):
                self.assertIn(value, doc)

    def test_python_floor_stays_declared_without_claiming_a_test_matrix(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        self.assertEqual(project["requires-python"], ">=3.11")
        scope = support_scope()
        conditional = "\n".join(scope["conditional_support"]).casefold()
        self.assertIn("per-minor ci matrix", conditional)


if __name__ == "__main__":
    unittest.main()
