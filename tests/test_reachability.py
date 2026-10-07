import subprocess

from routeguard.reachability import (
    DockerPingProbe,
    ReachabilityTarget,
    sample_reachability,
)


TARGET = ReachabilityTarget(
    name="test-path",
    router="dub1",
    source="10.100.0.1",
    target="10.200.0.1",
)


def test_ping_probe_treats_packet_loss_as_unreachable():
    def runner(command, **_):
        return subprocess.CompletedProcess(command, 1, "", "")

    probe = DockerPingProbe(runner=runner)

    assert probe.sample(TARGET) is False


def test_reachability_summary_counts_success_and_loss():
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
    assert summary.loss_percent == 100 / 3
