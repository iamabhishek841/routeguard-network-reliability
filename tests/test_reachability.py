import subprocess

import pytest

from routeguard.reachability import (
    DockerPingProbe,
    ReachabilityTarget,
    sample_reachability,
)


TARGET = ReachabilityTarget(
    name="test-path",
    router="dub1",
    source="10.110.0.1",
    target="10.210.0.1",
)


def test_ping_probe_treats_packet_loss_as_unreachable():
    def runner(command, **_):
        return subprocess.CompletedProcess(command, 1, "", "")

    probe = DockerPingProbe(runner=runner)

    assert probe.sample(TARGET) is False


def test_reachability_summary_counts_success_loss_and_failure_window():
    outcomes = iter([True, False, True])
    now = 0.0

    class FakeProbe:
        def sample(self, _):
            return next(outcomes)

    def clock():
        return now

    def sleeper(seconds):
        nonlocal now
        now += seconds

    summary = sample_reachability(
        FakeProbe(),
        TARGET,
        duration_seconds=1.0,
        interval_seconds=0.5,
        clock=clock,
        sleeper=sleeper,
    )

    assert summary.samples == 3
    assert summary.successful == 2
    assert summary.failed == 1
    assert summary.loss_percent == pytest.approx(100 / 3)
    assert summary.first_failure_seconds == pytest.approx(0.5)
    assert summary.last_failure_seconds == pytest.approx(0.5)
    assert [sample.elapsed_seconds for sample in summary.timeline] == [0.0, 0.5, 1.0]


def test_reachability_summary_has_no_failure_window_when_all_samples_pass():
    outcomes = iter([True, True])
    now = 0.0

    class FakeProbe:
        def sample(self, _):
            return next(outcomes)

    def clock():
        return now

    def sleeper(seconds):
        nonlocal now
        now += seconds

    summary = sample_reachability(
        FakeProbe(),
        TARGET,
        duration_seconds=0.5,
        interval_seconds=0.5,
        clock=clock,
        sleeper=sleeper,
    )

    assert summary.samples == 2
    assert summary.loss_percent == 0.0
    assert summary.first_failure_seconds is None
    assert summary.last_failure_seconds is None
