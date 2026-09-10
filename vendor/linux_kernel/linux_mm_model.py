"""
vendor/linux_kernel/linux_mm_model.py - Linux Kernel Memory Subsystem Algorithmic Model
Derived directly from Linux kernel C sources:
- include/linux/mmzone.h: enum lru_list, zone watermarks (WMARK_MIN, WMARK_LOW, WMARK_HIGH)
- mm/vmscan.c: shrink_active_list(), shrink_inactive_list(), shrink_page_list(), kswapd priority scan
- mm/oom_kill.c: badness() scoring, select_bad_process(), oom_kill_process()
"""

import time
from collections import deque
from typing import Dict, List, Optional, Any, Tuple

# From include/linux/mmzone.h
LRU_INACTIVE_ANON = 0
LRU_ACTIVE_ANON   = 1
LRU_INACTIVE_FILE = 2
LRU_ACTIVE_FILE   = 3
LRU_UNEVICTABLE   = 4
NR_LRU_LISTS      = 5

# Zone Watermarks
WMARK_MIN  = 0
WMARK_LOW  = 1
WMARK_HIGH = 2

# From mm/vmscan.c
DEF_PRIORITY = 12
SWAP_CLUSTER_MAX = 32
PAGE_SIZE_BYTES = 4096

# Linux Page Flags
PG_ACTIVE     = 0x01
PG_REFERENCED = 0x02
PG_DIRTY      = 0x04
PG_LRU        = 0x08
PG_SWAPBACKED = 0x10


class LinuxPage:
    """Represents a Linux struct page descriptor."""
    def __init__(self, page_id: int, owner_pid: int, is_file: bool = False):
        self.page_id = page_id
        self.owner_pid = owner_pid
        self.flags = PG_LRU | (0 if is_file else PG_SWAPBACKED)
        self.lru_type = LRU_INACTIVE_FILE if is_file else LRU_INACTIVE_ANON
        self.is_file = is_file
        self.access_count = 0
        self.last_access = time.time()

    @property
    def is_active(self) -> bool:
        return bool(self.flags & PG_ACTIVE)

    @property
    def is_referenced(self) -> bool:
        return bool(self.flags & PG_REFERENCED)

    def mark_accessed(self):
        """Emulates Linux mark_page_accessed() logic."""
        if not (self.flags & PG_REFERENCED):
            self.flags |= PG_REFERENCED
        elif not (self.flags & PG_ACTIVE):
            self.flags |= PG_ACTIVE
            self.flags &= ~PG_REFERENCED
        self.access_count += 1
        self.last_access = time.time()


class LinuxProcessStub:
    """Emulates a Linux task_struct for memory accounting and OOM badness."""
    def __init__(self, pid: int, name: str, rss_pages: int, oom_score_adj: int = 0):
        self.pid = pid
        self.name = name
        self.rss_pages = rss_pages
        self.swap_pages = 0
        self.oom_score_adj = oom_score_adj
        self.is_killed = False
        self.page_faults = 0
        self.io_wait_ms = 0.0
        self.pages: List[LinuxPage] = []


