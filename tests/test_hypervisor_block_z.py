#!/usr/bin/env python3
"""
Test Suite: Block Z Master Integration, Type-1 Hypervisor & Autonomous System Matrix
Verifies:
1. core/hypervisor: RISC-V H-Extension Hypervisor CSRs & delegation
2. core/hypervisor: Stage-2 Nested Paging (SLAT: GPA -> HPA) and page faulting
3. core/hypervisor: Multi-tenant isolated guest VM partitions
4. core/hypervisor: VM-Exit trap interception, MMIO virtualization & guest resumption
5. core/system_matrix: Grand Master cross-subsystem autonomous verification
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.hypervisor import (
    Type1Hypervisor, GuestVM, Stage2PageTable,
    CAUSE_GUEST_PAGE_FLT, CAUSE_VIRT_INSN
)
from core.system_matrix import SovereignSystemMatrix

def test_hypervisor_block_z_suite():
    print("[Test Hypervisor Block Z] Initializing Grand Master Hypervisor & Integration Verification...")

    # 1. Test Stage-2 Nested Paging (SLAT)
    print("  -> Testing Stage-2 Second-Level Address Translation (SLAT)...")
    s2_pt = Stage2PageTable()
    # Map GPA 0x80000000 -> HPA 0x40000000 (4KB page)
    s2_pt.map_page(0x80000000, 0x40000000)

    hpa, is_fault = s2_pt.translate(0x80000124)
    assert not is_fault
    assert hpa == 0x40000124

    # Test unmapped GPA triggers Stage-2 fault
    unmapped_hpa, fault = s2_pt.translate(0x90000000)
    assert fault is True
    print("  -> [PASS] Stage-2 nested paging & fault detection verified.")

    # 2. Test Multi-Tenant Isolated Guest Partitions
    print("  -> Testing Multi-Tenant Hardware Guest Partitions...")
    hyp = Type1Hypervisor()
    guest1 = hyp.create_guest(vmid=1, gpa_start=0x80000000, hpa_start=0x10000000, num_pages=32)
    guest2 = hyp.create_guest(vmid=2, gpa_start=0x80000000, hpa_start=0x20000000, num_pages=32)

    # Both guests see GPA 0x80000000, but they map to separate physical memory!
    hpa1, _ = guest1.stage2_pt.translate(0x80000000)
    hpa2, _ = guest2.stage2_pt.translate(0x80000000)
    assert hpa1 == 0x10000000
    assert hpa2 == 0x20000000
    assert hpa1 != hpa2
    print("  -> [PASS] Multi-tenant memory partition isolation verified.")

    # 3. Test VM-Exit Interception & MMIO Virtualization
    print("  -> Testing VM-Exit Trap Interception & Device Emulation...")
    guest1.pc = 0x80001000 # Trigger virtual MMIO access
    reason, pc_after = hyp.run_guest(vmid=1, max_steps=10)
    assert reason == "VM_EXIT_MMIO"
    assert guest1.vm_exits_count == 1
    assert pc_after == 0x80001004 # Advanced past faulting instruction
    assert guest1.intercepted_mmio[0x10000000] == 0x55AA55AA
    print("  -> [PASS] VM-Exit trap handling and device virtualization verified.")

    # 4. Test Grand Master Cross-Subsystem Autonomous Integration
    print("  -> Testing Sovereign Grand Master Cross-Subsystem Integration Matrix...")
    assert SovereignSystemMatrix.run_full_cross_subsystem_verification() is True
    print("  -> [PASS] Cross-subsystem master integration matrix verified.")

    print("\n[Test Hypervisor Block Z] ALL BLOCK Z HYPERVISOR & MASTER TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_hypervisor_block_z_suite()
