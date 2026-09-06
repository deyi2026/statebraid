import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProductBoundaryContractTest(unittest.TestCase):
    def test_package_description_is_compute_only(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        self.assertEqual(
            project["description"],
            "Agent-aware compute-continuity runtime for long-running local agents",
        )

    def test_authoritative_docs_reject_old_multi_brain_product_claims(self) -> None:
        paths = (
            ROOT / "README.md",
            ROOT / "docs" / "PRODUCT_BOUNDARY.md",
            ROOT / "docs" / "ARCHITECTURE.md",
            ROOT / "docs" / "ROADMAP.md",
            ROOT / "SECURITY.md",
        )
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths).casefold()
        for old_claim in (
            "compute and reasoning continuity",
            "preserves both compute continuity and task-state continuity",
            "the three v0.1 capabilities",
            "selected-evidence context continuity",
            "interrupted-generation continuity",
            "continuity projection",
        ):
            with self.subTest(old_claim=old_claim):
                self.assertNotIn(old_claim, text)

    def test_product_boundary_assigns_agent_state_to_harness(self) -> None:
        text = (ROOT / "docs" / "PRODUCT_BOUNDARY.md").read_text(encoding="utf-8")
        self.assertIn("## What StateBraid owns", text)
        self.assertIn("## What the agent harness owns", text)
        for responsibility in (
            "selected raw evidence",
            "provider-interruption",
            "Goal/handoff",
            "SubAgent",
            "ExecutionWorkspace",
        ):
            with self.subTest(responsibility=responsibility):
                self.assertIn(responsibility, text)

    def test_compute_contract_remains_the_statebraid_runtime_boundary(self) -> None:
        text = (ROOT / "docs" / "PRODUCT_BOUNDARY.md").read_text(encoding="utf-8")
        for compute_term in (
            "Exact compute identity",
            "Stable and active compute continuity",
            "Bounded KV/prompt-cache residency",
            "Transactional cache mutation",
            "Generation-safe reuse",
            "Factual compute telemetry",
        ):
            with self.subTest(compute_term=compute_term):
                self.assertIn(compute_term, text)


if __name__ == "__main__":
    unittest.main()
