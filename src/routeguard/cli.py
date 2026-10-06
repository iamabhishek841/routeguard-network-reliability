from __future__ import annotations

import argparse
import json
import sys

from .checks import check_bgp_peers, check_ospf_neighbors
from .frr import FRRClient, FRRCommandError
from .inventory import EXPECTED_BGP_PEERS, EXPECTED_OSPF_NEIGHBORS, ROUTERS
from .models import CheckResult


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="routeguard")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser(
        "check", help="compare live control-plane state with the lab baseline"
    )
    check.add_argument("router", choices=(*ROUTERS, "all"), default="all", nargs="?")
    check.add_argument("--json", action="store_true", dest="as_json")

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
        return _check(args.router, args.as_json)
    except FRRCommandError as exc:
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


def _check(router: str, as_json: bool) -> int:
    routers = ROUTERS if router == "all" else (router,)
    output: list[dict[str, object]] = []
    failed = False

    for name in routers:
        client = FRRClient(name)
        bgp = check_bgp_peers(client.bgp_peers(), EXPECTED_BGP_PEERS[name])
        if EXPECTED_OSPF_NEIGHBORS[name]:
            ospf = check_ospf_neighbors(
                client.ospf_neighbors(), EXPECTED_OSPF_NEIGHBORS[name]
            )
        else:
            ospf = CheckResult(
                name="ospf-neighbors",
                ok=True,
                detail="OSPF is not part of this router's baseline",
            )
        failed = failed or not bgp.ok or not ospf.ok
        output.append(
            {
                "router": name,
                "checks": [
                    {"name": bgp.name, "ok": bgp.ok, "detail": bgp.detail},
                    {"name": ospf.name, "ok": ospf.ok, "detail": ospf.detail},
                ],
            }
        )

    if as_json:
        print(json.dumps(output, indent=2))
    else:
        for router_result in output:
            print(router_result["router"])
            for result in router_result["checks"]:
                marker = "PASS" if result["ok"] else "FAIL"
                print(f"  {marker:<4} {result['name']}: {result['detail']}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