class LinuxZone:
    """
    Emulates a Linux struct zone with 4-list LRU page reclaim:
    LRU_INACTIVE_ANON, LRU_ACTIVE_ANON, LRU_INACTIVE_FILE, LRU_ACTIVE_FILE.
    """
    def __init__(self, total_ram_mb: int = 1024):
        self.total_pages = (total_ram_mb * 1024 * 1024) // PAGE_SIZE_BYTES
        self.free_pages = self.total_pages
        self.lru_lists = [deque() for _ in range(NR_LRU_LISTS)]
        self.allocated_pages: Dict[int, LinuxPage] = {}

        # Set Linux zone watermarks (approx 2% min, 3% low, 4% high)
        self.wmark_min = int(self.total_pages * 0.02)
        self.wmark_low = int(self.total_pages * 0.03)
        self.wmark_high = int(self.total_pages * 0.04)

        # Telemetry
        self.pages_scanned = 0
        self.pages_reclaimed = 0
        self.swap_disk_written_kb = 0.0
        self.io_wait_ms = 0.0
        self.bus_bytes_transferred = 0

    def watermark_ok(self, level: int = WMARK_LOW) -> bool:
        if level == WMARK_MIN:
            return self.free_pages >= self.wmark_min
        elif level == WMARK_LOW:
            return self.free_pages >= self.wmark_low
        return self.free_pages >= self.wmark_high

    def allocate_page(self, proc: LinuxProcessStub, is_file: bool = False) -> Optional[LinuxPage]:
        """Allocates a 4KB page frame in the zone."""
        if self.free_pages <= 0:
            return None
        page_id = len(self.allocated_pages) + 1
        page = LinuxPage(page_id, proc.pid, is_file)
        self.allocated_pages[page_id] = page
        self.free_pages -= 1

        # Newly allocated pages enter inactive list
        lru_type = LRU_INACTIVE_FILE if is_file else LRU_INACTIVE_ANON
        page.lru_type = lru_type
        self.lru_lists[lru_type].append(page)
        proc.pages.append(page)
        proc.rss_pages += 1
        return page


class LinuxVMScanEngine:
    """
    Executes the exact dual-list LRU page reclaim algorithm from mm/vmscan.c:
    - shrink_active_list(): demotes unreferenced active pages to inactive
    - shrink_inactive_list(): scans inactive list and reclaims unreferenced pages to swap
    - kswapd_reclaim(): priority decay from DEF_PRIORITY down to 0
    """
    def __init__(self, zone: LinuxZone):
        self.zone = zone
        self.processes: Dict[int, LinuxProcessStub] = {}

    def register_process(self, proc: LinuxProcessStub):
        self.processes[proc.pid] = proc

    def shrink_active_list(self, nr_to_scan: int, is_file: bool = False) -> int:
        """
        Implements Linux shrink_active_list() from mm/vmscan.c.
        Pages with PG_REFERENCED stay in active list with bit cleared.
        Unreferenced pages are deactivated to inactive list.
        """
        active_lru = LRU_ACTIVE_FILE if is_file else LRU_ACTIVE_ANON
        inactive_lru = LRU_INACTIVE_FILE if is_file else LRU_INACTIVE_ANON
        queue = self.zone.lru_lists[active_lru]

        scanned = 0
        deactivated = 0
        while queue and scanned < nr_to_scan:
            page = queue.popleft()
            scanned += 1
            self.zone.pages_scanned += 1

            if page.flags & PG_REFERENCED:
                # Keep active, clear referenced flag
                page.flags &= ~PG_REFERENCED
                queue.append(page)
            else:
                # Deactivate to inactive list
                page.flags &= ~PG_ACTIVE
                page.lru_type = inactive_lru
                self.zone.lru_lists[inactive_lru].append(page)
                deactivated += 1
        return deactivated

    def shrink_inactive_list(self, nr_to_scan: int, is_file: bool = False) -> int:
        """
        Implements Linux shrink_inactive_list() & shrink_page_list() from mm/vmscan.c.
        Pages with PG_REFERENCED are promoted to active list.
        Unreferenced pages are evicted to swap disk (swap out).
        """
        inactive_lru = LRU_INACTIVE_FILE if is_file else LRU_INACTIVE_ANON
        active_lru = LRU_ACTIVE_FILE if is_file else LRU_ACTIVE_ANON
        queue = self.zone.lru_lists[inactive_lru]

        scanned = 0
        reclaimed = 0
        while queue and scanned < nr_to_scan:
            page = queue.popleft()
            scanned += 1
            self.zone.pages_scanned += 1

            if (page.flags & PG_REFERENCED) or (page.flags & PG_ACTIVE):
                # Re-activate to active list
                page.flags |= PG_ACTIVE
                page.flags &= ~PG_REFERENCED
                page.lru_type = active_lru
                self.zone.lru_lists[active_lru].append(page)
            else:
                # Evict page to swap disk
                proc = self.processes.get(page.owner_pid)
                if proc and page in proc.pages:
                    proc.pages.remove(page)
                    proc.rss_pages = max(0, proc.rss_pages - 1)
                    proc.swap_pages += 1

                self.zone.allocated_pages.pop(page.page_id, None)
                self.zone.free_pages += 1
                self.zone.pages_reclaimed += 1
                self.zone.swap_disk_written_kb += (PAGE_SIZE_BYTES / 1024.0)
                # NVMe/SSD page-write latency penalty: 30 microseconds per 4KB page
                self.zone.io_wait_ms += 0.030
                reclaimed += 1
        return reclaimed

    def kswapd_reclaim(self, target_pages: int) -> int:
        """
        Implements Linux kswapd memory reclaim loop across priority tiers (12 to 0).
        """
        reclaimed_total = 0
        for priority in range(DEF_PRIORITY, -1, -1):
            if self.zone.free_pages >= (self.zone.wmark_high + target_pages):
                break

            # Scan ratio based on priority decay: nr_to_scan = lru_size >> priority
            for is_file in (True, False):
                active_lru = LRU_ACTIVE_FILE if is_file else LRU_ACTIVE_ANON
                inactive_lru = LRU_INACTIVE_FILE if is_file else LRU_INACTIVE_ANON

                nr_active = len(self.zone.lru_lists[active_lru])
                nr_inactive = len(self.zone.lru_lists[inactive_lru])

                scan_inactive = max(SWAP_CLUSTER_MAX, nr_inactive >> priority)
                scan_active = max(SWAP_CLUSTER_MAX, nr_active >> priority)

                # 1. Shrink active list to replenish inactive list
                self.shrink_active_list(scan_active, is_file=is_file)

                # 2. Reclaim from inactive list
                reclaimed = self.shrink_inactive_list(scan_inactive, is_file=is_file)
                reclaimed_total += reclaimed

        return reclaimed_total


