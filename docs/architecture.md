# Architecture Note

`otel-cardinality-lab` is intentionally a preflight tool, not a collector processor.

The v0 path is:

1. Load an OTLP metrics JSON export or a small simple metrics fixture.
2. Normalize resource and data point attributes into metric series identities.
3. Count observed series, per-attribute distinct values, denied attributes, and theoretical series expansion.
4. Compare the result with a JSON budget policy.
5. Emit JSON and Markdown reports for local review or CI.

The first version avoids live vendor APIs and collector mutation. That keeps the safety boundary clear: it reads local telemetry fixtures and writes reports. Remediation advice points to OpenTelemetry views, collector transforms, and cardinality processors, but the tool does not rewrite production collector config.

## Design Decisions

- **JSON first:** OTLP JSON is easy to fixture in a repo and does not require protobuf tooling in v0.
- **Budget policy over vendor pricing:** Vendor cost models change. Series and attribute budgets are stable enough to review in PRs.
- **Observed plus theoretical series:** Tiny test fixtures can hide cross-product growth. Reporting both catches new dimensions before traffic scales.
- **Zero runtime dependencies:** SRE teams can drop it into CI without accepting another dependency tree for a preflight check.

## Boundaries

- The tool estimates metric cardinality from supplied samples. It does not prove production cost.
- It does not read Prometheus TSDB blocks or live collector telemetry yet.
- It does not perform automatic config rewrites.
