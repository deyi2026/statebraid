import unittest
from dataclasses import fields

from statebraid.adapters.llama_cpp import LLAMA_CPP_BACKEND_DESCRIPTOR
from statebraid.adapters.mlx import MLX_BACKEND_DESCRIPTOR
from statebraid.backend import BackendCapability, ObservationMode
from statebraid.integration import (
    FORBIDDEN_SEMANTIC_FIELDS,
    HARNESS_INTEGRATION_CONTRACT_VERSION,
    HarnessComputeFacts,
    HarnessComputeRequest,
    IntegrationContractViolation,
    MechanicalResourceConstraints,
    TrustedOwnership,
    TrustDomainDeriver,
    check_backend_compatibility,
    integration_contract_metadata,
)


class HarnessIntegrationContractTest(unittest.TestCase):
    def test_request_schema_is_mechanical_and_rejects_semantic_extension_fields(self) -> None:
        request = HarnessComputeRequest.from_mapping(
            {
                "backend_identity": "mlx-reference",
                "trust_domain": "tenant-a",
                "token_ids": [1, 2, 3],
                "resource_constraints": {
                    "max_sequences": 4,
                    "max_bytes": 1024,
                    "transient_reserve": 1,
                },
            }
        )
        self.assertEqual(request.token_ids, (1, 2, 3))
        self.assertEqual(request.resource_constraints.max_bytes, 1024)
        for forbidden in FORBIDDEN_SEMANTIC_FIELDS:
            payload = request.to_dict()
            payload[forbidden] = "semantic-smuggling"
            with self.subTest(forbidden=forbidden):
                with self.assertRaises(IntegrationContractViolation):
                    HarnessComputeRequest.from_mapping(payload)

    def test_request_and_fact_dataclasses_have_no_semantic_control_fields(self) -> None:
        field_names = {field.name for field in fields(HarnessComputeRequest)} | {
            field.name for field in fields(HarnessComputeFacts)
        }
        for forbidden in FORBIDDEN_SEMANTIC_FIELDS:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, field_names)

    def test_compute_facts_validate_actual_prefix_and_cache_counts(self) -> None:
        facts = HarnessComputeFacts(
            backend_identity="mlx-reference",
            trust_domain="tenant-a",
            request_token_ids=(10, 11, 12, 13),
            actual_reused_prefix=(10, 11),
            cache_hit_tokens=2,
            admitted=True,
            evicted_entries=1,
            generation_replay_tokens=1,
            resident_sequences=2,
            resident_bytes=4096,
        )
        self.assertEqual(facts.actual_reused_prefix, (10, 11))
        with self.assertRaisesRegex(ValueError, "exact request prefix"):
            HarnessComputeFacts(
                backend_identity="mlx-reference",
                trust_domain="tenant-a",
                request_token_ids=(10, 11, 12),
                actual_reused_prefix=(10, 99),
            )
        with self.assertRaisesRegex(ValueError, "must equal"):
            HarnessComputeFacts(
                backend_identity="mlx-reference",
                trust_domain="tenant-a",
                request_token_ids=(10, 11, 12),
                actual_reused_prefix=(10, 11),
                cache_hit_tokens=1,
            )

    def test_trusted_ownership_derivation_is_opaque_and_not_authentication(self) -> None:
        deriver = TrustDomainDeriver(b"integration-contract-key-32-bytes!!")
        ownership = TrustedOwnership(subject="alice@example.com", issuer="test-idp")
        domain = deriver.derive(ownership)
        self.assertRegex(domain, r"^principal-[0-9a-f]{32}$")
        self.assertNotIn("alice", domain)
        self.assertEqual(
            TrustDomainDeriver().derive(
                TrustedOwnership(
                    subject="local", issuer="local", local_single_user=True
                )
            ),
            "local-default",
        )
        with self.assertRaisesRegex(ValueError, "trusted derivation key"):
            TrustDomainDeriver().derive(ownership)

    def test_backend_compatibility_gate_never_selects_backend(self) -> None:
        mlx = check_backend_compatibility(
            backend_identity="already-selected-mlx",
            descriptor=MLX_BACKEND_DESCRIPTOR,
            required_capabilities=[BackendCapability.NAMESPACE_ISOLATION],
        )
        self.assertTrue(mlx.compatible)
        self.assertEqual(mlx.backend_identity, "already-selected-mlx")
        llama = check_backend_compatibility(
            backend_identity="already-selected-llama",
            descriptor=LLAMA_CPP_BACKEND_DESCRIPTOR,
            required_capabilities=[BackendCapability.NAMESPACE_ISOLATION],
        )
        self.assertFalse(llama.compatible)
        self.assertEqual(
            llama.missing_capabilities, (BackendCapability.NAMESPACE_ISOLATION,)
        )

    def test_backend_observation_modes_make_side_effect_semantics_explicit(self) -> None:
        mlx = MLX_BACKEND_DESCRIPTOR.observation_profile
        llama = LLAMA_CPP_BACKEND_DESCRIPTOR.observation_profile
        self.assertIsNotNone(mlx)
        self.assertIsNotNone(llama)
        assert mlx is not None and llama is not None
        self.assertIs(mlx.mode, ObservationMode.PASSIVE)
        self.assertTrue(mlx.may_mutate_backend_state)
        self.assertIs(llama.mode, ObservationMode.EXECUTION_COUPLED)
        self.assertTrue(llama.may_mutate_backend_state)
        llama_qualification = LLAMA_CPP_BACKEND_DESCRIPTOR.qualification_profile
        mlx_qualification = MLX_BACKEND_DESCRIPTOR.qualification_profile
        self.assertIsNotNone(llama_qualification)
        self.assertIsNotNone(mlx_qualification)
        assert llama_qualification is not None and mlx_qualification is not None
        self.assertFalse(llama_qualification.runtime_qualified)
        self.assertTrue(mlx_qualification.runtime_qualified)

    def test_machine_metadata_freezes_external_backend_selection_and_allowed_shapes(self) -> None:
        metadata = integration_contract_metadata()
        self.assertEqual(HARNESS_INTEGRATION_CONTRACT_VERSION, "0.1")
        self.assertEqual(
            metadata["backend_selection"], "external-harness-or-gateway-owned"
        )
        self.assertNotIn("goal", " ".join(metadata["allowed_inputs"]))
        self.assertIn("goal", metadata["forbidden_semantic_fields"])
        self.assertIn("cache_tag", metadata["forbidden_semantic_fields"])
        self.assertEqual(
            metadata["backend_identity_provenance"],
            "trusted-operator-or-configured-serving-backend",
        )
        self.assertEqual(
            metadata["trust_domain_provenance"],
            "trusted-authentication-or-ownership-boundary",
        )
        self.assertEqual(
            metadata["semantic_provenance_validation"],
            "deployment-owned-not-statebraid-inferred",
        )

    def test_resource_constraints_reject_non_mechanical_extension(self) -> None:
        with self.assertRaises(IntegrationContractViolation):
            MechanicalResourceConstraints.from_mapping(
                {"max_bytes": 1024, "retry_desirability": "high"}
            )


if __name__ == "__main__":
    unittest.main()
