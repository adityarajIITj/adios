#!/usr/bin/env python3
"""
AdiOS Process & Multitasking Subsystem: Process Lifecycle & TCB (process.py)
Implements enterprise-scale Process Control Blocks (TaskControlBlock),
full process state transitions, parent-child hierarchies, resource accounting,
virtual memory area (VMA) layout, and credential management from first principles.

Zero external dependencies. Pure RV32IM bare-metal process engine.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

import time
from enum import IntEnum
from typing import Dict, List, Optional, Any, Tuple

class ProcessState(IntEnum):
    EMBRYO   = 0  # Process is being created/cloned
    READY    = 1  # Process is ready in run-queue waiting for CPU
    RUNNING  = 2  # Process is actively executing on a hardware core
    SLEEPING = 3  # Process is blocked on I/O, IPC, or timer
    STOPPED  = 4  # Process is paused by SIGSTOP/SIGTSTP
    ZOMBIE   = 5  # Process has terminated but parent has not waitpid'd
    DEAD     = 6  # Process descriptor is freed

class PriorityClass(IntEnum):
    REALTIME = 0  # Deterministic real-time tasks (Audio synth, Framebuffer raster)
    HIGH     = 1  # Interactive UI, Window Manager, Shell
    NORMAL   = 2  # Standard userland computing tasks
    IDLE     = 3  # Background housekeeping, entropy harvesting, memory compaction

# POSIX waitpid options
WNOHANG    = 0x00000001
WUNTRACED  = 0x00000002
WCONTINUED = 0x00000008

# POSIX fcntl commands
F_DUPFD  = 0
F_GETFD  = 1
F_SETFD  = 2
F_GETFL  = 3
F_SETFL  = 4
FD_CLOEXEC = 1

# Open flags
O_RDONLY   = 0x0000
O_WRONLY   = 0x0001
O_RDWR     = 0x0002
O_APPEND   = 0x0008
O_NONBLOCK = 0x0004
O_CREAT    = 0x0200

# Status helper functions
def WIFEXITED(status: int) -> bool:
    return (status & 0x7F) == 0

def WEXITSTATUS(status: int) -> int:
    return (status >> 8) & 0xFF

def WIFSIGNALED(status: int) -> bool:
    return ((status & 0x7F) != 0) and ((status & 0x7F) != 0x7F)

def WTERMSIG(status: int) -> int:
    return status & 0x7F

def WIFSTOPPED(status: int) -> bool:
    return (status & 0xFF) == 0x7F

def WSTOPSIG(status: int) -> int:
    return (status >> 8) & 0xFF

class CPUContext:
    """
    34-register hardware CPU context saved on interrupt or task switch.
    Includes x0-x31, PC, and CSR STATUS.
    """
    def __init__(self, pc: int = 0x80000000, sp: int = 0x82000000):
        self.regs = [0] * 32
        self.regs[2] = sp & 0xFFFFFFFF   # sp (x2)
        self.pc = pc & 0xFFFFFFFF
        self.mstatus = 0x00001800        # Machine status (Ring-0 M-mode)
        self.satp = 0                    # Virtual memory root pointer

    def clone(self) -> 'CPUContext':
        ctx = CPUContext(self.pc, self.regs[2])
        ctx.regs = list(self.regs)
        ctx.mstatus = self.mstatus
        ctx.satp = self.satp
        return ctx

class FileDescriptor:
    """
    Open file/stream descriptor held by a process.
    """
    def __init__(self, fd_num: int, target_type: str, target_ref: Any, flags: int = 0):
        self.fd_num = fd_num
        self.target_type = target_type  # 'FILE', 'PIPE_READ', 'PIPE_WRITE', 'SOCKET', 'CONSOLE'
        self.target_ref = target_ref
        self.flags = flags              # O_RDONLY, O_WRONLY, O_NONBLOCK
        self.offset = 0
        self.cloexec = False

    def clone(self, new_fd: int) -> 'FileDescriptor':
        fd = FileDescriptor(new_fd, self.target_type, self.target_ref, self.flags)
        fd.offset = self.offset
        fd.cloexec = self.cloexec
        return fd

class ResourceLimits:
    """
    POSIX-style resource limits (RLIMIT) for a process.
    """
    def __init__(self):
        self.max_cpu_time = 0xFFFFFFFF      # Microseconds
        self.max_memory_bytes = 64 * 1024 * 1024  # 64 MB RAM maximum
        self.max_open_files = 256
        self.max_child_processes = 64
        self.max_stack_bytes = 8 * 1024 * 1024   # 8 MB stack

class ProcessMetrics:
    """
    Detailed CPU and memory runtime accounting telemetry.
    """
    def __init__(self):
        self.creation_time = time.time()
        self.cpu_time_ticks = 0
        self.user_time_ticks = 0
        self.system_time_ticks = 0
        self.voluntary_switches = 0
        self.involuntary_switches = 0
        self.context_switches = 0
        self.page_faults = 0
        self.io_bytes_read = 0
        self.io_bytes_written = 0

class VirtualMemoryArea:
    """
    Describes a mapped virtual memory region in process address space.
    """
    def __init__(self, start: int, end: int, flags: str = "rwx", name: str = "[anon]"):
        self.start = start & 0xFFFFFFFF
        self.end = end & 0xFFFFFFFF
        self.flags = flags
        self.name = name

    @property
    def size(self) -> int:
        return max(0, self.end - self.start)

    def contains(self, vaddr: int) -> bool:
        return self.start <= (vaddr & 0xFFFFFFFF) < self.end

    def clone(self) -> 'VirtualMemoryArea':
        return VirtualMemoryArea(self.start, self.end, self.flags, self.name)

class TaskControlBlock:
    """
    Enterprise-scale Process Control Block (TaskControlBlock).
    Contains full state, registers, memory maps, credentials, signals,
    open file table, hierarchy links, and telemetry.
    """
    _next_pid = 1

    def __init__(self, name: str = "init", parent_pid: int = 0, priority: PriorityClass = PriorityClass.NORMAL):
        self.pid = TaskControlBlock._next_pid
        TaskControlBlock._next_pid += 1
        self.ppid = parent_pid
        self.name = name
        self.state = ProcessState.EMBRYO
        self.priority = priority
        self.quantum = 10  # Milliseconds / scheduler ticks per time slice
        self.quantum_left = 10

        # POSIX Credentials & Process Groups
        self.pgid = self.pid if parent_pid == 0 else parent_pid
        self.sid = self.pid if parent_pid == 0 else parent_pid
        self.uid = 0  # Root by default
        self.gid = 0
        self.euid = 0
        self.egid = 0

        # Hardware execution context
        self.context = CPUContext()

        # Virtual memory address space (Sv32) & Memory Areas
        self.address_space = None
        self.vmas: List[VirtualMemoryArea] = []
        self.heap_start = 0x10000000
        self.heap_break = 0x10000000
        self.stack_top  = 0x82000000

        # Process Hierarchy Links
        self.parent: Optional['TaskControlBlock'] = None
        self.children: List['TaskControlBlock'] = []
        self.exit_code: int = 0
        self.termination_status: int = 0

        # Open File Descriptor Table (FD 0: stdin, FD 1: stdout, FD 2: stderr)
        self.fd_table: Dict[int, FileDescriptor] = {}
        self._init_default_fds()

        # Signal Subsystem State
        self.signal_pending_mask = 0
        self.signal_blocked_mask = 0
        self.signal_handlers: Dict[int, Any] = {}  # sig_num -> SigAction

        # Resource limits & telemetry metrics
        self.rlimits = ResourceLimits()
        self.metrics = ProcessMetrics()

        # Sleep / Block tracking
        self.sleep_until_tick = 0
        self.wait_channel: Optional[str] = None

    def _init_default_fds(self):
        """Initializes standard I/O file descriptors."""
        self.fd_table[0] = FileDescriptor(0, 'CONSOLE', 'STDIN', flags=O_RDONLY)
        self.fd_table[1] = FileDescriptor(1, 'CONSOLE', 'STDOUT', flags=O_WRONLY)
        self.fd_table[2] = FileDescriptor(2, 'CONSOLE', 'STDERR', flags=O_WRONLY)

    def set_state(self, new_state: ProcessState) -> bool:
        """
        Validates and transitions process lifecycle state machine.
        """
        valid_transitions = {
            ProcessState.EMBRYO:   {ProcessState.READY, ProcessState.DEAD},
            ProcessState.READY:    {ProcessState.RUNNING, ProcessState.STOPPED, ProcessState.ZOMBIE},
            ProcessState.RUNNING:  {ProcessState.READY, ProcessState.SLEEPING, ProcessState.STOPPED, ProcessState.ZOMBIE},
            ProcessState.SLEEPING: {ProcessState.READY, ProcessState.STOPPED, ProcessState.ZOMBIE},
            ProcessState.STOPPED:  {ProcessState.READY, ProcessState.ZOMBIE},
            ProcessState.ZOMBIE:   {ProcessState.DEAD},
            ProcessState.DEAD:     set()
        }
        allowed = valid_transitions.get(self.state, set())
        if new_state in allowed:
            self.state = new_state
            return True
        return False

    def update_accounting(self, ticks: int = 1, is_user: bool = True):
        """Updates CPU execution accounting counters."""
        self.metrics.cpu_time_ticks += ticks
        if is_user:
            self.metrics.user_time_ticks += ticks
        else:
            self.metrics.system_time_ticks += ticks

        self.quantum_left = max(0, self.quantum_left - ticks)

    def allocate_fd(self, target_type: str, target_ref: Any, flags: int = 0) -> int:
        """Allocates lowest available file descriptor integer."""
        for fd in range(self.rlimits.max_open_files):
            if fd not in self.fd_table:
                self.fd_table[fd] = FileDescriptor(fd, target_type, target_ref, flags)
                return fd
        raise IOError("Too many open files (RLIMIT_NOFILE exceeded)")

    def close_fd(self, fd: int):
        """Closes an open file descriptor."""
        if fd in self.fd_table:
            del self.fd_table[fd]

    def dup(self, oldfd: int) -> int:
        """Duplicates oldfd to the lowest unused descriptor."""
        if oldfd not in self.fd_table:
            raise ValueError(f"Bad file descriptor {oldfd}")
        return self.allocate_fd(
            self.fd_table[oldfd].target_type,
            self.fd_table[oldfd].target_ref,
            self.fd_table[oldfd].flags
        )

    def dup2(self, oldfd: int, newfd: int) -> int:
        """Duplicates oldfd to specific newfd, closing newfd if already open."""
        if oldfd not in self.fd_table:
            raise ValueError(f"Bad file descriptor {oldfd}")
        if newfd < 0 or newfd >= self.rlimits.max_open_files:
            raise ValueError(f"Invalid new file descriptor {newfd}")
        if oldfd == newfd:
            return newfd
        if newfd in self.fd_table:
            self.close_fd(newfd)

        cloned = self.fd_table[oldfd].clone(newfd)
        self.fd_table[newfd] = cloned
        return newfd

    def fcntl(self, fd: int, cmd: int, arg: int = 0) -> int:
        """POSIX fcntl implementation for file descriptor flags and manipulation."""
        if fd not in self.fd_table:
            raise ValueError(f"Bad file descriptor {fd}")
        entry = self.fd_table[fd]

        if cmd == F_DUPFD:
            for target in range(arg, self.rlimits.max_open_files):
                if target not in self.fd_table:
                    self.fd_table[target] = entry.clone(target)
                    return target
            raise IOError("EMFILE: Too many open files")
        elif cmd == F_GETFD:
            return 1 if entry.cloexec else 0
        elif cmd == F_SETFD:
            entry.cloexec = bool(arg & FD_CLOEXEC)
            return 0
        elif cmd == F_GETFL:
            return entry.flags
        elif cmd == F_SETFL:
            entry.flags = (entry.flags & ~O_NONBLOCK) | (arg & O_NONBLOCK)
            return 0
        else:
            raise ValueError(f"Unsupported fcntl command {cmd}")

    def adjust_brk(self, new_brk: int) -> int:
        """
        Expands or shrinks program heap break.
        Ensures total memory remains within resource limits.
        """
        new_brk = new_brk & 0xFFFFFFFF
        if new_brk < self.heap_start:
            return self.heap_break

        alloc_bytes = new_brk - self.heap_start
        if alloc_bytes > self.rlimits.max_memory_bytes:
            raise MemoryError("ENOMEM: Out of memory (RLIMIT_DATA exceeded)")

        self.heap_break = new_brk
        return self.heap_break

    def add_vma(self, start: int, end: int, flags: str = "rwx", name: str = "[anon]"):
        """Registers a new virtual memory area for memory mapping."""
        self.vmas.append(VirtualMemoryArea(start, end, flags, name))

    def find_vma(self, vaddr: int) -> Optional[VirtualMemoryArea]:
        """Locates the memory area containing virtual address."""
        for vma in self.vmas:
            if vma.contains(vaddr):
                return vma
        return None

    def fork(self, child_name: Optional[str] = None) -> 'TaskControlBlock':
        """
        Clones this process to create an exact child process.
        Copies CPU context, duplicated file descriptors, signal masks, and allocates new PID.
        """
        child = TaskControlBlock(
            name=child_name or f"{self.name}_child",
            parent_pid=self.pid,
            priority=self.priority
        )
        child.pgid = self.pgid
        child.sid = self.sid
        child.uid = self.uid
        child.gid = self.gid
        child.euid = self.euid
        child.egid = self.egid

        # Copy hardware context
        child.context = self.context.clone()
        child.context.regs[10] = 0  # Child returns 0 from fork() in a0 (x10)

        # Duplicate file descriptors
        child.fd_table.clear()
        for fd_idx, fd_obj in self.fd_table.items():
            child.fd_table[fd_idx] = fd_obj.clone(fd_idx)

        # Clone virtual memory areas
        child.vmas = [vma.clone() for vma in self.vmas]
        child.heap_start = self.heap_start
        child.heap_break = self.heap_break
        child.stack_top = self.stack_top

        # Inherit signal state
        child.signal_blocked_mask = self.signal_blocked_mask
        child.signal_handlers = dict(self.signal_handlers)

        # Establish hierarchy
        child.parent = self
        self.children.append(child)
        child.state = ProcessState.READY
        return child

    def terminate(self, exit_code: int = 0):
        """
        Terminates the process, transitioning it to ZOMBIE state
        and closing all open file descriptors.
        """
        self.exit_code = exit_code
        self.termination_status = (exit_code & 0xFF) << 8
        self.state = ProcessState.ZOMBIE
        self.fd_table.clear()

        # Reparent all orphan children to PID 1 (Init)
        if self.parent:
            for child in self.children:
                child.ppid = 1
                child.parent = None
        self.children.clear()

class ProcessManager:
    """
    Sovereign Process Manager & Process Table.
    Maintains process indexing, process group hierarchy, and waitpid synchronization.
    """
    def __init__(self):
        self.processes: Dict[int, TaskControlBlock] = {}
        self.zombies: Dict[int, TaskControlBlock] = {}

    def register_process(self, proc: TaskControlBlock):
        self.processes[proc.pid] = proc

    def get_process(self, pid: int) -> Optional[TaskControlBlock]:
        return self.processes.get(pid) or self.zombies.get(pid)

    def exit_process(self, proc: TaskControlBlock, exit_code: int):
        """Transitions process to zombie and indexes in zombie table."""
        proc.terminate(exit_code)
        if proc.pid in self.processes:
            del self.processes[proc.pid]
        self.zombies[proc.pid] = proc

    def reap_zombie(self, pid: int) -> Optional[TaskControlBlock]:
        """Reaps a zombie process and removes from memory."""
        proc = self.zombies.pop(pid, None)
        if proc:
            proc.state = ProcessState.DEAD
        return proc

    def waitpid(self, caller: TaskControlBlock, target_pid: int = -1, options: int = 0) -> Tuple[int, int]:
        """
        POSIX waitpid implementation:
        - target_pid == -1: waits for any child
        - target_pid == 0: waits for any child in same process group
        - target_pid > 0: waits for specific child PID
        Returns (reaped_pid, status). If WNOHANG and not ready, returns (0, 0).
        """
        eligible_children: List[TaskControlBlock] = []

        # Find all eligible children from caller or zombie pool
        all_children = list(caller.children)
        for z_proc in self.zombies.values():
            if z_proc.ppid == caller.pid and z_proc not in all_children:
                all_children.append(z_proc)

        for child in all_children:
            if target_pid == -1:
                eligible_children.append(child)
            elif target_pid == 0 and child.pgid == caller.pgid:
                eligible_children.append(child)
            elif target_pid > 0 and child.pid == target_pid:
                eligible_children.append(child)

        if not eligible_children:
            return -1, -1  # ECHILD

        # Check for zombies
        for child in eligible_children:
            if child.state == ProcessState.ZOMBIE:
                reaped_pid = child.pid
                status = child.termination_status or ((child.exit_code & 0xFF) << 8)
                self.reap_zombie(reaped_pid)
                if child in caller.children:
                    caller.children.remove(child)
                return reaped_pid, status

        # If WNOHANG set and no child has exited
        if options & WNOHANG:
            return 0, 0

        # In simulation without blocking sleep, return 0, 0
        return 0, 0

    def dump_process_tree(self) -> List[str]:
        """Produces ASCII hierarchy of all running tasks."""
        tree = []
        for pid, proc in sorted(self.processes.items()):
            tree.append(f"PID {pid:4d} | PPID {proc.ppid:4d} | State: {proc.state.name:8s} | Name: {proc.name}")
        for pid, proc in sorted(self.zombies.items()):
            tree.append(f"PID {pid:4d} | PPID {proc.ppid:4d} | State: ZOMBIE   | Name: {proc.name} (Reapable)")
        return tree

if __name__ == "__main__":
    pm = ProcessManager()
    init_proc = TaskControlBlock("init", parent_pid=0, priority=PriorityClass.REALTIME)
    pm.register_process(init_proc)
    print(f"Created PID {init_proc.pid}: {init_proc.name} in state {init_proc.state.name}")

    child = init_proc.fork("shell")
    pm.register_process(child)
    print(f"Forked PID {child.pid}: {child.name} (Parent: {child.ppid})")
    assert child.ppid == init_proc.pid
    assert len(init_proc.children) == 1

    # Test FD duplication & fcntl
    new_fd = child.dup(1)
    assert new_fd == 3
    assert child.fcntl(new_fd, F_GETFL) == O_WRONLY

    # Terminate child
    pm.exit_process(child, exit_code=42)
    assert child.state == ProcessState.ZOMBIE
    assert child.exit_code == 42

    # Reap via waitpid
    reaped_pid, status = pm.waitpid(init_proc, child.pid)
    assert reaped_pid == child.pid
    assert WIFEXITED(status)
    assert WEXITSTATUS(status) == 42
    print("Process TCB lifecycle, waitpid, and FD manipulation verified.")
