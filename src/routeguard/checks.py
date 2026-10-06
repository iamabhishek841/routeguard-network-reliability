from __future__ import annotations

from collections.abc import Iterable

from .models import BgpPeer, CheckResult, OspfNeighbor


def check_bgp_peers(peers: Iterable[BgpPeer], expected: set[str]) -> CheckResult:
    peers_by_address = {peer.address: peer for peer in peers}
    observed = set(peers_by_address)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    down = sorted(
        address
        for address in expected & observed
        if not peers_by_address[address].established
    )

    problems: list[str] = []
    if missing:
        problems.append(f"missing={','.join(missing)}")
    if down:
        problems.append(f"not-established={','.join(down)}")
    if unexpected:
        problems.append(f"unexpected={','.join(unexpected)}")

    return CheckResult(
        name="bgp-peers",
        ok=not problems,
        detail="all expected BGP peers are established" if not problems else "; ".join(problems),
    )


def check_ospf_neighbors(
    neighbors: Iterable[OspfNeighbor], expected: set[str]
) -> CheckResult:
    neighbors_by_id = {neighbor.router_id: neighbor for neighbor in neighbors}
    observed = set(neighbors_by_id)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    not_full = sorted(
        router_id
        for router_id in expected & observed
        if not neighbors_by_id[router_id].full
    )

    problems: list[str] = []
    if missing:
        problems.append(f"missing={','.join(missing)}")
    if not_full:
        problems.append(f"not-full={','.join(not_full)}")
    if unexpected:
        problems.append(f"unexpected={','.join(unexpected)}")

    return CheckResult(
        name="ospf-neighbors",
        ok=not problems,
        detail="all expected OSPF neighbors are Full" if not problems else "; ".join(problems),
    )
