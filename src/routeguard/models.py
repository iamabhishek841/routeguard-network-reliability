from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BgpPeer:
    address: str
    remote_as: int | None
    state: str
    prefixes_received: int | None = None

    @property
    def established(self) -> bool:
        return self.state.lower() == "established"


@dataclass(frozen=True, slots=True)
class OspfNeighbor:
    router_id: str
    state: str
    interface: str | None = None

    @property
    def full(self) -> bool:
        return self.state.lower().startswith("full")


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
