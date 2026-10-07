from routeguard.baseline import collect_baseline, wait_for_baseline
from routeguard.models import BgpPeer, OspfNeighbor


class FakeDub1Client:
    def __init__(self, *, established: bool = True) -> None:
        self.established = established

    def bgp_peers(self):
        state = "Established" if self.established else "Connect"
        return [
            BgpPeer("10.0.10.0", 65000, "Established", 2),
            BgpPeer("10.100.0.2", 65100, state, 0),
        ]

    def ospf_neighbors(self):
        return [OspfNeighbor("10.100.0.2", "Full/-", "eth2")]


def test_collect_baseline_combines_bgp_and_ospf_checks():
    results = collect_baseline(
        ("dub1",),
        client_factory=lambda _: FakeDub1Client(established=True),
    )

    assert len(results) == 1
    assert results[0].router == "dub1"
    assert results[0].ok is True


def test_wait_for_baseline_retries_until_control_plane_is_ready():
    attempts = 0
    now = 0.0

    def factory(_):
        nonlocal attempts
        attempts += 1
        return FakeDub1Client(established=attempts >= 3)

    def clock():
        return now

    def sleeper(seconds):
        nonlocal now
        now += seconds

    result = wait_for_baseline(
        routers=("dub1",),
        timeout_seconds=10,
        interval_seconds=1,
        client_factory=factory,
        clock=clock,
        sleeper=sleeper,
    )

    assert result.ok is True
    assert result.attempts == 3
    assert result.elapsed_seconds == 2.0
