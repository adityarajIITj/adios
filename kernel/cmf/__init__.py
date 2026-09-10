"""
kernel/cmf - Causal Materialization Framework (CMF)
The authoritative operating system primitive for elastic, causal derivation and recomputation.
"""

from kernel.cmf.causal_types import (
    MaterializationState,
    PurityLevel,
    DerivationRecipe,
    CausalMemoryObject
)
from kernel.cmf.causal_object import (
    CausalObject,
    compute_derivation_hash
)
from kernel.cmf.object_store import CausalObjectStore
from kernel.cmf.derivation_pipeline import (
    DerivationOp,
    OpMap,
    OpFilter,
    OpReduceSum,
    OpGaloisPermute,
    DerivationPipeline,
    DAGExecutionEngine
)
from kernel.cmf.cost_model import (
    CostModelParameters,
    MaterializationBudget,
    RematerializationCostEngine
)
from kernel.cmf.remat_scheduler import (
    MaterializationPolicy,
    RematerializationScheduler
)
from kernel.cmf.fluidram_bridge import FluidRAMCMFBridge
from kernel.cmf.purity_sandbox import (
    PurityViolation,
    CausalIntegrityViolation,
    ResourceBoundExceeded,
    PuritySandbox
)
from kernel.cmf.spatial_distributed import (
    SpatialMemoryTier,
    SpatialCostMatrix,
    DistributedCMFNode
)
from kernel.cmf.hardware_mmu import (
    PTE_V, PTE_R, PTE_W, PTE_X, PTE_U, PTE_G, PTE_A, PTE_D,
    PTE_CAUSAL, PTE_REVERSIBLE, PTE_EVAPORABLE,
    CausalPageTableEntry,
    CausalMMU
)
from kernel.cmf.comparative_engine import (
    ArchitectureParadigm,
    ComparativeArchitectureEngine
)
from kernel.cmf.security_guard import (
    CausalAccessViolation,
    CausalDepthExceeded,
    CausalQuotaExceeded,
    CausalPermission,
    ProcessSecurityContext,
    CMFSecurityGuard
)
from kernel.cmf.unified_kernel import AdiOSUnifiedKernel, FirstImplementationSequence

__all__ = [
    "MaterializationState",
    "PurityLevel",
    "DerivationRecipe",
    "CausalMemoryObject",
    "CausalObject",
    "compute_derivation_hash",
    "CausalObjectStore",
    "DerivationOp",
    "OpMap",
    "OpFilter",
    "OpReduceSum",
    "OpGaloisPermute",
    "DerivationPipeline",
    "DAGExecutionEngine",
    "CostModelParameters",
    "MaterializationBudget",
    "RematerializationCostEngine",
    "MaterializationPolicy",
    "RematerializationScheduler",
    "FluidRAMCMFBridge",
    "PurityViolation",
    "CausalIntegrityViolation",
    "ResourceBoundExceeded",
    "PuritySandbox",
    "SpatialMemoryTier",
    "SpatialCostMatrix",
    "DistributedCMFNode",
    "PTE_V", "PTE_R", "PTE_W", "PTE_X", "PTE_U", "PTE_G", "PTE_A", "PTE_D",
    "PTE_CAUSAL", "PTE_REVERSIBLE", "PTE_EVAPORABLE",
    "CausalPageTableEntry",
    "CausalMMU",
    "ArchitectureParadigm",
    "ComparativeArchitectureEngine",
    "CausalAccessViolation",
    "CausalDepthExceeded",
    "CausalQuotaExceeded",
    "CausalPermission",
    "ProcessSecurityContext",
    "CMFSecurityGuard",
    "AdiOSUnifiedKernel",
    "FirstImplementationSequence"
]
