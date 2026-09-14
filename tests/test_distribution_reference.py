import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from statebraid.integrations.llama_cpp_managed import (
    MANAGED_LLAMA_CPP_BASE_SHA,
    MANAGED_LLAMA_CPP_BASE_TREE_SHA,
    MANAGED_LLAMA_CPP_PATCH_SHA256,
    MANAGED_LLAMA_CPP_SOURCE_SHA,
    MANAGED_LLAMA_CPP_SOURCE_TREE_SHA,
    check_managed_patch,
    managed_patch_bytes,
    verify_managed_patch,
    write_managed_patch,
)
from statebraid.integrations.mlx import (
    REFERENCE_MLX_BASE_SHA,
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
            "6d21ce4b065a2e163fa6de76a9936c61aeb5784a",
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

    def test_llama_cpp_managed_patch_digest_and_identity_are_frozen(self):
        data = managed_patch_bytes()
        self.assertTrue(verify_managed_patch())
        self.assertEqual(
            hashlib.sha256(data).hexdigest(), MANAGED_LLAMA_CPP_PATCH_SHA256
        )
        self.assertEqual(
            MANAGED_LLAMA_CPP_BASE_SHA,
            "465e49b9cea78a68b9c244ffb48d0ee24a82873d",
        )
        self.assertEqual(
            MANAGED_LLAMA_CPP_BASE_TREE_SHA,
            "4e34a10914c334511b880e641a75260d0be6ad0e",
        )
        self.assertEqual(
            MANAGED_LLAMA_CPP_SOURCE_SHA,
            "09a4891ddd3e546f29dffd38e1a00ab5a19085f6",
        )
        self.assertEqual(
            MANAGED_LLAMA_CPP_SOURCE_TREE_SHA,
            "4788b62631a8316472c9a272a04235bdb1de39e6",
        )

    def test_llama_cpp_managed_patch_contains_only_expected_paths(self):
        text = managed_patch_bytes().decode("utf-8")
        paths = {
            line.split(" b/", 1)[1]
            for line in text.splitlines()
            if line.startswith("diff --git a/") and " b/" in line
        }
        self.assertEqual(
            paths,
            {
                "common/arg.cpp",
                "common/common.h",
                "tools/server/server-context.cpp",
                "tools/server/server-context.h",
                "tools/server/server-task.h",
                "tools/server/server.cpp",
                "tools/server/tests/unit/test_statebraid_managed_cache.py",
                "tools/server/tests/utils.py",
            },
        )
        for forbidden in (
            "/Users/",
            "BEGIN " + "OPENSSH PRIVATE KEY",  # concat: keep literal out of source
            "BEGIN " + "PRIVATE KEY",
            "api_" + "key=",
            "Authorization: " + "Bearer",
        ):
            self.assertNotIn(forbidden, text)

    def test_llama_cpp_managed_patch_can_be_materialized(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "managed.patch"
            actual = write_managed_patch(target)
            self.assertEqual(actual, target)
            self.assertEqual(target.read_bytes(), managed_patch_bytes())

    def test_llama_cpp_managed_apply_check_requires_exact_clean_base(self):
        ok = Mock(
            returncode=0,
            stdout=(MANAGED_LLAMA_CPP_BASE_SHA + "\n").encode(),
            stderr=b"",
        )
        top = Mock(returncode=0, stdout=b"/tmp/llama.cpp\n", stderr=b"")
        clean = Mock(returncode=0, stdout=b"", stderr=b"")
        apply_ok = Mock(returncode=0, stdout=b"", stderr=b"")
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "statebraid.integrations.llama_cpp_managed.subprocess.run",
                side_effect=[top, ok, clean, apply_ok],
            ) as run:
                self.assertEqual(check_managed_patch(directory), Path(directory).resolve())
                self.assertEqual(run.call_count, 4)
                self.assertEqual(
                    run.call_args_list[-1].args[0][-4:],
                    ["apply", "--check", "--whitespace=nowarn", "-"],
                )
                self.assertEqual(run.call_args_list[-1].kwargs["input"], managed_patch_bytes())

    def test_llama_cpp_managed_apply_check_rejects_wrong_base(self):
        top = Mock(returncode=0, stdout=b"/tmp/llama.cpp\n", stderr=b"")
        wrong = Mock(returncode=0, stdout=b"deadbeef\n", stderr=b"")
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "statebraid.integrations.llama_cpp_managed.subprocess.run",
                side_effect=[top, wrong],
            ):
                with self.assertRaisesRegex(RuntimeError, "requires exact base"):
                    check_managed_patch(directory)

    def test_llama_cpp_managed_apply_check_rejects_digest_drift_first(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "statebraid.integrations.llama_cpp_managed.verify_managed_patch",
                return_value=False,
            ), patch(
                "statebraid.integrations.llama_cpp_managed.subprocess.run"
            ) as run:
                with self.assertRaisesRegex(RuntimeError, "patch digest mismatch"):
                    check_managed_patch(directory)
                run.assert_not_called()

    def test_llama_cpp_managed_apply_check_rejects_dirty_checkout(self):
        top = Mock(returncode=0, stdout=b"/tmp/llama.cpp\n", stderr=b"")
        head = Mock(
            returncode=0,
            stdout=(MANAGED_LLAMA_CPP_BASE_SHA + "\n").encode(),
            stderr=b"",
        )
        dirty = Mock(returncode=0, stdout=b" M tools/server/server.cpp\n", stderr=b"")
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "statebraid.integrations.llama_cpp_managed.subprocess.run",
                side_effect=[top, head, dirty],
            ):
                with self.assertRaisesRegex(RuntimeError, "requires a clean checkout"):
                    check_managed_patch(directory)

    def test_llama_cpp_managed_cli_exports_patch(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "cli-managed.patch"
            self.assertEqual(
                reference_main(["llama-cpp-managed", "--output", str(target)]),
                0,
            )
            self.assertTrue(target.is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
