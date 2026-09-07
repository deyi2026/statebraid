import unittest

from statebraid.backend import (
    BACKEND_CONTRACT_VERSION,
    BackendCapability,
    BackendDescriptor,
    BackendObservationProfile,
    BackendQualificationProfile,
    LookupObservation,
    ObservationMode,
    UnsupportedBackendCapability,
)


def _test_observation_profile():
    return BackendObservationProfile(
        mode=ObservationMode.PASSIVE,
        may_mutate_backend_state=False,
    )


def _test_qualification_profile():
    return BackendQualificationProfile(
        source_revision="synthetic-test",
        observation_path="synthetic lookup",
        cache_mode="synthetic",
        concurrency_profile="serial",
        model_class="synthetic",
        runtime_qualified=False,
    )


class BackendContractTest(unittest.TestCase):
    def test_contract_version_and_partial_capability_levels(self) -> None:
        identity = BackendDescriptor(
            name="identity-only",
            adapter="tests.identity",
            capabilities=frozenset({BackendCapability.NAMESPACE_ISOLATION}),
        )
        self.assertEqual(BACKEND_CONTRACT_VERSION, "0.2")
        self.assertEqual(identity.integration_level, "identity-only")
        self.assertTrue(identity.supports(BackendCapability.NAMESPACE_ISOLATION))
        self.assertFalse(identity.supports(BackendCapability.PREFIX_LOOKUP))
        with self.assertRaises(UnsupportedBackendCapability):
            identity.require(BackendCapability.PREFIX_LOOKUP)

    def test_capability_dependencies_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "prefix_lookup"):
            BackendDescriptor(
                name="bad-hit",
                adapter="tests.bad",
                capabilities=frozenset({BackendCapability.HIT_ATTRIBUTION}),
            )
        with self.assertRaisesRegex(ValueError, "transactional_mutation"):
            BackendDescriptor(
                name="bad-rollback",
                adapter="tests.bad",
                capabilities=frozenset({BackendCapability.ROLLBACK}),
            )

    def test_prefix_lookup_requires_explicit_observation_side_effect_semantics(self) -> None:
        with self.assertRaisesRegex(ValueError, "observation_profile"):
            BackendDescriptor(
                name="ambiguous-lookup",
                adapter="tests.ambiguous",
                capabilities=frozenset({BackendCapability.PREFIX_LOOKUP}),
            )
        descriptor = BackendDescriptor(
            name="passive-may-mutate",
            adapter="tests.passive",
            capabilities=frozenset({BackendCapability.PREFIX_LOOKUP}),
            observation_profile=BackendObservationProfile(
                mode=ObservationMode.PASSIVE,
                may_mutate_backend_state=True,
            ),
        )
        payload = descriptor.to_dict()["observation_profile"]
        self.assertEqual(payload["mode"], "passive")
        self.assertTrue(payload["may_mutate_backend_state"])

    def test_generation_safety_requires_narrow_qualification_profile(self) -> None:
        with self.assertRaisesRegex(ValueError, "qualification_profile"):
            BackendDescriptor(
                name="unqualified-generation",
                adapter="tests.unqualified",
                capabilities=frozenset(
                    {BackendCapability.PREFIX_LOOKUP, BackendCapability.GENERATION_SAFETY}
                ),
                observation_profile=_test_observation_profile(),
            )
        descriptor = BackendDescriptor(
            name="qualified-generation",
            adapter="tests.qualified",
            capabilities=frozenset(
                {BackendCapability.PREFIX_LOOKUP, BackendCapability.GENERATION_SAFETY}
            ),
            observation_profile=_test_observation_profile(),
            qualification_profile=_test_qualification_profile(),
        )
        profile = descriptor.to_dict()["qualification_profile"]
        self.assertEqual(profile["source_revision"], "synthetic-test")
        self.assertFalse(profile["runtime_qualified"])

    def test_lookup_observation_normalizes_exact_prefix_identity(self) -> None:
        payload = object()
        observation = LookupObservation.from_backend_result(
            "namespace", [1, 2, 3, 4], payload, [3, 4]
        )
        self.assertTrue(observation.hit)
        self.assertFalse(observation.exact)
        self.assertEqual(observation.matched_tokens, 2)
        self.assertIsNotNone(observation.matched_key)
        assert observation.matched_key is not None
        self.assertEqual(observation.matched_key.tokens, (1, 2))
        self.assertEqual(observation.remaining, (3, 4))

    def test_lookup_observation_rejects_inconsistent_backend_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "exact prompt suffix"):
            LookupObservation.from_backend_result("n", [1, 2, 3], object(), [9])
        with self.assertRaisesRegex(ValueError, "without a payload"):
            LookupObservation.from_backend_result("n", [1, 2, 3], None, [3])
        with self.assertRaisesRegex(ValueError, "without a matched prefix"):
            LookupObservation.from_backend_result("n", [1, 2, 3], object(), [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
