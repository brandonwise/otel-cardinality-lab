from __future__ import annotations

import fnmatch
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union


DEFAULT_BUDGET: Dict[str, Any] = {
    "global": {
        "max_series_per_metric": 2000,
        "warn_series_per_metric": 1000,
        "max_values_per_attribute": 100,
        "warn_values_per_attribute": 50,
        "dangerous_attributes": [
            "user.id",
            "user_id",
            "session.id",
            "session_id",
            "request.id",
            "request_id",
            "trace_id",
            "span_id",
            "container.id",
            "k8s.pod.uid",
            "*.uuid",
            "*.guid",
        ],
    },
    "metrics": {},
}

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
SEVERITIES = ("low", "medium", "high", "critical")


@dataclass(frozen=True)
class MetricPoint:
    metric: str
    attributes: Mapping[str, str]


@dataclass
class MetricStats:
    name: str
    datapoints: int = 0
    series: Set[Tuple[Tuple[str, str], ...]] = field(default_factory=set)
    values_by_attribute: DefaultDict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def add(self, attributes: Mapping[str, str]) -> None:
        normalized = tuple(sorted((str(k), str(v)) for k, v in attributes.items()))
        self.datapoints += 1
        self.series.add(normalized)
        for key, value in normalized:
            self.values_by_attribute[key].add(value)


