# otel-cardinality-lab

Preflight OpenTelemetry metric cardinality before a new label ships.

## Problem

OpenTelemetry metric SDKs and observability backends have hard limits and real costs around cardinality. A harmless-looking label like `user.id`, `session.id`, `request.id`, or `k8s.pod.uid` can turn one metric into thousands of time series, raise backend cost, or cause SDKs to drop new attribute sets.

## Intended User

This is for platform, SRE, and backend teams that review instrumentation changes in pull requests. The first version is useful when you can export or hand-write a small OTLP metrics JSON fixture for the metric you are about to add.

## Why Existing Options Fall Short

Collector processors and vendor dashboards help after telemetry is already flowing. Prometheus and hosted observability tools can show the damage, but they usually sit after the code review where the label was introduced.

`otel-cardinality-lab` runs earlier. It checks a local metric fixture against a budget policy and writes a report a reviewer can read.

## Quickstart

```bash
python3 -m pip install -e .
python3 -m otel_cardinality_lab analyze examples/otlp-metrics.json \
  --budget examples/budget.json \
  --output /tmp/otel-cardinality-report.json \
  --markdown /tmp/otel-cardinality-report.md
```

Open the Markdown report:

```bash
sed -n '1,120p' /tmp/otel-cardinality-report.md
```

Use it as a CI gate:

```bash
python3 -m otel_cardinality_lab analyze examples/otlp-metrics.json \
  --budget examples/budget.json \
  --fail-on high
```

## Example Finding

The included fixture flags `http.server.duration` because it includes `user.id` and `session.id`, exceeds the example series budget, and can expand past the budget as more users hit the route.

The report recommends dropping or hashing those dimensions before export and keeping stable labels like `service.name`, `deployment.environment`, `http.route`, and `http.status_code`.

## Budget Policy

Budgets are JSON:

```json
{
  "global": {
    "max_series_per_metric": 2000,
    "warn_series_per_metric": 1000,
    "dangerous_attributes": ["user.id", "session.id", "request.id", "k8s.pod.uid"]
  },
  "metrics": {
    "http.server.duration": {
      "max_series": 100,
      "warn_series": 50,
      "deny_attributes": ["user.id", "session.id"],
      "allow_attributes": ["service.name", "deployment.environment", "http.route", "http.status_code"]
    }
  }
}
```

## Supported Input

The main input is OTLP metrics JSON with `resourceMetrics`, `scopeMetrics`, `metrics`, and metric `dataPoints`.

For tests and small checks, this simpler shape also works:

```json
{
  "metrics": [
    {
      "name": "http.server.duration",
      "points": [
        { "attributes": { "service.name": "checkout", "user.id": "u-1" } }
      ]
    }
  ]
}
```

## Limitations

- This estimates cardinality from supplied samples. It does not prove production spend.
- It does not read Prometheus TSDB blocks or query vendor APIs.
- It does not mutate collector configuration.
- YAML collector config checks are out of scope for v0.

## Roadmap

- Read Prometheus `/api/v1/status/tsdb` snapshots.
- Emit GitHub PR comments with the Markdown report.
- Add optional collector-config checks for transform, filter, and cardinality processors.
- Add policy presets for HTTP, database, messaging, and Kubernetes semantic conventions.
