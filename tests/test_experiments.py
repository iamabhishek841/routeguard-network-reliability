from routeguard.baseline import BaselineWait, RouterBaseline
from routeguard.experiments import ExperimentPreconditionError, run_link_failure
from routeguard.models import CheckResult


class FakeController:
    def __init__(self):
        self.events = []

    def fail(self, link_name):
        self.events.append(("fail", link_name))

    def restore(self, link_name):
        self.events.append(("restore", link_name))


def healthy_wait():
    baseline = (
        RouterBaseline(
            "dub1",
            (CheckResult("bgp-peers", True, "ok"),),
        ),
    )
    return BaselineWait(baseline, attempts=2, elapsed_seconds=1.0)


def test_link_failure_restores_link_and_reports_recovery():
    controller = FakeController()
    waits = [
        healthy_wait(),
        BaselineWait(healthy_wait().results, attempts=3, elapsed_seconds=2.0),
    ]

    def wait_fn(**_):
        return waits.pop(0)

    during = (
        RouterBaseline(
            "dub1",
            (CheckResult("bgp-peers", False, "not-established=10.0.10.0"),),
        ),
    )

    report = run_link_failure(
        "core1-dub1",
        hold_seconds=0,
        controller=controller,
        wait_fn=wait_fn,
        collect_fn=lambda: during,
        sleeper=lambda _: None,
    )

    assert controller.events == [
        ("fail", "core1-dub1"),
        ("restore", "core1-dub1"),
    ]
    assert report.failed_checks_during_fault == ("dub1:bgp-peers",)
    assert report.recovered is True
    assert report.recovery_attempts == 3
    assert report.recovery_seconds == 2.0


def test_unhealthy_baseline_refuses_to_inject_fault():
    controller = FakeController()
    unhealthy = BaselineWait(
        (
            RouterBaseline(
                "dub1",
                (CheckResult("bgp-peers", False, "down"),),
            ),
        ),
        attempts=2,
        elapsed_seconds=1.0,
    )

    try:
        run_link_failure(
            "core1-dub1",
            controller=controller,
            wait_fn=lambda **_: unhealthy,
            sleeper=lambda _: None,
        )
    except ExperimentPreconditionError:
        pass
    else:
        raise AssertionError("expected ExperimentPreconditionError")

    assert controller.events == []
