#!/usr/bin/env python3
"""
AdiOS Sovereign Computing Subsystem: The Cosmic Entropy Oracle (oracle.py)
Generates philosophical aphorisms and combinatorial vocabulary streams using
hardware entropy harvested from simulated CPU cycles, timer MMIO, and mouse registers.
"""

import time
import os
import sys

# Secular, Philosophical, Mathematical, Astronomical & Cyber Vocabulary
VOCABULARY = [
    # Cosmic & Astronomical
    "aether", "aphelion", "asteroid", "astral", "aurora", "blackhole", "celestial",
    "chroma", "cluster", "comet", "constellation", "corona", "cosmic", "cosmos",
    "darkmatter", "deepspace", "eclipse", "ecliptic", "equinox", "exoplanet",
    "flare", "galaxy", "graviton", "horizon", "interstellar", "jupiter",
    "kepler", "lightyear", "luminosity", "lunar", "magnetar", "mars", "mercury",
    "meteor", "milkyway", "moon", "nebula", "neptune", "neutron", "nova",
    "orbit", "parallax", "perihelion", "photon", "planet", "plasma", "pluto",
    "pulsar", "quasar", "radiance", "redshift", "saturn", "singularity",
    "solar", "solstice", "spectrograph", "spectrum", "star", "starlight",
    "stellar", "supercluster", "supernova", "telescope", "umbra", "uranus",
    "vacuum", "velocity", "venus", "vortex", "zenith", "zodiac",

    # Mathematical & Physical
    "absolute", "algebra", "algorithm", "amplitude", "asymptote", "axiom",
    "binary", "calculus", "chaos", "cipher", "complex", "constant", "continuum",
    "convergence", "coordinate", "cryptography", "curvature", "cyber", "damping",
    "derivative", "determinant", "differential", "dimension", "discrete",
    "divergence", "eigenvalue", "entropy", "equation", "equilibrium", "euclidean",
    "exponential", "field", "flux", "fractal", "frequency", "function",
    "gaussian", "geometry", "gradient", "graph", "harmonic", "hyperbola",
    "inertial", "infinite", "integral", "invariant", "iteration", "kinetic",
    "lattice", "limit", "linear", "logarithm", "manifold", "matrix", "modulus",
    "momentum", "multiverse", "node", "nonlinear", "oscillation", "parabola",
    "parameter", "phase", "potential", "probability", "quantum", "quaternion",
    "radius", "recursion", "relativity", "resonance", "scalar", "sequence",
    "series", "simulation", "space", "symmetry", "tensor", "topology",
    "trajectory", "transform", "vector", "vertex", "wave", "wavelength",

    # Philosophical & Epistemic
    "actuality", "analogy", "antithesis", "architect", "awareness", "clarity",
    "cognition", "concept", "consciousness", "deduction", "dialectic",
    "empiricism", "enlightenment", "entelechy", "entity", "epiphany",
    "epistemology", "essence", "eternity", "existence", "form", "foundation",
    "heuristic", "hypothesis", "identity", "immutable", "imperative",
    "induction", "inference", "infinity", "insight", "intellect", "intuition",
    "logic", "lucid", "macrocosm", "microcosm", "monad", "necessity",
    "noumenon", "objective", "ontology", "paradigm", "phenomenon", "philosophy",
    "platonic", "postulate", "potential", "pragmatic", "premise", "principle",
    "pure", "rational", "reality", "reason", "reflection", "relation",
    "sovereignty", "substance", "syllogism", "synthesis", "teleology",
    "theory", "thought", "transcendent", "truth", "unity", "universal", "virtue"
]

