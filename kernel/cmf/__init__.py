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
    "RematerializationScheduler"
]
