"""Deterministic valuation math for v2.3 COMPUTE.

The MODEL proposes inputs (growth path, WACC, comp set); these functions
do the MATH. Keeping the arithmetic in pure Python — not the model —
keeps the one place a silent error is dangerous reproducible and
unit-testable.
"""

from .comps import comps, comps_result_to_facts
from .dcf import dcf
from .sensitivity import sensitivity, sensitivity_result_to_fact

__all__ = [
    "comps",
    "comps_result_to_facts",
    "dcf",
    "sensitivity",
    "sensitivity_result_to_fact",
]
