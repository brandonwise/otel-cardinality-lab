# Validation

Commands run for the initial release:

```bash
python3 -m pip install -e .
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m unittest tests.test_core -v
PYTHONPATH=src python3 scripts/lint.py
PYTHONPATH=src python3 scripts/typecheck.py
python3 -m compileall -q src tests scripts
python3 -m otel_cardinality_lab analyze examples/otlp-metrics.json --budget examples/budget.json --output /tmp/otel-cardinality-report.json --markdown /tmp/otel-cardinality-report.md
python3 -m pip wheel . -w /tmp/otel-cardinality-lab-wheel
node ../humanizer/src/cli.js score -f README.md --ignore-code
```

GitHub Actions must also pass on the initial `main` push before the release is considered shipped.
