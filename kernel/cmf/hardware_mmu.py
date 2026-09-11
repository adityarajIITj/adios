"""
kernel/cmf/hardware_mmu.py - Hardware & Architecture Co-Design: CXL 3.0 & MMU Extensions

Implements:
- Hardware Page Table Entry (PTE) flag extensions:
  _PAGE_CAUSAL (Bit 8), _PAGE_REVERSIBLE (Bit 9), _PAGE_EVAPORABLE (Bit 10)
- CausalPageTableEntry: RV32/Sv32 hardware descriptor
- CausalMMU: Hardware MMU emulator intercepting FAULT_CAUSAL_MISS
  and transparently re-materializing bytes without userland interruption
"""

from typing import Dict, List, Any, Optional, Tuple
from kernel.cmf.causal_types import MaterializationState, DerivationRecipe
from kernel.cmf.causal_object import CausalObject
from kernel.cmf.object_store import CausalObjectStore


# Standard RISC-V Sv32 PTE bits (Bits 0-7)
PTE_V = 1 << 0   # Valid
PTE_R = 1 << 1   # Readable
PTE_W = 1 << 2   # Writable
PTE_X = 1 << 3   # Executable
PTE_U = 1 << 4   # User-accessible
PTE_G = 1 << 5   # Global mapping
PTE_A = 1 << 6   # Accessed
PTE_D = 1 << 7   # Dirty

# AdiOS CMF Hardware PTE Extensions (Bits 8-10):
# Co-designed using the RISC-V Privileged Architecture RSW (Reserved for Supervisor Software) bits:
PTE_CAUSAL     = 1 << 8   # Page is causally recomputable via CMF derivation recipe
PTE_REVERSIBLE = 1 << 9   # Page is part of a Chronos Galois-reversible thermodynamic chain
PTE_EVAPORABLE = 1 << 10  # Hardware/kernel may evaporate this physical frame without saving to disk


class CausalPageTableEntry:
    """
    Simulated 32-bit RISC-V Page Table Entry (Sv32) with CMF hardware extensions.
    """

    def __init__(self, vpn: int, ppn: int = 0, flags: int = 0, causal_obj_id: Optional[str] = None):
        self.vpn = vpn
        self.ppn = ppn
        self.flags = flags
        self.causal_obj_id = causal_obj_id

    @property
    def is_valid(self) -> bool:
        return bool(self.flags & PTE_V)

    @property
    def is_causal(self) -> bool:
        return bool(self.flags & PTE_CAUSAL)

    @property
    def is_evaporable(self) -> bool:
        return bool(self.flags & PTE_EVAPORABLE)

    def set_valid(self, valid: bool = True):
        if valid:
            self.flags |= PTE_V
        else:
            self.flags &= ~PTE_V


class CausalMMU:
    """
    Hardware Memory Management Unit (MMU) with CMF fault interception.
    """

    def __init__(self, store: CausalObjectStore):
        self.store = store
        self.page_table: Dict[int, CausalPageTableEntry] = {}  # VPN -> PTE
        self.physical_frames: Dict[int, bytes] = {}           # PPN -> 4KB frame
        self.next_ppn = 1000

        # Telemetry
        self.tlb_hits = 0
        self.tlb_misses = 0
        self.causal_faults_handled = 0
        self.standard_page_faults = 0

    def map_causal_page(self, vpn: int, causal_obj_id: str, readable: bool = True, writable: bool = False) -> CausalPageTableEntry:
        """
        Maps a virtual page to a CMF CausalObject.
        Initially marked non-valid (V=0) and causal (CAUSAL=1).
        Physical frame is NOT allocated until accessed!
        """
        flags = PTE_CAUSAL | PTE_EVAPORABLE
        if readable:
            flags |= PTE_R
        if writable:
            flags |= PTE_W

        pte = CausalPageTableEntry(
            vpn=vpn,
            ppn=0,
            flags=flags,
            causal_obj_id=causal_obj_id
        )
        self.page_table[vpn] = pte
        return pte

    def translate_and_read(self, vpn: int) -> Tuple[bytes, str]:
        """
        Translates VPN to physical memory.
        If V=0 and CAUSAL=1, triggers FAULT_CAUSAL_MISS, re-materializes, sets V=1,
        and returns the data seamlessly with zero disk I/O.
        """
        if vpn not in self.page_table:
            self.standard_page_faults += 1
            raise MemoryError(f"Segmentation fault: unmapped VPN {vpn}")

        pte = self.page_table[vpn]

        if pte.is_valid:
            self.tlb_hits += 1
            frame = self.physical_frames.get(pte.ppn, b"\x00" * 4096)
            return frame, "TLB_HIT"

        # V == 0: Page Fault!
        self.tlb_misses += 1

        if pte.is_causal and pte.causal_obj_id:
            # FAULT_CAUSAL_MISS: Transparent hardware re-materialization!
            self.causal_faults_handled += 1
            obj = self.store.get(pte.causal_obj_id)
            if not obj:
                raise KeyError(f"Causal object '{pte.causal_obj_id}' not found.")

            # Re-materialize bytes
            data = self.store.materialize(pte.causal_obj_id)

            # Assign physical frame
            ppn = self.next_ppn
            self.next_ppn += 1
            self.physical_frames[ppn] = data[:4096]

            # Update PTE
            pte.ppn = ppn
            pte.set_valid(True)
            pte.flags |= PTE_A

            return self.physical_frames[ppn], "FAULT_CAUSAL_RESOLVED"

        self.standard_page_faults += 1
        raise MemoryError(f"Standard page fault: non-causal unmapped page at VPN {vpn}")

    def handle_causal_fault(self, vpn: int) -> bool:
        """Convenience trap handler returning True if causal fault was successfully resolved."""
        try:
            _, status = self.translate_and_read(vpn)
            return status in ("FAULT_CAUSAL_RESOLVED", "TLB_HIT")
        except Exception:
            return False

    def evaporate_page(self, vpn: int) -> bool:
        """
        Hardware/OS clears the physical frame of an evaporable page.
        Sets V=0, frees physical frame, but retains PTE_CAUSAL.
        """
        if vpn not in self.page_table:
            return False

        pte = self.page_table[vpn]
        if not pte.is_evaporable or not pte.is_valid:
            return False

        # Release physical frame
        self.physical_frames.pop(pte.ppn, None)
        pte.ppn = 0
        pte.set_valid(False)

        # Evaporate in CMF store if mapped
        if pte.causal_obj_id:
            self.store.evaporate_object(pte.causal_obj_id)

        return True
