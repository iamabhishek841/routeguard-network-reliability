from routeguard.baseline import BaselineWait, RouterBaseline
from routeguard.experiments import ExperimentPreconditionError, run_link_failure
from routeguard.models import CheckResult
from routeguard.reachability import ReachabilitySummary, ReachabilityTarget


TARGET = ReachabilityTarget(
    name="dub1-to-lon1",
    router="dub1",
    source="10.100.0.1",
    target="10.200.0.1",
)


class FakeController:
    def __init__(self):
        self.events = []

    def fail(self, link_name):
        self.events.append(("fail", link_name))

    def restore(self, link_name):
        self.events.append(("restore", link_name))


class FakeProbe:
    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [True])
        self.calls = 0

    def sample(self, _):
        value = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        return value


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
    probe = FakeProbe([True, True])
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

    summary = ReachabilitySummary(TARGET, samples=5, successful=5)

    report = run_link_failure(
        "core1-dub1",
        probe_target=TARGET,
        controller=controller,
        probe=probe,
        wait_fn=wait_fn,
        collect_fn=lambda: during,
        sample_fn=lambda *args, **kwargs: summary,
    )

    assert controller.events == [
        ("fail", "core1-dub1"),
        ("restore", "core1-dub1"),
    ]
    assert report.failed_checks_during_fault == ("dub1:bgp-peers",)
    assert report.recovered is True
    assert report.recovery_attempts == 3
    assert report.recovery_seconds == 2.0
    assert report.reachability.loss_percent == 0.0
    assert report.reachable_after_recovery is True


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
            probe_target=TARGET,
            controller=controller,
            wait_fn=lambda **_: unhealthy,
        )
    except ExperimentPreconditionError:
        pass
    else:
        raise AssertionError("expected ExperimentPreconditionError")

    assert controller.events == []


def test_unreachable_probe_refuses_to_inject_fault():
    controller = FakeController()

    try:
        run_link_failure(
            "core1-dub1",
            probe_target=TARGET,
            controller=controller,
            probe=FakeProbe([False]),
            wait_fn=lambda **_: healthy_wait(),
        )
    except ExperimentPreconditionError:
        pass
    else:
        raise AssertionError("expected ExperimentPreconditionError")

    assert controller.events == []
