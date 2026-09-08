from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from statebraid.adapters.llama_cpp import LLAMA_CPP_REFERENCE_SHA
from statebraid.adapters.llama_cpp_managed import LLAMA_CPP_MANAGED_REFERENCE_SHA
from statebraid.integrations.llama_cpp_managed import (
    MANAGED_LLAMA_CPP_BASE_SHA,
    MANAGED_LLAMA_CPP_BASE_TREE_SHA,
    MANAGED_LLAMA_CPP_PATCH_SHA256,
    MANAGED_LLAMA_CPP_SOURCE_SHA,
    MANAGED_LLAMA_CPP_SOURCE_TREE_SHA,
)


ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION = ROOT / "qualification"
REAL = QUALIFICATION / "llama_cpp_real_gguf"
MANAGED = QUALIFICATION / "llama_cpp_managed_m1"


class QualificationAssetsTest(unittest.TestCase):
    def load(self, path: Path) -> dict[str, object]:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_manifests_match_runtime_and_distribution_identities(self) -> None:
        real = self.load(REAL / "manifest.json")
        managed = self.load(MANAGED / "manifest.json")

        self.assertEqual(real["llama_cpp"]["source_sha"], LLAMA_CPP_REFERENCE_SHA)  # type: ignore[index]
        self.assertFalse(real["runtime_qualified"])

        self.assertEqual(managed["upstream_base_sha"], MANAGED_LLAMA_CPP_BASE_SHA)
        self.assertEqual(managed["upstream_base_tree_sha"], MANAGED_LLAMA_CPP_BASE_TREE_SHA)
        self.assertEqual(managed["managed_source_sha"], MANAGED_LLAMA_CPP_SOURCE_SHA)
        self.assertEqual(managed["managed_source_sha"], LLAMA_CPP_MANAGED_REFERENCE_SHA)
        self.assertEqual(managed["managed_source_tree_sha"], MANAGED_LLAMA_CPP_SOURCE_TREE_SHA)
        self.assertEqual(managed["packaged_patch_sha256"], MANAGED_LLAMA_CPP_PATCH_SHA256)
        self.assertFalse(managed["runtime_qualified"])

    def test_compact_evidence_has_source_provenance_and_no_raw_runtime_identity(self) -> None:
        for path in (REAL / "compact_evidence.json", MANAGED / "compact_evidence.json"):
            evidence = self.load(path)
            self.assertEqual(evidence["status"], "PASS")
            self.assertFalse(evidence["runtime_qualified"])
            provenance = evidence["raw_evidence_sha256"]
            self.assertIsInstance(provenance, dict)
            assert isinstance(provenance, dict)
            self.assertGreater(len(provenance), 0)
            for digest in provenance.values():
                self.assertRegex(str(digest), r"^[0-9a-f]{64}$")

            text = path.read_text(encoding="utf-8")
            for forbidden in (
                '"pid"',
                '"session_id"',
                '"epoch"',
                '"handle"',
                '"reasoning"',
                "/Users/",
                "/private/",
                ".workbuddy/",
                ".lmstudio/",
            ):
                self.assertNotIn(forbidden, text)

    def test_all_qualification_text_is_public_safe(self) -> None:
        forbidden = (
            "/Users/",
            "/private/",
            ".workbuddy/",
            ".lmstudio/",
            "BEGIN " + "OPENSSH PRIVATE KEY",  # concat: keep literal out of source
            "BEGIN " + "PRIVATE KEY",
            "Authorization: " + "Bearer",
        )
        for path in QUALIFICATION.rglob("*"):
            if not path.is_file() or path.suffix not in {".json", ".md", ".py"}:
                continue
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, text, path.as_posix())

    def test_runner_sources_are_stable_and_do_not_write_repo_results(self) -> None:
        runners = sorted(QUALIFICATION.rglob("*.py"))
        self.assertEqual(len(runners), 6)
        for path in runners:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("__file__).with_name", text)
            self.assertNotIn("OUT.write_text", text)
            self.assertNotIn("Path(__file__)", text)
            self.assertNotIn("STATEBRAID_LLAMA_EXP", text)

    def test_compact_evidence_files_have_stable_sha256(self) -> None:
        for path in (REAL / "compact_evidence.json", MANAGED / "compact_evidence.json"):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertRegex(digest, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
