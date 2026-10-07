from __future__ import annotations

import argparse
import json
import sys

from .baseline import collect_baseline, wait_for_baseline
from .experiments import ExperimentPreconditionError, run_link_failure
from .faults import LAB_LINKS, FaultCommandError
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

    experiment = sub.add_parser(
        "experiment", help="run a bounded failure experiment against the lab"
    )
    experiment_sub = experiment.add_subparsers(dest="experiment", required=True)
    link_failure = experiment_sub.add_parser(
        "link-failure",
        help="take one lab link down, sample control-plane impact, then restore it",
    )
    link_failure.add_argument("link", choices=tuple(sorted(LAB_LINKS)))
    link_failure.add_argument(
        "--hold",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="time to keep the link down before sampling state (default: 5)",
    )
    link_failure.add_argument(
        "--recovery-timeout",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="maximum time to wait for a healthy baseline after restore (default: 30)",
    )
    link_failure.add_argument(
        "--interval",
        type=float,
        default=1.0,
        metavar="SECONDS",
        help="baseline polling interval (default: 1)",
    )
    link_failure.add_argument("--json", action="store_true", dest="as_json")

    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        if args.command == "snapshot":
            return _snapshot(args.router)
        if args.command == "experiment":
            return _experiment_link_failure(args)
        return _check(args.router, args.as_json, args.wait, args.interval)
    except (FRRCommandError, FaultCommandError, ExperimentPreconditionError, ValueError) as exc:
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


def _experiment_link_failure(args: argparse.Namespace) -> int:
    report = run_link_failure(
        args.link,
        hold_seconds=args.hold,
        recovery_timeout_seconds=args.recovery_timeout,
        interval_seconds=args.interval,
    )
    payload = {
        "link": report.link,
        "hold_seconds": report.hold_seconds,
        "failed_checks_during_fault": list(report.failed_checks_during_fault),
        "recovered": report.recovered,
        "recovery_attempts": report.recovery_attempts,
        "recovery_seconds": report.recovery_seconds,
    }

    if args.as_json:
        print(json.dumps(payload, indent=2))
    else:
        failures = (
            ", ".join(report.failed_checks_during_fault)
            if report.failed_checks_during_fault
            else "none observed"
        )
        recovery = "PASS" if report.recovered else "FAIL"
        print(f"link: {report.link}")
        print(f"control-plane failures while down: {failures}")
        print(
            f"recovery: {recovery} after {report.recovery_attempts} checks "
            f"({report.recovery_seconds:.2f}s)"
        )

    return 0 if report.recovered else 1


if __name__ == "__main__":
    raise SystemExit(main())