def load_metrics(path: Union[str, Path]) -> Mapping[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_budget(path: Optional[Union[str, Path]]) -> Dict[str, Any]:
    budget = _deep_copy(DEFAULT_BUDGET)
    if path is None:
        return budget
    with Path(path).open("r", encoding="utf-8") as handle:
        user_budget = json.load(handle)
    return _merge_budget(budget, user_budget)


def analyze_payload(payload: Mapping[str, Any], budget: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    active_budget = _merge_budget(_deep_copy(DEFAULT_BUDGET), budget or {})
    stats_by_metric: Dict[str, MetricStats] = {}

    for point in iter_metric_points(payload):
        stats = stats_by_metric.setdefault(point.metric, MetricStats(point.metric))
        stats.add(point.attributes)

    metric_reports = [_metric_report(stats, active_budget) for stats in stats_by_metric.values()]
    metric_reports.sort(key=lambda item: (SEVERITY_ORDER[item["severity"]], item["series"]), reverse=True)

    severity_counts = {severity: 0 for severity in SEVERITIES}
    for item in metric_reports:
        severity_counts[item["severity"]] += 1

    highest = "low"
    if metric_reports:
        highest = max(metric_reports, key=lambda item: SEVERITY_ORDER[item["severity"]])["severity"]

    return {
        "tool": "otel-cardinality-lab",
        "schema_version": "0.1",
        "summary": {
            "metrics": len(metric_reports),
            "datapoints": sum(item["datapoints"] for item in metric_reports),
            "highest_severity": highest,
            "severity_counts": severity_counts,
        },
        "metrics": metric_reports,
    }


def iter_metric_points(payload: Mapping[str, Any]) -> Iterable[MetricPoint]:
    if isinstance(payload.get("metrics"), list):
        yield from _iter_simple_metrics(payload["metrics"])
        return

    for resource_metric in payload.get("resourceMetrics", []):
        resource_attrs = _attributes_to_dict(resource_metric.get("resource", {}).get("attributes", []))
        for scope_metric in resource_metric.get("scopeMetrics", []):
            for metric in scope_metric.get("metrics", []):
                name = str(metric.get("name", "unknown.metric"))
                for data_point in _data_points(metric):
                    attrs = dict(resource_attrs)
                    attrs.update(_attributes_to_dict(data_point.get("attributes", [])))
                    yield MetricPoint(metric=name, attributes=attrs)


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# OpenTelemetry Cardinality Report",
        "",
        f"- Metrics analyzed: {summary['metrics']}",
        f"- Data points analyzed: {summary['datapoints']}",
        f"- Highest severity: {summary['highest_severity']}",
        "",
        "## Metrics",
        "",
    ]
    for item in report["metrics"]:
        lines.extend(
            [
                f"### {item['name']}",
                "",
                f"- Severity: {item['severity']}",
                f"- Observed series: {item['series']} / budget {item['series_budget']}",
                f"- Theoretical series from observed attributes: {item['theoretical_series']}",
                f"- Data points: {item['datapoints']}",
            ]
        )
        if item["estimated_sdk_drops"] > 0:
            lines.append(f"- Estimated data points over SDK default limit: {item['estimated_sdk_drops']}")
        if item["problems"]:
            lines.append("- Problems:")
            for problem in item["problems"]:
                lines.append(f"  - {problem}")
        if item["top_attributes"]:
            lines.append("- Top attributes:")
            for attr in item["top_attributes"][:5]:
                lines.append(f"  - {attr['name']}: {attr['distinct_values']} distinct values")
        if item["recommendations"]:
            lines.append("- Recommended next moves:")
            for recommendation in item["recommendations"]:
                lines.append(f"  - {recommendation}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _iter_simple_metrics(metrics: Sequence[Mapping[str, Any]]) -> Iterable[MetricPoint]:
    for metric in metrics:
        name = str(metric.get("name", "unknown.metric"))
        if isinstance(metric.get("points"), list):
            for point in metric["points"]:
                attrs = point.get("attributes", {})
                if isinstance(attrs, Mapping):
                    yield MetricPoint(metric=name, attributes={str(k): str(v) for k, v in attrs.items()})
        else:
            attrs = metric.get("attributes", {})
            if isinstance(attrs, Mapping):
                yield MetricPoint(metric=name, attributes={str(k): str(v) for k, v in attrs.items()})


def _data_points(metric: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for kind in ("gauge", "sum", "histogram", "exponentialHistogram", "summary"):
        body = metric.get(kind)
        if isinstance(body, Mapping):
            for point in body.get("dataPoints", []):
                yield point


def _attributes_to_dict(attributes: Sequence[Mapping[str, Any]]) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for attr in attributes:
        key = attr.get("key")
        if key is None:
            continue
        parsed[str(key)] = _otel_value_to_str(attr.get("value", {}))
    return parsed


def _otel_value_to_str(value: Any) -> str:
    if not isinstance(value, Mapping):
        return str(value)
    for key in ("stringValue", "intValue", "doubleValue", "boolValue", "bytesValue"):
        if key in value:
            return str(value[key])
    if "arrayValue" in value:
        values = value["arrayValue"].get("values", [])
        return "[" + ",".join(_otel_value_to_str(item) for item in values) + "]"
    if "kvlistValue" in value:
        attrs = _attributes_to_dict(value["kvlistValue"].get("values", []))
        return json.dumps(attrs, sort_keys=True)
    return json.dumps(value, sort_keys=True)


def _metric_report(stats: MetricStats, budget: Mapping[str, Any]) -> Dict[str, Any]:
    global_budget = budget.get("global", {})
    metric_budget = budget.get("metrics", {}).get(stats.name, {})
    series_budget = int(
        metric_budget.get("max_series", global_budget.get("max_series_per_metric", 2000))
    )
    warn_series = int(
        metric_budget.get("warn_series", global_budget.get("warn_series_per_metric", series_budget // 2))
    )
    max_values = int(
        metric_budget.get("max_values_per_attribute", global_budget.get("max_values_per_attribute", 100))
    )
    warn_values = int(
        metric_budget.get("warn_values_per_attribute", global_budget.get("warn_values_per_attribute", 50))
    )
    denied = set(metric_budget.get("deny_attributes", []))
    allowed = set(metric_budget.get("allow_attributes", []))
    dangerous_patterns = list(global_budget.get("dangerous_attributes", []))

    attr_reports = [
        {"name": key, "distinct_values": len(values), "sample_values": sorted(values)[:5]}
        for key, values in stats.values_by_attribute.items()
    ]
    attr_reports.sort(key=lambda item: item["distinct_values"], reverse=True)

    theoretical_series = 1
    for values in stats.values_by_attribute.values():
        theoretical_series *= max(1, len(values))

    present_attrs = set(stats.values_by_attribute.keys())
    denied_present = sorted(present_attrs & denied)
    dangerous_present = sorted(
        key for key in present_attrs if any(fnmatch.fnmatch(key, pattern) for pattern in dangerous_patterns)
    )
    unexpected_attrs = sorted(present_attrs - allowed) if allowed else []
    high_value_attrs = [item for item in attr_reports if item["distinct_values"] >= max_values]
    warn_value_attrs = [item for item in attr_reports if item["distinct_values"] >= warn_values]

    problems: List[str] = []
    if len(stats.series) > series_budget:
        problems.append(f"observed series count exceeds budget ({len(stats.series)} > {series_budget})")
    if len(stats.series) >= warn_series:
        problems.append(f"observed series count is near budget ({len(stats.series)} >= {warn_series})")
    if theoretical_series > series_budget:
        problems.append(
            f"observed attribute combinations can expand past budget ({theoretical_series} > {series_budget})"
        )
    if denied_present:
        problems.append("denied attributes are present: " + ", ".join(denied_present))
    if dangerous_present:
        problems.append("high-cardinality attribute patterns are present: " + ", ".join(dangerous_present))
    if unexpected_attrs:
        problems.append("attributes outside allow-list are present: " + ", ".join(unexpected_attrs))
    for attr in high_value_attrs:
        problems.append(f"{attr['name']} has {attr['distinct_values']} distinct values")

    severity = "low"
    if denied_present or len(stats.series) > series_budget:
        severity = "critical"
    elif dangerous_present or theoretical_series > series_budget or high_value_attrs:
        severity = "high"
    elif len(stats.series) >= warn_series or warn_value_attrs or unexpected_attrs:
        severity = "medium"

    recommendations = _recommendations(
        denied_present=denied_present,
        dangerous_present=dangerous_present,
        high_value_attrs=high_value_attrs,
        unexpected_attrs=unexpected_attrs,
        theoretical_series=theoretical_series,
        series_budget=series_budget,
    )

    return {
        "name": stats.name,
        "severity": severity,
        "datapoints": stats.datapoints,
        "series": len(stats.series),
        "series_budget": series_budget,
        "warn_series": warn_series,
        "theoretical_series": theoretical_series,
        "estimated_sdk_drops": max(
            0,
            len(stats.series) - int(global_budget.get("sdk_default_cardinality_limit", 2000)),
        ),
        "problems": problems,
        "top_attributes": attr_reports[:10],
        "recommendations": recommendations,
    }


def _recommendations(
    *,
    denied_present: Sequence[str],
    dangerous_present: Sequence[str],
    high_value_attrs: Sequence[Mapping[str, Any]],
    unexpected_attrs: Sequence[str],
    theoretical_series: int,
    series_budget: int,
) -> List[str]:
    recs: List[str] = []
    risky = list(dict.fromkeys(list(denied_present) + list(dangerous_present)))
    if risky:
        recs.append(
            "Drop or hash "
            + ", ".join(risky)
            + " before export; prefer route templates and stable dimensions."
        )
    if high_value_attrs:
        names = ", ".join(attr["name"] for attr in high_value_attrs[:3])
        recs.append(f"Add metric views or collector transforms to aggregate high-value attributes: {names}.")
    if unexpected_attrs:
        recs.append(
            "Tighten the metric allow-list so new dimensions require review: "
            + ", ".join(unexpected_attrs[:5])
            + "."
        )
    if theoretical_series > series_budget:
        recs.append("Set a metric-specific budget and run this check in CI before adding new labels.")
    if not recs:
        recs.append("Keep this fixture in CI as a regression guard for future instrumentation changes.")
    return recs


def _merge_budget(base: Dict[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            base[key] = _merge_budget(dict(base[key]), value)
        else:
            base[key] = value
    return base


def _deep_copy(value: Mapping[str, Any]) -> Dict[str, Any]:
    return json.loads(json.dumps(value))
