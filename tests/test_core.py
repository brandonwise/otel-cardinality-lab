from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from otel_cardinality_lab.core import analyze_payload, iter_metric_points, load_budget, render_markdown


class CoreTests(unittest.TestCase):
    def test_iterates_otlp_metric_points_with_resource_attributes(self) -> None:
        payload = {
            "resourceMetrics": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "checkout"}},
                        ]
                    },
                    "scopeMetrics": [
                        {
                            "metrics": [
                                {
                                    "name": "http.server.duration",
                                    "histogram": {
                                        "dataPoints": [
                                            {
                                                "attributes": [
                                                    {"key": "http.route", "value": {"stringValue": "/pay/{id}"}},
                                                    {"key": "user.id", "value": {"stringValue": "u-1"}},
                                                ]
                                            }
                                        ]
                                    },
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        points = list(iter_metric_points(payload))

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].metric, "http.server.duration")
        self.assertEqual(points[0].attributes["service.name"], "checkout")
        self.assertEqual(points[0].attributes["user.id"], "u-1")

    def test_denied_attribute_makes_metric_critical(self) -> None:
        payload = {
            "metrics": [
                {
                    "name": "http.server.duration",
                    "points": [
                        {"attributes": {"service.name": "checkout", "http.route": "/pay/{id}", "user.id": "u-1"}},
                        {"attributes": {"service.name": "checkout", "http.route": "/pay/{id}", "user.id": "u-2"}},
                    ],
                }
            ]
        }
        budget = {
            "metrics": {
                "http.server.duration": {
                    "max_series": 10,
                    "deny_attributes": ["user.id"],
                }
            }
        }

        report = analyze_payload(payload, load_budget(None) | budget)

        metric = report["metrics"][0]
        self.assertEqual(metric["severity"], "critical")
        self.assertIn("denied attributes are present: user.id", metric["problems"])

    def test_high_cardinality_attribute_recommendation(self) -> None:
        payload = {
            "metrics": [
                {
                    "name": "queue.message.latency",
                    "points": [
                        {"attributes": {"queue.name": "default", "k8s.pod.uid": f"pod-{idx}"}}
                        for idx in range(8)
                    ],
                }
            ]
        }
        budget = {
            "global": {
                "max_values_per_attribute": 5,
                "warn_values_per_attribute": 3,
                "dangerous_attributes": ["k8s.pod.uid"],
            }
        }

        report = analyze_payload(payload, load_budget(None) | budget)
        rendered = render_markdown(report)

        self.assertEqual(report["summary"]["highest_severity"], "high")
        self.assertIn("k8s.pod.uid", rendered)
        self.assertIn("collector transforms", rendered)


class CliTests(unittest.TestCase):
    def test_cli_writes_json_and_markdown(self) -> None:
        payload = {
            "metrics": [
                {
                    "name": "http.server.duration",
                    "points": [
                        {"attributes": {"service.name": "checkout", "user.id": "u-1"}},
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "metrics.json"
            json_path = root / "report.json"
            md_path = root / "report.md"
            input_path.write_text(json.dumps(payload), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "otel_cardinality_lab",
                    "analyze",
                    str(input_path),
                    "--output",
                    str(json_path),
                    "--markdown",
                    str(md_path),
                ],
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["summary"]["metrics"], 1)
            self.assertIn("OpenTelemetry Cardinality Report", md_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