class HardwareRandomLCG:
    """
    64-bit Linear Congruential Generator utilizing hardware peripheral entropy.
    Formula: seed = (seed * 6364136223846793005 + 1442695040888963407) mod 2^64
    """
    def __init__(self, seed=None):
        if seed is None:
            self.seed = int(time.time() * 1000000) & 0xFFFFFFFFFFFFFFFF
        else:
            self.seed = seed & 0xFFFFFFFFFFFFFFFF

    def harvest_hardware_entropy(self, vm=None):
        """Extracts entropy from simulated CPU cycle count, timer MMIO, and mouse registers."""
        entropy = int(time.time() * 1000000) & 0xFFFFFFFF
        if vm:
            entropy ^= (vm.mcycle & 0xFFFFFFFF)
            entropy ^= (vm.timer_time & 0xFFFFFFFF)
            if vm.display:
                entropy ^= ((vm.display.mouse_x << 16) | vm.display.mouse_y)
        
        self.seed = (self.seed ^ (entropy << 17) ^ (entropy >> 7)) & 0xFFFFFFFFFFFFFFFF
        self.next_u32()

    def next_u32(self):
        """Returns 32-bit unsigned pseudo-random integer."""
        self.seed = (self.seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return (self.seed >> 32) & 0xFFFFFFFF

    def rand_range(self, low, high):
        """Returns random integer in [low, high]."""
        if high <= low:
            return low
        span = (high - low) + 1
        return low + (self.next_u32() % span)

    def choice(self, items):
        """Picks a random element from sequence."""
        if not items:
            return None
        idx = self.next_u32() % len(items)
        return items[idx]

class CosmicOracle:
    """
    The AdiOS Hardware Entropy Oracle Engine.
    Speaks in philosophical and scientific aphorisms using hardware entropy.
    """
    def __init__(self, vm=None):
        self.vm = vm
        self.rng = HardwareRandomLCG()

    def consult_oracle(self, word_count=16):
        """Generates a sequence of entropy-driven scientific and philosophical terms."""
        self.rng.harvest_hardware_entropy(self.vm)
        words = []
        for _ in range(word_count):
            words.append(self.rng.choice(VOCABULARY))
        return " ".join(words)

    def consult_doldoc(self, title="COSMIC ORACLE CONSULTATION"):
        """Returns a formatted DolDoc document containing the oracle utterance."""
        self.rng.harvest_hardware_entropy(self.vm)
        num_lines = self.rng.rand_range(2, 5)
        
        doc = []
        doc.append(f"$CL$$FG,14$$TX,3,1$=== {title} ===$FG,0$\n")
        doc.append(f"$FG,6$Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}$FG,0$\n")
        doc.append(f"$FG,8$Entropy Source: RISC-V MMIO Timer & Cycle Entropy$FG,0$\n\n")
        
        for _ in range(num_lines):
            line_words = [self.rng.choice(VOCABULARY) for _ in range(self.rng.rand_range(5, 9))]
            doc.append(f"$FG,11$> $FG,15${' '.join(line_words)}$FG,0$\n")
            
        doc.append(f"\n$FG,10$$LK,\"Reconsult Oracle\",\"oracle_consult\"$  $LK,\"Synthesize Chiptune\",\"synth_play\"$  $LK,\"Exit\",\"exit\"$$FG,0$\n")
        return "".join(doc)

    def generate_aphorism(self):
        """Generates a philosophical or scientific axiom."""
        self.rng.harvest_hardware_entropy(self.vm)
        templates = [
            "The {0} of {1} governs the {2} through universal {3} in {4}.",
            "Observe the {0}: an invariant {1} across the {2} of {3} and {4}.",
            "Through {0} and {1}, the sovereign {2} converges upon {3} in {4}.",
            "Every {0} reflects the {1} of {2}, generating {3} from pure {4}.",
            "When {0} resonates with {1}, the {2} establishes a {3} of {4}."
        ]
        template = self.rng.choice(templates)
        w = [self.rng.choice(VOCABULARY) for _ in range(5)]
        return template.format(*w)

if __name__ == "__main__":
    oracle = CosmicOracle()
    print("--- Cosmic Oracle Consultation ---")
    print(oracle.consult_oracle(16))
    print("\n--- Philosophical Axiom ---")
    print(oracle.generate_aphorism())