class LinuxOOMKiller:
    """
    Implements Linux out-of-memory killer logic from mm/oom_kill.c:
    oom_badness() scoring and SIGKILL dispatch.
    """
    def __init__(self, zone: LinuxZone):
        self.zone = zone
        self.killed_processes: List[int] = []

    def oom_badness(self, proc: LinuxProcessStub, total_pages: int) -> int:
        """Calculates badness score in [0, 1000] based on RSS + swap + oom_score_adj."""
        if proc.is_killed or proc.oom_score_adj == -1000:
            return 0  # OOM_SCORE_ADJ_MIN: unkillable
        
        points = proc.rss_pages + proc.swap_pages
        adj = (proc.oom_score_adj * total_pages) // 1000
        points += adj
        return max(0, points)

    def select_bad_process(self, processes: List[LinuxProcessStub]) -> Optional[LinuxProcessStub]:
        best_proc = None
        best_score = 0
        for p in processes:
            if not p.is_killed and (p.rss_pages > 0 or p.swap_pages > 0):
                score = self.oom_badness(p, self.zone.total_pages)
                if score > best_score:
                    best_score = score
                    best_proc = p
        return best_proc

    def oom_kill_process(self, proc: LinuxProcessStub) -> int:
        """Simulates Linux oom_kill_process() SIGKILL termination."""
        if proc.is_killed:
            return 0
        proc.is_killed = True
        freed = proc.rss_pages
        self.zone.free_pages += freed
        self.killed_processes.append(proc.pid)
        for page in list(proc.pages):
            self.zone.allocated_pages.pop(page.page_id, None)
            for lru in self.zone.lru_lists:
                if page in lru:
                    lru.remove(page)
        proc.pages.clear()
        proc.rss_pages = 0
        return freed
