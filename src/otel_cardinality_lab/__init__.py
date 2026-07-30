"""OpenTelemetry metric cardinality preflight analysis."""

from .core import analyze_payload, load_budget, load_metrics

__all__ = ["analyze_payload", "load_budget", "load_metrics"]

__version__ = "0.1.0"
