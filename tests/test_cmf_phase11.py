"""
tests/test_cmf_phase11.py - Verification Suite for CMF Phase 11 (Security, Failure Modes & Edge Cases)

Tests:
1. Fine-grained Access Control Lists (ACLs) and cross-process derive/read authorization
2. Rejection of unauthorized derivation hijacking (CausalAccessViolation)
3. Maximum DAG topological depth enforcement (CausalDepthExceeded)
4. Per-process virtual memory and recipe count quotas (CausalQuotaExceeded)
5. Kernel context bypass for core OS subsystems
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kernel.cmf import (
    MaterializationState,
    PurityLevel,
    DerivationRecipe,
    CausalObject,
    CausalPermission,
    ProcessSecurityContext,
    CMFSecurityGuard,
    CausalAccessViolation,
    CausalDepthExceeded,
    CausalQuotaExceeded
)


class TestCMFPhase11(unittest.TestCase):
    """Verifies Phase 11: Security, Failure Modes & Threat Mitigation."""

    def test_unauthorized_derive_rejection(self):
        """Verifies process cannot derive from another user's private object."""
        guard = CMFSecurityGuard()

        # Alice (UID 1001) owns private object with OWNER_READ and OWNER_DERIVE only
        alice_ctx = guard.get_or_create_context(pid=10, uid=1001)
        private_recipe = DerivationRecipe("alice_private", [], lambda inp, p: b"SECRET", "gen")
        guard.validate_recipe_registration(alice_ctx, private_recipe, parent_depths=[0])

        # Restrict to Alice only
        guard.set_object_acl(
            "alice_private",
            owner_uid=1001,
            permissions=(CausalPermission.OWNER_READ.value | CausalPermission.OWNER_DERIVE.value)
        )

        # Bob (UID 1002) attempts to derive from Alice's private object
        bob_ctx = guard.get_or_create_context(pid=20, uid=1002)
        bob_recipe = DerivationRecipe("bob_leak", ["alice_private"], lambda inp, p: inp[0], "leak")

        with self.assertRaises(CausalAccessViolation):
            guard.validate_recipe_registration(bob_ctx, bob_recipe, parent_depths=[1])

    def test_unauthorized_read_rejection(self):
        """Verifies process cannot read object without WORLD_READ permission."""
        guard = CMFSecurityGuard()
        alice_ctx = guard.get_or_create_context(pid=10, uid=1001)
        bob_ctx = guard.get_or_create_context(pid=20, uid=1002)

        guard.set_object_acl("secure_vault", owner_uid=1001, permissions=CausalPermission.OWNER_READ.value)

        # Alice can read
        guard.check_read_permission(alice_ctx, "secure_vault")

        # Bob is denied
        with self.assertRaises(CausalAccessViolation):
            guard.check_read_permission(bob_ctx, "secure_vault")

    def test_dag_depth_limit_enforcement(self):
        """Verifies derivation chains deeper than 16 levels are rejected."""
        guard = CMFSecurityGuard()
        ctx = guard.get_or_create_context(pid=50, uid=1000)

        recipe_valid = DerivationRecipe("d15", ["d14"], lambda inp, p: b"X", "p")
        guard.validate_recipe_registration(ctx, recipe_valid, parent_depths=[14])  # Depth 15 <= 16 -> OK

        recipe_deep = DerivationRecipe("d17", ["d16"], lambda inp, p: b"X", "p")
        with self.assertRaises(CausalDepthExceeded):
            guard.validate_recipe_registration(ctx, recipe_deep, parent_depths=[16])  # Depth 17 > 16 -> Error!

    def test_quota_virtual_memory_limit(self):
        """Verifies per-process virtual causal memory ceiling (128 MB)."""
        guard = CMFSecurityGuard()
        ctx = guard.get_or_create_context(pid=60, uid=1000)

        # Register 100 MB recipe -> OK
        recipe_100mb = DerivationRecipe(
            "big_100mb", [], lambda inp, p: b"X", "p", output_size_bytes=100 * 1024 * 1024
        )
        guard.validate_recipe_registration(ctx, recipe_100mb, parent_depths=[0])

        # Attempt to register another 50 MB (100 + 50 = 150 MB > 128 MB limit)
        recipe_50mb = DerivationRecipe(
            "big_50mb", [], lambda inp, p: b"X", "p", output_size_bytes=50 * 1024 * 1024
        )
        with self.assertRaises(CausalQuotaExceeded):
            guard.validate_recipe_registration(ctx, recipe_50mb, parent_depths=[0])

    def test_kernel_context_bypass(self):
        """Verifies kernel contexts bypass quotas and access control."""
        guard = CMFSecurityGuard()
        kernel_ctx = guard.get_or_create_context(pid=0, uid=0, is_kernel=True)

        # Kernel can derive from anything and exceed user quotas
        recipe_kernel = DerivationRecipe(
            "kernel_obj", ["any_parent"], lambda inp, p: b"K", "k", output_size_bytes=500 * 1024 * 1024
        )
        # Even with parent depth 30, kernel passes
        guard.validate_recipe_registration(kernel_ctx, recipe_kernel, parent_depths=[30])
        guard.check_read_permission(kernel_ctx, "any_private_vault")


if __name__ == "__main__":
    unittest.main()
