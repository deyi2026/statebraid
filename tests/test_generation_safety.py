import unittest

from statebraid.cache.generation import (
    ensure_generation_safe_exact_hit,
    is_generation_safe_hybrid_checkpoint,
)


class FakeCache:
    def __init__(self, *, trimmable=False, size=3):
        self.trimmable = trimmable
        self.size = size


class GenerationSafetyTest(unittest.TestCase):
    def test_trimmable_exact_hit_replays_last_token(self):
        cache = FakeCache(trimmable=True)
        calls = []

        def trim_one(value):
            value.size -= 1

        def fetch_shorter(tokens):
            calls.append(list(tokens))
            return None, []

        got, rest = ensure_generation_safe_exact_hit(
            cache,
            [],
            [1, 2, 3],
            can_trim=lambda value: value.trimmable,
            trim_one=trim_one,
            fetch_shorter=fetch_shorter,
        )
        self.assertIs(got, cache)
        self.assertEqual(rest, [3])
        self.assertEqual(cache.size, 2)
        self.assertEqual(calls, [])

    def test_nontrimmable_exact_hit_uses_prelast_checkpoint(self):
        cache = FakeCache(trimmable=False)
        prefix = FakeCache(trimmable=False, size=2)
        calls = []

        def fetch_shorter(tokens):
            calls.append(list(tokens))
            return prefix, []

        got, rest = ensure_generation_safe_exact_hit(
            cache,
            [],
            [1, 2, 3],
            can_trim=lambda value: value.trimmable,
            trim_one=lambda value: None,
            fetch_shorter=fetch_shorter,
        )
        self.assertIs(got, prefix)
        self.assertEqual(rest, [3])
        self.assertEqual(calls, [[1, 2]])

    def test_nontrimmable_without_shorter_recomputes(self):
        cache = FakeCache(trimmable=False)
        got, rest = ensure_generation_safe_exact_hit(
            cache,
            [],
            [1, 2, 3],
            can_trim=lambda value: value.trimmable,
            trim_one=lambda value: None,
            fetch_shorter=lambda tokens: (None, list(tokens)),
        )
        self.assertIsNone(got)
        self.assertEqual(rest, [1, 2, 3])

    def test_non_exact_hit_is_unchanged(self):
        cache = FakeCache()
        got, rest = ensure_generation_safe_exact_hit(
            cache,
            [3],
            [1, 2, 3],
            can_trim=lambda value: value.trimmable,
            trim_one=lambda value: None,
            fetch_shorter=lambda tokens: self.fail("must not fetch"),
        )
        self.assertIs(got, cache)
        self.assertEqual(rest, [3])

    def test_hybrid_checkpoint_is_only_n_minus_one(self):
        self.assertTrue(is_generation_safe_hybrid_checkpoint([1, 2, 3], [1, 2, 3, 4]))
        self.assertFalse(is_generation_safe_hybrid_checkpoint([1, 2, 3, 4], [1, 2, 3, 4]))
        self.assertFalse(is_generation_safe_hybrid_checkpoint([1, 2], [1, 2, 3, 4]))


if __name__ == "__main__":
    unittest.main()
