from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .experiments import LinkFailureReport


REPORT_SCHEMA_VERSION = 1


def report_to_dict(
    report: LinkFailureReport,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc)

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at.astimezone(timezone.utc).isoformat(),
        "experiment": {
            "type": "link-failure",
            "link": report.link,
            "hold_seconds": report.hold_seconds,
            "outcome": report.outcome,
        },
        "control_plane": {
            "failed_checks_during_fault": list(report.failed_checks_during_fault),
            "recovered": report.recovered,
            "recovery_attempts": report.recovery_attempts,
            "recovery_seconds": report.recovery_seconds,
        },
        "reachability": {
            "probe": report.reachability.target.name,
            "router": report.reachability.target.router,
            "source": report.reachability.target.source,
            "target": report.reachability.target.target,
            "samples": report.reachability.samples,
            "successful": report.reachability.successful,
            "failed": report.reachability.failed,
            "loss_percent": report.reachability.loss_percent,
            "first_failure_seconds": report.reachability.first_failure_seconds,
            "last_failure_seconds": report.reachability.last_failure_seconds,
            "reachable_after_recovery": report.reachable_after_recovery,
            "timeline": [
                {
                    "elapsed_seconds": sample.elapsed_seconds,
                    "reachable": sample.reachable,
                }
                for sample in report.reachability.timeline
            ],
        },
    }


def write_report(
    report: LinkFailureReport,
    path: str | Path,
    *,
    generated_at: datetime | None = None,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            report_to_dict(report, generated_at=generated_at),
            indent=2,
            sort_keys=True,
        )
        + "
",
        encoding="utf-8",
    )
    return destination
