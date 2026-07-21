"""Repeatable, deterministic evaluation for stock research reports."""

from .models import EvaluationDataset, EvaluationReport
from .runner import load_dataset, run_evaluation

__all__ = [
    "EvaluationDataset",
    "EvaluationReport",
    "load_dataset",
    "run_evaluation",
]
