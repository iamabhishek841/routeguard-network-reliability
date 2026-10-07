from __future__ import annotations

import json
import subprocess
from typing import Any

from .models import BgpPeer, OspfNeighbor


class FRRCommandError(RuntimeError):
    pass


class FRRClient:
    def __init__(self, router: str, lab_name: str = "routeguard") -> None:
        self.router = router
        self.container = f"clab-{lab_name}-{router}"

    def _json_command(self, command: str) -> dict[str, Any]:
        proc = subprocess.run(
            ["docker", "exec", self.container, "vtysh", "-c", command],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            message = proc.stderr.strip() or proc.stdout.strip() or "unknown FRR error"
            raise FRRCommandError(f"{self.router}: {command!r} failed: {message}")

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise FRRCommandError(
                f"{self.router}: {command!r} did not return valid JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise FRRCommandError(
                f"{self.router}: {command!r} returned an unexpected JSON shape"
            )
        return payload

    def bgp_peers(self) -> list[BgpPeer]:
        payload = self._json_command("show bgp ipv4 unicast summary json")
        return parse_bgp_peers(payload)

    def ospf_neighbors(self) -> list[OspfNeighbor]:
        payload = self._json_command("show ip ospf neighbor json")
        return parse_ospf_neighbors(payload)


def parse_bgp_peers(payload: dict[str, Any]) -> list[BgpPeer]:
    peers: dict[str, BgpPeer] = {}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            candidate = value.get("peers")
            if isinstance(candidate, dict):
                for address, raw in candidate.items():
                    if not isinstance(raw, dict):
                        continue
                    remote_as = _as_int(raw.get("remoteAs") or raw.get("remoteAS"))
                    state = str(
                        raw.get("state")
                        or raw.get("peerState")
                        or raw.get("bgpState")
                        or ""
                    )
                    prefixes = _as_int(
                        raw.get("pfxRcd")
                        if raw.get("pfxRcd") is not None
                        else raw.get("prefixesReceived")
                    )
                    peers[str(address)] = BgpPeer(
                        address=str(address),
                        remote_as=remote_as,
                        state=state,
                        prefixes_received=prefixes,
                    )
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return sorted(peers.values(), key=lambda peer: peer.address)


def parse_ospf_neighbors(payload: dict[str, Any]) -> list[OspfNeighbor]:
    neighbors: dict[str, OspfNeighbor] = {}

    def walk(value: Any, key_hint: str | None = None) -> None:
        if isinstance(value, dict):
            is_neighbor = "nbrState" in value or (
                "state" in value and _looks_like_ospf(value)
            )
            if is_neighbor:
                router_id = str(
                    value.get("neighborId")
                    or value.get("nbrRouterId")
                    or value.get("routerId")
                    or key_hint
                    or ""
                )
                if router_id:
                    state = str(value.get("nbrState") or value.get("state") or "")
                    interface = value.get("ifaceName") or value.get("interfaceName")
                    neighbors[router_id] = OspfNeighbor(
                        router_id=router_id,
                        state=state,
                        interface=str(interface) if interface else None,
                    )

            for key, child in value.items():
                walk(child, str(key))
        elif isinstance(value, list):
            for child in value:
                walk(child, key_hint)

    walk(payload)
    return sorted(neighbors.values(), key=lambda nbr: nbr.router_id)


def _looks_like_ospf(value: dict[str, Any]) -> bool:
    return any(
        key in value
        for key in ("nbrState", "ifaceName", "neighborId", "nbrRouterId", "routerId")
    )


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
