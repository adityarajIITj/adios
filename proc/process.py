#!/usr/bin/env python3
"""
AdiOS Process & Multitasking Subsystem: Process Lifecycle & TCB (process.py)
Implements enterprise-scale Process Control Blocks (TaskControlBlock),
full process state transitions, parent-child hierarchies, resource accounting,
and credential management from first principles. Zero external dependencies.
"""

import time
from enum import IntEnum
from typing import Dict, List, Optional, Any

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

class ResourceLimits:
    """
    POSIX-style resource limits (RLIMIT) for a process.
    """
    def __init__(self):
        self.max_cpu_time = 0xFFFFFFFF      # Microseconds
        self.max_memory_bytes = 64 * 1024 * 1024  # 64 MB RAM maximum
        self.max_open_files = 256
        self.max_child_processes = 64

class ProcessMetrics:
    """
    Detailed CPU and memory runtime accounting telemetry.
    """
    def __init__(self):
        self.creation_time = time.time()
        self.cpu_time_ticks = 0
        self.user_time_ticks = 0
        self.system_time_ticks = 0
        self.context_switches = 0
        self.page_faults = 0
        self.io_bytes_read = 0
        self.io_bytes_written = 0

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

        # Hardware execution context
        self.context = CPUContext()

        # Virtual memory address space (Sv32)
        self.address_space = None

        # Process Hierarchy Links
        self.parent: Optional['TaskControlBlock'] = None
        self.children: List['TaskControlBlock'] = []
        self.exit_code: int = 0

        # Open File Descriptor Table (FD 0: stdin, FD 1: stdout, FD 2: stderr)
        self.fd_table: Dict[int, FileDescriptor] = {}
        self._init_default_fds()

        # Signal Subsystem State
        self.signal_pending_mask = 0
        self.signal_blocked_mask = 0
        self.signal_handlers: Dict[int, Any] = {} # sig_num -> (handler_addr, flags, mask)

        # Resource limits & telemetry metrics
        self.rlimits = ResourceLimits()
        self.metrics = ProcessMetrics()

        # Sleep / Block tracking
        self.sleep_until_tick = 0
        self.wait_channel: Optional[str] = None

    def _init_default_fds(self):
        """Initializes standard I/O file descriptors."""
        self.fd_table[0] = FileDescriptor(0, 'CONSOLE', 'STDIN', flags=0)
        self.fd_table[1] = FileDescriptor(1, 'CONSOLE', 'STDOUT', flags=1)
        self.fd_table[2] = FileDescriptor(2, 'CONSOLE', 'STDERR', flags=1)

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
        child.context = self.context.clone()
        # Child return value for fork() is 0 (register a0 = x10)
        child.context.regs[10] = 0

        # Duplicate file descriptors
        child.fd_table.clear()
        for fd_idx, fd_obj in self.fd_table.items():
            child.fd_table[fd_idx] = FileDescriptor(fd_idx, fd_obj.target_type, fd_obj.target_ref, fd_obj.flags)

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
        self.state = ProcessState.ZOMBIE
        self.fd_table.clear()

        # Reparent all orphan children to PID 1 (Init)
        if self.parent:
            for child in self.children:
                child.ppid = 1
                child.parent = None
        self.children.clear()

if __name__ == "__main__":
    init_proc = TaskControlBlock("init", parent_pid=0, priority=PriorityClass.REALTIME)
    print(f"Created PID {init_proc.pid}: {init_proc.name} in state {init_proc.state.name}")
    child = init_proc.fork("shell")
    print(f"Forked PID {child.pid}: {child.name} (Parent: {child.ppid})")
    assert child.ppid == init_proc.pid
    assert len(init_proc.children) == 1
    child.terminate(exit_code=42)
    assert child.state == ProcessState.ZOMBIE
    assert child.exit_code == 42
    print("Process TCB lifecycle verified.")
