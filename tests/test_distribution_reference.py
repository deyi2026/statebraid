import hashlib
import tempfile
import unittest
from pathlib import Path

from statebraid.integrations.mlx import (
    REFERENCE_MLX_BASE_SHA,
    REFERENCE_MLX_BASE_TREE_SHA,
    REFERENCE_MLX_COMMIT_SHA,
    REFERENCE_MLX_SOURCE_TREE_SHA,
    REFERENCE_PATCH_SHA256,
    reference_patch_bytes,
    verify_reference_patch,
    write_reference_patch,
)
from statebraid.reference import main as reference_main


class DistributionReferenceTest(unittest.TestCase):
    def test_distribution_docs_freeze_reference_and_rollback_contract(self):
        root = Path(__file__).resolve().parents[1]
        distribution = (root / "docs" / "DISTRIBUTION_BOUNDARY.md").read_text()
        readme = (root / "README.md").read_text()
        for text in (distribution, readme):
            self.assertIn(REFERENCE_MLX_BASE_SHA, text)
            self.assertIn("statebraid-doctor mlx", text)
            self.assertIn("MLX_LM_STATEBRAID", text)
        self.assertIn("statebraid-reference mlx", distribution)
        self.assertIn("unset MLX_LM_STATEBRAID", distribution)
        normalized = " ".join(distribution.split())
        self.assertIn("not an authentication mechanism", normalized)

    def test_reference_patch_digest_and_exact_base_are_frozen(self):
        data = reference_patch_bytes()
        self.assertTrue(verify_reference_patch())
        self.assertEqual(hashlib.sha256(data).hexdigest(), REFERENCE_PATCH_SHA256)
        self.assertEqual(
            REFERENCE_MLX_BASE_SHA,
            "7fb4be44d560e5b74595210f83cb6003a57e52a7",
        )
        self.assertEqual(
            REFERENCE_MLX_BASE_TREE_SHA,
            "a47df2a0f9f3658677721dac2d846cb3db6cab06",
        )
        self.assertEqual(
            REFERENCE_MLX_COMMIT_SHA,
            "404b970d12928d1c1db27317614982623abf0208",
        )
        self.assertEqual(
            REFERENCE_MLX_SOURCE_TREE_SHA,
            "9212fdfe2412aa711dff937ebf34044d9d00ed77",
        )

    def test_reference_patch_contains_only_expected_integration_paths(self):
        text = reference_patch_bytes().decode("utf-8")
        paths = {
            line.split(" b/", 1)[1]
            for line in text.splitlines()
            if line.startswith("diff --git a/") and " b/" in line
        }
        self.assertEqual(
            paths,
            {
                "bench/test_models_endpoint.py",
                "bench/test_server_cache_exact.py",
                "bench/test_server_quiet_disconnect.py",
                "bench/test_statebraid_reference.py",
                "mlx_lm/models/cache.py",
                "mlx_lm/server.py",
            },
        )
        for forbidden in (
            "CognitivePromptCache",
            "MLX_LM_COGNITIVE_CACHE",
            "ORNITH_",
            "start-ornith",
            "/v1/embeddings",
            "cache_tag",
            "/Users/",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("STATEBRAID_REFERENCE_RUNTIME_QUALIFIED = True", text)
        self.assertIn('STATEBRAID_REFERENCE_STATUS = "reference_qualified"', text)

    def test_reference_patch_can_be_materialized(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "reference.patch"
            actual = write_reference_patch(target)
            self.assertEqual(actual, target)
            self.assertEqual(target.read_bytes(), reference_patch_bytes())

    def test_reference_cli_exports_patch(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "cli.patch"
            self.assertEqual(
                reference_main(["mlx", "--output", str(target)]),
                0,
            )
            self.assertTrue(target.is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
