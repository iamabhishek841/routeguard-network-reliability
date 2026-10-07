from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .checks import check_bgp_peers, check_ospf_neighbors
from .frr import FRRClient
from .inventory import EXPECTED_BGP_PEERS, EXPECTED_OSPF_NEIGHBORS, ROUTERS
from .models import CheckResult


@dataclass(frozen=True, slots=True)
class RouterBaseline:
    router: str
    checks: tuple[CheckResult, ...]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)


@dataclass(frozen=True, slots=True)
class BaselineWait:
    results: tuple[RouterBaseline, ...]
    attempts: int
    elapsed_seconds: float

    @property
    def ok(self) -> bool:
        return all(result.ok for result in self.results)


def collect_baseline(
    routers: Iterable[str] = ROUTERS,
    client_factory: Callable[[str], FRRClient] = FRRClient,
) -> tuple[RouterBaseline, ...]:
    results: list[RouterBaseline] = []

    for router in routers:
        client = client_factory(router)
        bgp = check_bgp_peers(client.bgp_peers(), EXPECTED_BGP_PEERS[router])

        if EXPECTED_OSPF_NEIGHBORS[router]:
            ospf = check_ospf_neighbors(
                client.ospf_neighbors(), EXPECTED_OSPF_NEIGHBORS[router]
            )
        else:
            ospf = CheckResult(
                name="ospf-neighbors",
                ok=True,
                detail="OSPF is not part of this router's baseline",
            )

        results.append(RouterBaseline(router=router, checks=(bgp, ospf)))

    return tuple(results)


def wait_for_baseline(
    *,
    routers: Iterable[str] = ROUTERS,
    timeout_seconds: float = 30.0,
    interval_seconds: float = 1.0,
    client_factory: Callable[[str], FRRClient] = FRRClient,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> BaselineWait:
    if timeout_seconds < 0:
        raise ValueError("timeout_seconds must be non-negative")
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")

    selected = tuple(routers)
    start = clock()
    attempts = 0

    while True:
        attempts += 1
        results = collect_baseline(selected, client_factory)
        elapsed = clock() - start

        if all(result.ok for result in results) or elapsed >= timeout_seconds:
            return BaselineWait(
                results=results,
                attempts=attempts,
                elapsed_seconds=elapsed,
            )

        remaining = timeout_seconds - elapsed
        sleeper(min(interval_seconds, remaining))
