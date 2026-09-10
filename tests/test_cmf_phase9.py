"""
tests/test_cmf_phase9.py - Verification Suite for CMF Phase 9 (Hardware MMU & Architecture Co-Design)

Tests:
1. Custom RISC-V Sv32 PTE flag bits (PTE_CAUSAL, PTE_REVERSIBLE, PTE_EVAPORABLE)
2. Transparent FAULT_CAUSAL_MISS interception and resolution
3. TLB hit tracking after initial materialization
4. Hardware page evaporation and transparent re-faulting
5. Protection against unmapped segmentation faults
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kernel.cmf import (
    MaterializationState,
    PurityLevel,
    DerivationRecipe,
    CausalObjectStore,
    PTE_V, PTE_R, PTE_W, PTE_CAUSAL, PTE_EVAPORABLE,
    CausalPageTableEntry,
    CausalMMU
)


class TestCMFPhase9(unittest.TestCase):
    """Verifies Phase 9: Hardware & Architecture Co-Design (CXL 3.0 & MMU Extensions)."""

    def test_pte_flag_bits(self):
        """Verifies bitwise separation of standard vs causal PTE flags."""
        pte = CausalPageTableEntry(vpn=10, flags=(PTE_V | PTE_R | PTE_CAUSAL | PTE_EVAPORABLE))

        self.assertTrue(pte.is_valid)
        self.assertTrue(pte.is_causal)
        self.assertTrue(pte.is_evaporable)

        pte.set_valid(False)
        self.assertFalse(pte.is_valid)
        self.assertTrue(pte.is_causal)  # Still causal!

    def test_causal_mmu_transparent_fault_resolution(self):
        """Verifies MMU transparently catches FAULT_CAUSAL_MISS and materializes data."""
        store = CausalObjectStore()
        store.register_root("matrix_root", payload=bytes([1, 2, 3, 4] * 1024))  # 4 KB root

        # Derived matrix page
        recipe = DerivationRecipe(
            "matrix_derived",
            ["matrix_root"],
            lambda inp, p: bytes([(b * 3) & 0xFF for b in inp[0]]),
            "triple",
            output_size_bytes=4096
        )
        store.register_derivation(recipe)

        mmu = CausalMMU(store)

        # Map VPN 500 to causal object (starts V=0)
        pte = mmu.map_causal_page(vpn=500, causal_obj_id="matrix_derived")
        self.assertFalse(pte.is_valid)
        self.assertTrue(pte.is_causal)

        # 1. First translation: V=0 -> FAULT_CAUSAL_MISS -> Resolved!
        data, status1 = mmu.translate_and_read(vpn=500)
        self.assertEqual(status1, "FAULT_CAUSAL_RESOLVED")
        self.assertEqual(mmu.causal_faults_handled, 1)
        self.assertEqual(mmu.tlb_misses, 1)
        self.assertTrue(pte.is_valid)
        self.assertEqual(data[:4], bytes([3, 6, 9, 12]))

        # 2. Second translation: V=1 -> TLB_HIT directly!
        data2, status2 = mmu.translate_and_read(vpn=500)
        self.assertEqual(status2, "TLB_HIT")
        self.assertEqual(mmu.tlb_hits, 1)
        self.assertEqual(mmu.causal_faults_handled, 1)  # No extra fault!
        self.assertEqual(data2, data)

    def test_page_evaporation_and_rematerialization(self):
        """Verifies hardware page evaporation clears physical frame and re-faults cleanly."""
        store = CausalObjectStore()
        store.register_root("in", payload=b"HELLO_CAUSAL_WORLD" * 200)

        recipe = DerivationRecipe(
            "out", ["in"], lambda inp, p: inp[0], "pass", output_size_bytes=3600
        )
        store.register_derivation(recipe)

        mmu = CausalMMU(store)
        mmu.map_causal_page(vpn=100, causal_obj_id="out")

        # Initial read materializes
        mmu.translate_and_read(vpn=100)
        self.assertTrue(mmu.page_table[100].is_valid)

        # Evaporate page under pressure
        success = mmu.evaporate_page(vpn=100)
        self.assertTrue(success)
        self.assertFalse(mmu.page_table[100].is_valid)
        self.assertEqual(mmu.page_table[100].ppn, 0)

        # Next read re-materializes transparently
        data, status = mmu.translate_and_read(vpn=100)
        self.assertEqual(status, "FAULT_CAUSAL_RESOLVED")
        self.assertTrue(mmu.page_table[100].is_valid)
        self.assertEqual(mmu.causal_faults_handled, 2)

    def test_unmapped_page_raises_segfault(self):
        """Verifies accessing unmapped VPN triggers standard segmentation fault."""
        store = CausalObjectStore()
        mmu = CausalMMU(store)

        with self.assertRaises(MemoryError):
            mmu.translate_and_read(vpn=9999)
        self.assertEqual(mmu.standard_page_faults, 1)


if __name__ == "__main__":
    unittest.main()
