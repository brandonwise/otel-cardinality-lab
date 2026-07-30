# Market Signals

Evidence checked on 2026-07-29:

- OpenTelemetry Go release notes published a breaking metric SDK change on 2026-05-27: the Go metric SDK now applies the default 2000 cardinality limit and drops new attribute sets over that limit.
  Source: https://github.com/open-telemetry/opentelemetry-go/releases
- OpenTelemetry docs describe the 2000 default metric cardinality limit and explain that views can override it.
  Source: https://opentelemetry.io/docs/concepts/signals/metrics/
- OpenTelemetry Collector contrib issue #47368, opened 2026-04-03, accepted donation of a Cardinality Guardian processor for preventing metric label explosions.
  Source: https://github.com/open-telemetry/opentelemetry-collector-contrib/issues/47368
- Reddit observability and SRE threads repeatedly tie high-cardinality metrics to Datadog/Prometheus cost and reliability pain.
  Sources:
  - https://www.reddit.com/r/Observability/comments/1od5cln/how_do_you_balance_high_cardinality_data_needs/
  - https://www.reddit.com/r/sre/comments/1ow3ltg/our_observability_costs_are_now_higher_than_our/
  - https://www.reddit.com/r/Observability/comments/1srqb1s/cardinality_guardian_stop_cardinality_explosions/
- Product Hunt shows adoption pressure around lower-cost OpenTelemetry-native observability stacks.
  Sources:
  - https://www.producthunt.com/products/hyperdx
  - https://www.producthunt.com/products/openobserve
  - https://www.producthunt.com/products/signoz/reviews
- Package ecosystem docs for `@opentelemetry/sdk-metrics` and `go.opentelemetry.io/otel/sdk/metric` document the same default cardinality limit.
  Sources:
  - https://www.npmjs.com/package/@opentelemetry/sdk-metrics
  - https://pkg.go.dev/go.opentelemetry.io/otel/sdk/metric

## Disconfirming Evidence

There are real downstream controls already, including Prometheus TSDB analysis, vendor cardinality dashboards, OpenTelemetry views, and the donated Cardinality Guardian collector processor. That weakens any claim that teams need another runtime processor.

The gap here is earlier and smaller: a repo-local fixture check that tells a developer in review, before merge, which new metric dimensions are likely to become costly or get dropped by SDK limits.
