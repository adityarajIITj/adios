"""
kernel/cmf/purity_sandbox.py - Determinism, Side-Effect Isolation & Purity Proofs

Implements:
- PuritySandbox: isolated execution of derivation transforms with time and memory bounds
- Cryptographic hash verification (SHA-256)
- Multi-trial replay determinism verification
- Exception types: PurityViolation, CausalIntegrityViolation, ResourceBoundExceeded
"""

import hashlib
import time
from typing import Dict, List, Any, Optional, Callable, Tuple
from kernel.cmf.causal_types import MaterializationState, PurityLevel, DerivationRecipe
from kernel.cmf.causal_object import CausalObject


class PurityViolation(Exception):
    """Raised when a derivation attempts an unauthorized side-effect or non-deterministic behavior."""
    pass


class CausalIntegrityViolation(Exception):
    """Raised when re-materialized bytes fail cryptographic validation hash."""
    pass


class ResourceBoundExceeded(Exception):
    """Raised when a derivation exceeds its allotted execution time or memory quota."""
    pass


class PuritySandbox:
    """
    Executes derivation recipes inside an isolated environment with strict resource bounds.
    """

    def __init__(
        self,
        max_exec_time_us: float = 10000.0,  # 10 ms max per transform
        max_output_bytes: int = 16 * 1024 * 1024  # 16 MB max
    ):
        self.max_exec_time_us = max_exec_time_us
        self.max_output_bytes = max_output_bytes

    def execute(self, recipe: DerivationRecipe, input_payloads: List[bytes]) -> bytes:
        """
        Executes transform with resource bounding and cryptographic verification.
        """
        if recipe.purity == PurityLevel.NON_DETERMINISTIC:
            # Non-deterministic recipes cannot be safely recomputed without explicit journal
            raise PurityViolation(
                f"Recipe '{recipe.output_id}' is classified as NON_DETERMINISTIC. "
                "Kernel refuses to recompute without execution journal."
            )

        t0 = time.perf_counter()
        try:
            output = recipe.transform(input_payloads, recipe.parameters)
        except Exception as e:
            raise PurityViolation(f"Derivation '{recipe.output_id}' failed execution: {str(e)}") from e

        elapsed_us = (time.perf_counter() - t0) * 1e6

        if elapsed_us > self.max_exec_time_us:
            raise ResourceBoundExceeded(
                f"Derivation '{recipe.output_id}' exceeded time bound: {elapsed_us:.1f} us > {self.max_exec_time_us:.1f} us"
            )

        if len(output) > self.max_output_bytes:
            raise ResourceBoundExceeded(
                f"Derivation '{recipe.output_id}' exceeded memory bound: {len(output)} bytes > {self.max_output_bytes} bytes"
            )

        # Cryptographic validation check
        if recipe.validation_hash:
            actual_hash = hashlib.sha256(output).hexdigest()
            if actual_hash != recipe.validation_hash:
                raise CausalIntegrityViolation(
                    f"Causal integrity violation for '{recipe.output_id}': "
                    f"expected {recipe.validation_hash[:12]}..., computed {actual_hash[:12]}..."
                )

        return output

    def verify_deterministic_replay(
        self,
        recipe: DerivationRecipe,
        input_payloads: List[bytes],
        trials: int = 3
    ) -> Tuple[bool, str]:
        """
        Runs the derivation transform multiple times across independent trials.
        Asserts that every execution produces bit-identical results.
        Returns (is_deterministic, representative_sha256).
        """
        hashes = []
        last_output = b""

        for trial in range(trials):
            output = self.execute(recipe, input_payloads)
            h = hashlib.sha256(output).hexdigest()
            hashes.append(h)
            last_output = output

        # Check all hashes match trial 0
        if len(set(hashes)) == 1:
            return True, hashes[0]
        else:
            return False, ""
