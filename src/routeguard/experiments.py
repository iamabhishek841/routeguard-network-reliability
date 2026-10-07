from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from .baseline import BaselineWait, RouterBaseline, collect_baseline, wait_for_baseline
from .faults import DockerLinkController


class ExperimentPreconditionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LinkFailureReport:
    link: str
    hold_seconds: float
    failed_checks_during_fault: tuple[str, ...]
    recovered: bool
    recovery_attempts: int
    recovery_seconds: float


def failed_check_names(results: tuple[RouterBaseline, ...]) -> tuple[str, ...]:
    failures: list[str] = []
    for result in results:
        for check in result.checks:
            if not check.ok:
                failures.append(f"{result.router}:{check.name}")
    return tuple(failures)


def run_link_failure(
    link_name: str,
    *,
    hold_seconds: float = 5.0,
    recovery_timeout_seconds: float = 30.0,
    interval_seconds: float = 1.0,
    controller: DockerLinkController | None = None,
    wait_fn: Callable[..., BaselineWait] = wait_for_baseline,
    collect_fn: Callable[..., tuple[RouterBaseline, ...]] = collect_baseline,
    sleeper: Callable[[float], None] = time.sleep,
) -> LinkFailureReport:
    if hold_seconds < 0:
        raise ValueError("hold_seconds must be non-negative")

    controller = controller or DockerLinkController()
    before = wait_fn(
        timeout_seconds=recovery_timeout_seconds,
        interval_seconds=interval_seconds,
    )
    if not before.ok:
        raise ExperimentPreconditionError(
            "baseline is not healthy; refusing to inject a fault"
        )

    controller.fail(link_name)
    try:
        sleeper(hold_seconds)
        during = collect_fn()
    finally:
        controller.restore(link_name)

    recovery = wait_fn(
        timeout_seconds=recovery_timeout_seconds,
        interval_seconds=interval_seconds,
    )
    return LinkFailureReport(
        link=link_name,
        hold_seconds=hold_seconds,
        failed_checks_during_fault=failed_check_names(during),
        recovered=recovery.ok,
        recovery_attempts=recovery.attempts,
        recovery_seconds=recovery.elapsed_seconds,
    )
