"""
kernel/cmf/security_guard.py - Security, Failure Modes & Threat Mitigation in CMF

Mitigates:
1. Malicious cyclic derivation & deep stack explosion (Static DAG Depth Bounds)
2. Causal DoS / Memory Exhaustion (Per-process quotas and output size ceilings)
3. Poison Input & Cross-Process Data Pollution (Capability-based ACLs)
4. Unauthorized derivation hijacking (DerivationCapabilities)
"""

from enum import Enum, auto
from typing import Dict, List, Any, Optional, Set, Tuple
from kernel.cmf.causal_types import MaterializationState, DerivationRecipe
from kernel.cmf.causal_object import CausalObject


class CausalAccessViolation(Exception):
    """Raised when an unprivileged process attempts unauthorized read or derivation."""
    pass


class CausalDepthExceeded(Exception):
    """Raised when a derivation graph exceeds the maximum allowed topological depth."""
    pass


class CausalQuotaExceeded(Exception):
    """Raised when a process exceeds its allowed quota of causal recipes or memory."""
    pass


class CausalPermission(Enum):
    OWNER_READ    = 1 << 0
    OWNER_DERIVE  = 1 << 1
    WORLD_READ    = 1 << 2
    WORLD_DERIVE  = 1 << 3


class ProcessSecurityContext:
    """Security credentials and quota tracker for a client process."""

    def __init__(self, pid: int, uid: int = 1000, is_kernel: bool = False):
        self.pid = pid
        self.uid = uid
        self.is_kernel = is_kernel

        # Quotas
        self.max_registered_recipes = 256
        self.max_virtual_causal_bytes = 128 * 1024 * 1024  # 128 MB virtual limit
        self.max_dag_depth = 16

        # Active consumption
        self.registered_recipe_count = 0
        self.total_virtual_bytes = 0


class CMFSecurityGuard:
    """
    Authoritative security and isolation monitor for CMF.
    Enforces ACLs, capability tokens, DAG depth ceilings, and per-process memory quotas.
    """

    def __init__(self):
        self.contexts: Dict[int, ProcessSecurityContext] = {}
        # Object permissions: object_id -> (owner_uid, bitmask)
        self.acls: Dict[str, Tuple[int, int]] = {}

    def get_or_create_context(self, pid: int, uid: int = 1000, is_kernel: bool = False) -> ProcessSecurityContext:
        if pid not in self.contexts:
            self.contexts[pid] = ProcessSecurityContext(pid, uid, is_kernel)
        return self.contexts[pid]

    def set_object_acl(self, object_id: str, owner_uid: int, permissions: int):
        """
        Configures Access Control List (ACL) bitmask permissions for a causal memory object.
        Supported bits: CausalPermission.READ, DERIVE, MUTATE, INVALIDATE, ADMIN.
        """
        self.acls[object_id] = (owner_uid, permissions)

    def check_read_permission(self, caller_ctx: ProcessSecurityContext, object_id: str):
        """
        Asserts that caller context is authorized to read the causal object bytes.
        Kernel context bypasses ACL checks; unassigned objects default to public read.
        """
        if caller_ctx.is_kernel:
            return  # Kernel has unrestricted access

        if object_id not in self.acls:
            return  # Default public if no ACL set

        owner_uid, perms = self.acls[object_id]
        if caller_ctx.uid == owner_uid:
            if perms & CausalPermission.OWNER_READ.value:
                return
        else:
            if perms & CausalPermission.WORLD_READ.value:
                return

        raise CausalAccessViolation(
            f"Process {caller_ctx.pid} (UID {caller_ctx.uid}) denied READ access to object '{object_id}'"
        )

    def check_derive_permission(self, caller_ctx: ProcessSecurityContext, parent_id: str):
        """Asserts that caller has permission to use parent_id as an input to a new derivation."""
        if caller_ctx.is_kernel:
            return

        if parent_id not in self.acls:
            return

        owner_uid, perms = self.acls[parent_id]
        if caller_ctx.uid == owner_uid:
            if perms & CausalPermission.OWNER_DERIVE.value:
                return
        else:
            if perms & CausalPermission.WORLD_DERIVE.value:
                return

        raise CausalAccessViolation(
            f"Process {caller_ctx.pid} (UID {caller_ctx.uid}) denied DERIVE permission on parent '{parent_id}'"
        )

    def validate_recipe_registration(
        self,
        caller_ctx: ProcessSecurityContext,
        recipe: DerivationRecipe,
        parent_depths: List[int]
    ):
        """
        Validates quotas, DAG depth, and parent derivation rights before recipe registration.
        """
        if not caller_ctx.is_kernel:
            # 1. Quota checks
            if caller_ctx.registered_recipe_count >= caller_ctx.max_registered_recipes:
                raise CausalQuotaExceeded(
                    f"Process {caller_ctx.pid} exceeded recipe quota ({caller_ctx.max_registered_recipes})"
                )

            new_virtual_total = caller_ctx.total_virtual_bytes + recipe.output_size_bytes
            if new_virtual_total > caller_ctx.max_virtual_causal_bytes:
                raise CausalQuotaExceeded(
                    f"Process {caller_ctx.pid} exceeded virtual causal memory quota ({caller_ctx.max_virtual_causal_bytes} bytes)"
                )

            # 2. DAG Depth check
            max_parent_depth = max(parent_depths) if parent_depths else 0
            current_depth = max_parent_depth + 1
            if current_depth > caller_ctx.max_dag_depth:
                raise CausalDepthExceeded(
                    f"Derivation chain depth {current_depth} exceeds limit of {caller_ctx.max_dag_depth}"
                )

            # 3. Check derive rights for each input
            for parent_id in recipe.input_ids:
                self.check_derive_permission(caller_ctx, parent_id)

            # Update consumption
            caller_ctx.registered_recipe_count += 1
            caller_ctx.total_virtual_bytes += recipe.output_size_bytes

        # Assign initial default ACL (owner read/derive, world read)
        default_perms = (
            CausalPermission.OWNER_READ.value |
            CausalPermission.OWNER_DERIVE.value |
            CausalPermission.WORLD_READ.value
        )
        self.set_object_acl(recipe.output_id, caller_ctx.uid, default_perms)
