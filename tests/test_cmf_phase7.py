"""
tests/test_cmf_phase7.py - Verification Suite for CMF Phase 7 (Determinism & Purity Proofs)

Tests:
1. Pure deterministic execution within PuritySandbox
2. Rejection of NON_DETERMINISTIC derivations without journal
3. Memory and execution time bound enforcement
4. Cryptographic validation hash mismatch detection (CausalIntegrityViolation)
5. Multi-trial deterministic replay verification (passing pure vs detecting flaky transforms)
"""

import os
import sys
import unittest
import hashlib
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kernel.cmf import (
    MaterializationState,
    PurityLevel,
    DerivationRecipe,
    CausalObject,
    PurityViolation,
    CausalIntegrityViolation,
    ResourceBoundExceeded,
    PuritySandbox
)


class TestCMFPhase7(unittest.TestCase):
    """Verifies Phase 7: Determinism, Side-Effect Isolation & Purity Proofs."""

    def test_pure_execution(self):
        """Verifies standard pure transform runs cleanly in sandbox."""
        sandbox = PuritySandbox()
        recipe = DerivationRecipe(
            "pure_sq",
            ["in"],
            lambda inp, p: bytes([(b * b) % 256 for b in inp[0]]),
            "square",
            purity=PurityLevel.PURE_DETERMINISTIC
        )
        res = sandbox.execute(recipe, [bytes([2, 3, 4])])
        self.assertEqual(res, bytes([4, 9, 16]))

    def test_non_deterministic_rejection(self):
        """Verifies sandbox refuses to recompute NON_DETERMINISTIC recipes."""
        sandbox = PuritySandbox()
        recipe = DerivationRecipe(
            "nondet_clock",
            ["in"],
            lambda inp, p: bytes([random.randint(0, 255)]),
            "random_byte",
            purity=PurityLevel.NON_DETERMINISTIC
        )
        with self.assertRaises(PurityViolation):
            sandbox.execute(recipe, [b"dummy"])

    def test_resource_memory_bound_exceeded(self):
        """Verifies that exceeding memory quota raises ResourceBoundExceeded."""
        sandbox = PuritySandbox(max_output_bytes=1024)  # 1 KB limit
        recipe = DerivationRecipe(
            "bloated",
            ["in"],
            lambda inp, p: b"A" * 2048,  # Produces 2 KB
            "bloat",
            purity=PurityLevel.PURE_DETERMINISTIC
        )
        with self.assertRaises(ResourceBoundExceeded):
            sandbox.execute(recipe, [b"dummy"])

    def test_causal_integrity_hash_verification(self):
        """Verifies validation hash mismatch raises CausalIntegrityViolation."""
        sandbox = PuritySandbox()
        correct_bytes = b"CORRECT_AUTHENTIC_DATA"
        corrupt_hash = hashlib.sha256(b"SOME_OTHER_DATA").hexdigest()

        recipe = DerivationRecipe(
            "checked_obj",
            ["in"],
            lambda inp, p: correct_bytes,
            "checked",
            purity=PurityLevel.PURE_DETERMINISTIC,
            validation_hash=corrupt_hash
        )

        with self.assertRaises(CausalIntegrityViolation):
            sandbox.execute(recipe, [b"dummy"])

    def test_multi_trial_replay_verification(self):
        """Verifies multi-trial replay detects flaky, non-deterministic functions."""
        sandbox = PuritySandbox()

        # 1. Deterministic function -> passes 3 trials
        recipe_stable = DerivationRecipe(
            "stable",
            ["in"],
            lambda inp, p: bytes([b ^ 0x55 for b in inp[0]]),
            "invert_55"
        )
        is_det, h = sandbox.verify_deterministic_replay(recipe_stable, [b"TEST_INPUT"], trials=3)
        self.assertTrue(is_det)
        self.assertEqual(len(h), 64)

        # 2. Stateful / Flaky function -> fails 3 trials
        counter = {"val": 0}
        def flaky_transform(inputs, params):
            counter["val"] += 1
            return bytes([counter["val"] % 256])

        recipe_flaky = DerivationRecipe(
            "flaky",
            ["in"],
            flaky_transform,
            "flaky"
        )
        is_det_flaky, _ = sandbox.verify_deterministic_replay(recipe_flaky, [b"TEST_INPUT"], trials=3)
        self.assertFalse(is_det_flaky)


if __name__ == "__main__":
    unittest.main()
