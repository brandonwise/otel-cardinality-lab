from __future__ import annotations

import inspect
import sys

from otel_cardinality_lab import analyze_payload, load_budget, load_metrics


def main() -> int:
    functions = [analyze_payload, load_budget, load_metrics]
    missing = []
    for function in functions:
        signature = inspect.signature(function)
        if signature.return_annotation is inspect.Signature.empty:
            missing.append(function.__name__)
    if missing:
        print("missing return annotations: " + ", ".join(missing))
        return 1
    print("type surface ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
