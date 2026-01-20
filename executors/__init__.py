"""Workflow executors for fan-out/fan-in pattern."""

from .dispatcher import PRAnalysisDispatcher
from .aggregator import PRAnalysisAggregator

__all__ = [
    "PRAnalysisDispatcher",
    "PRAnalysisAggregator",
]
