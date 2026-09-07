import types
import unittest
from dataclasses import dataclass

from statebraid.compat.mlx import probe_mlx_backend


class MLXCompatibilityProbeTest(unittest.TestCase):
    def test_missing_mlx_is_incompatible(self):
        def importer(_name):
            raise ModuleNotFoundError("mlx_lm")

        report = probe_mlx_backend(importer=importer, version_reader=lambda: None)
        self.assertFalse(report.installed)
        self.assertFalse(report.compatible)
        self.assertIn("not importable", report.issues[0])

    def test_import_time_backend_error_is_fail_closed(self):
        def importer(_name):
            raise AttributeError("simulated incompatible mlx import")

        report = probe_mlx_backend(
            importer=importer, version_reader=lambda: "0.31.1"
        )
        self.assertTrue(report.installed)
        self.assertFalse(report.compatible)
        self.assertIn("AttributeError", report.issues[0])
        self.assertEqual(report.backend_contract_version, "0.2")
        self.assertIn("transactional_mutation", report.declared_capabilities)
        self.assertEqual(report.integration_level, "generation-safe-managed")


    def test_stock_like_backend_without_markers_is_rejected(self):
        class Cache:
            pass

        cache_module = types.SimpleNamespace(LRUPromptCache=Cache)
        server_module = types.SimpleNamespace()

        def importer(name):
            return cache_module if name.endswith("models.cache") else server_module

        report = probe_mlx_backend(importer=importer, version_reader=lambda: "x")
        self.assertFalse(report.compatible)
        self.assertFalse(report.transactional_storage)
        self.assertFalse(report.request_namespace)
        self.assertGreaterEqual(len(report.issues), 4)

    def test_versioned_reference_capabilities_are_accepted(self):
        class Cache:
            def transactional_storage(self):
                return object()

        @dataclass
        class GenerationArguments:
            cache_namespace: object = None

        cache_module = types.SimpleNamespace(
            STATEBRAID_STORAGE_API_VERSION="0.1",
            LRUPromptCache=Cache,
        )
        server_module = types.SimpleNamespace(
            STATEBRAID_SERVER_API_VERSION="0.1",
            GenerationArguments=GenerationArguments,
        )

        def importer(name):
            return cache_module if name.endswith("models.cache") else server_module

        report = probe_mlx_backend(importer=importer, version_reader=lambda: "0.test")
        self.assertTrue(report.installed)
        self.assertTrue(report.compatible)
        self.assertEqual(report.issues, ())
        self.assertEqual(report.to_dict()["server_api_version"], "0.1")

    def test_api_version_mismatch_is_rejected_even_when_methods_exist(self):
        class Cache:
            def transactional_storage(self):
                return object()

        @dataclass
        class GenerationArguments:
            cache_namespace: object = None

        cache_module = types.SimpleNamespace(
            STATEBRAID_STORAGE_API_VERSION="9.9",
            LRUPromptCache=Cache,
        )
        server_module = types.SimpleNamespace(
            STATEBRAID_SERVER_API_VERSION="0.1",
            GenerationArguments=GenerationArguments,
        )

        def importer(name):
            return cache_module if name.endswith("models.cache") else server_module

        report = probe_mlx_backend(importer=importer, version_reader=lambda: "0.test")
        self.assertFalse(report.compatible)
        self.assertIn("must be 0.1", report.issues[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
