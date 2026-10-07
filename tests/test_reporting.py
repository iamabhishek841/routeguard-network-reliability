import json

import pytest
from datetime import datetime, timezone

from routeguard.experiments import LinkFailureReport
from routeguard.reachability import (
    ReachabilitySample,
    ReachabilitySummary,
    ReachabilityTarget,
)
from routeguard.reporting import report_to_dict, write_report


TARGET = ReachabilityTarget(
    name="dub1-to-lon1",
    router="dub1",
    source="10.110.0.1",
    target="10.210.0.1",
)


def example_report():
    return LinkFailureReport(
        link="core1-dub1",
        hold_seconds=5,
        failed_checks_during_fault=("core1:bgp-peers", "dub1:bgp-peers"),
        recovered=True,
        recovery_attempts=1,
        recovery_seconds=1.24,
        reachability=ReachabilitySummary(
            TARGET,
            (
                ReachabilitySample(0.0, True),
                ReachabilitySample(0.5, False),
                ReachabilitySample(1.0, True),
            ),
        ),
        reachable_after_recovery=True,
    )


def test_report_payload_keeps_control_plane_and_traffic_separate():
    payload = report_to_dict(
        example_report(),
        generated_at=datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc),
    )

    assert payload["schema_version"] == 1
    assert payload["experiment"]["outcome"] == "traffic-impact"
    assert payload["control_plane"]["failed_checks_during_fault"] == [
        "core1:bgp-peers",
        "dub1:bgp-peers",
    ]
    assert payload["reachability"]["loss_percent"] == pytest.approx(100 / 3)
    assert payload["reachability"]["first_failure_seconds"] == 0.5
    assert payload["reachability"]["last_failure_seconds"] == 0.5
    assert len(payload["reachability"]["timeline"]) == 3


def test_write_report_creates_parent_directory(tmp_path):
    path = tmp_path / "reports" / "run.json"

    written = write_report(
        example_report(),
        path,
        generated_at=datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc),
    )

    assert written == path
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["experiment"]["link"] == "core1-dub1"
    assert payload["reachability"]["probe"] == "dub1-to-lon1"
