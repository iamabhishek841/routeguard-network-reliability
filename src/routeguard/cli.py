from __future__ import annotations

import argparse
import json
import sys

from .baseline import collect_baseline, wait_for_baseline
from .frr import FRRClient, FRRCommandError
from .inventory import ROUTERS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="routeguard")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser(
        "check", help="compare live control-plane state with the lab baseline"
    )
    check.add_argument("router", choices=(*ROUTERS, "all"), default="all", nargs="?")
    check.add_argument("--json", action="store_true", dest="as_json")
    check.add_argument(
        "--wait",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="retry until the baseline is healthy or the timeout expires",
    )
    check.add_argument(
        "--interval",
        type=float,
        default=1.0,
        metavar="SECONDS",
        help="poll interval used with --wait (default: 1)",
    )

    snapshot = sub.add_parser(
        "snapshot", help="print peer state collected from one router"
    )
    snapshot.add_argument("router", choices=ROUTERS)

    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        if args.command == "snapshot":
            return _snapshot(args.router)
        return _check(args.router, args.as_json, args.wait, args.interval)
    except (FRRCommandError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _snapshot(router: str) -> int:
    client = FRRClient(router)
    payload = {
        "router": router,
        "bgp": [
            {
                "address": peer.address,
                "remote_as": peer.remote_as,
                "state": peer.state,
                "prefixes_received": peer.prefixes_received,
            }
            for peer in client.bgp_peers()
        ],
        "ospf": [
            {
                "router_id": neighbor.router_id,
                "state": neighbor.state,
                "interface": neighbor.interface,
            }
            for neighbor in client.ospf_neighbors()
        ],
    }
    print(json.dumps(payload, indent=2))
    return 0


def _check(router: str, as_json: bool, wait: float, interval: float) -> int:
    routers = ROUTERS if router == "all" else (router,)

    if wait > 0:
        waited = wait_for_baseline(
            routers=routers,
            timeout_seconds=wait,
            interval_seconds=interval,
        )
        results = waited.results
    else:
        waited = None
        results = collect_baseline(routers)

    output = [
        {
            "router": result.router,
            "checks": [
                {"name": check.name, "ok": check.ok, "detail": check.detail}
                for check in result.checks
            ],
        }
        for result in results
    ]
    failed = any(not result.ok for result in results)

    if as_json:
        print(json.dumps(output, indent=2))
    else:
        if waited is not None:
            state = "ready" if waited.ok else "not ready"
            print(
                f"baseline {state} after {waited.attempts} checks "
                f"({waited.elapsed_seconds:.2f}s)"
            )

        for router_result in output:
            print(router_result["router"])
            for result in router_result["checks"]:
                marker = "PASS" if result["ok"] else "FAIL"
                print(f"  {marker:<4} {result['name']}: {result['detail']}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
