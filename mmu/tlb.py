#!/usr/bin/env python3
"""
AdiOS Virtual Memory Subsystem: Translation Lookaside Buffer (TLB) (tlb.py)
Implements a 64-entry fully associative TLB with LRU replacement policy
and RISC-V sfence.vma instruction support.
"""

from collections import OrderedDict

TLB_CAPACITY = 64

class TLBEntry:
    def __init__(self, vpn: int, ppn: int, flags: int, asid: int = 0, is_megapage: bool = False):
        self.vpn = vpn
        self.ppn = ppn
        self.flags = flags
        self.asid = asid
        self.is_megapage = is_megapage

class TLB:
    """
    High-Performance Translation Lookaside Buffer.
    Accelerates virtual memory translations by caching recent page walks.
    """
    def __init__(self, capacity: int = TLB_CAPACITY):
        self.capacity = capacity
        # Ordered dictionary: (vpn, asid) -> TLBEntry (Maintains LRU order)
        self.entries = OrderedDict()
        self.hits = 0
        self.misses = 0

    def lookup(self, vaddr: int, asid: int = 0) -> TLBEntry:
        """
        Looks up virtual address in the TLB cache.
        Returns TLBEntry if hit, None if miss.
        """
        vpn_standard = vaddr >> 12
        key_standard = (vpn_standard, asid)

        # Check standard 4KB page first
        if key_standard in self.entries:
            self.hits += 1
            # Move to end (most recently used)
            self.entries.move_to_end(key_standard)
            return self.entries[key_standard]

        # Check 4MB megapage
        vpn_megapage = vaddr >> 22
        key_megapage = (vpn_megapage, asid)
        if key_megapage in self.entries:
            entry = self.entries[key_megapage]
            if entry.is_megapage:
                self.hits += 1
                self.entries.move_to_end(key_megapage)
                return entry

        self.misses += 1
        return None

    def insert(self, vaddr: int, paddr: int, flags: int, asid: int = 0, is_megapage: bool = False):
        """Inserts a translated entry into the TLB using LRU eviction."""
        if is_megapage:
            vpn = vaddr >> 22
            ppn = paddr >> 22
        else:
            vpn = vaddr >> 12
            ppn = paddr >> 12

        key = (vpn, asid)
        if key in self.entries:
            self.entries.move_to_end(key)
        else:
            if len(self.entries) >= self.capacity:
                # Evict least recently used (first item)
                self.entries.popitem(last=False)

        self.entries[key] = TLBEntry(vpn, ppn, flags, asid, is_megapage)

    def flush(self, vaddr: int = None, asid: int = None):
        """
        Implements RISC-V sfence.vma instruction behavior.
        - If vaddr and asid are None: Flush entire TLB.
        - If vaddr is provided and asid is None: Flush vaddr across all ASIDs.
        - If asid is provided and vaddr is None: Flush all entries for that ASID.
        - If both provided: Flush specific vaddr for specific ASID.
        """
        if vaddr is None and asid is None:
            self.entries.clear()
            return

        keys_to_remove = []
        target_vpn = (vaddr >> 12) if vaddr is not None else None
        target_mega_vpn = (vaddr >> 22) if vaddr is not None else None

        for (k_vpn, k_asid), entry in self.entries.items():
            match_asid = (asid is None) or (k_asid == asid) or bool(entry.flags & 0x20) # Global mapping
            match_vpn = (vaddr is None) or (k_vpn == target_vpn) or (entry.is_megapage and k_vpn == target_mega_vpn)

            if match_asid and match_vpn:
                keys_to_remove.append((k_vpn, k_asid))

        for k in keys_to_remove:
            del self.entries[k]

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total) if total > 0 else 0.0

if __name__ == "__main__":
    tlb = TLB(capacity=4)
    tlb.insert(0x80000000, 0x80000000, flags=0x07)
    hit = tlb.lookup(0x80000100)
    assert hit is not None
    assert hit.ppn == (0x80000000 >> 12)
    print(f"TLB Hit verified. Hit rate: {tlb.hit_rate * 100:.1f}%")
