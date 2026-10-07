from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LinkEndpoint:
    router: str
    interface: str


@dataclass(frozen=True, slots=True)
class LabLink:
    name: str
    left: LinkEndpoint
    right: LinkEndpoint


LAB_LINKS: dict[str, LabLink] = {
    "core1-core2": LabLink(
        "core1-core2",
        LinkEndpoint("core1", "eth1"),
        LinkEndpoint("core2", "eth1"),
    ),
    "core1-dub1": LabLink(
        "core1-dub1",
        LinkEndpoint("core1", "eth2"),
        LinkEndpoint("dub1", "eth1"),
    ),
    "core2-dub2": LabLink(
        "core2-dub2",
        LinkEndpoint("core2", "eth2"),
        LinkEndpoint("dub2", "eth1"),
    ),
    "core1-lon1": LabLink(
        "core1-lon1",
        LinkEndpoint("core1", "eth3"),
        LinkEndpoint("lon1", "eth1"),
    ),
    "core2-lon2": LabLink(
        "core2-lon2",
        LinkEndpoint("core2", "eth3"),
        LinkEndpoint("lon2", "eth1"),
    ),
    "dub1-dub2": LabLink(
        "dub1-dub2",
        LinkEndpoint("dub1", "eth2"),
        LinkEndpoint("dub2", "eth2"),
    ),
    "lon1-lon2": LabLink(
        "lon1-lon2",
        LinkEndpoint("lon1", "eth2"),
        LinkEndpoint("lon2", "eth2"),
    ),
}


class FaultCommandError(RuntimeError):
    pass


class DockerLinkController:
    def __init__(
        self,
        lab_name: str = "routeguard",
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.lab_name = lab_name
        self.runner = runner

    def fail(self, link_name: str) -> None:
        self._set_link(link_name, up=False)

    def restore(self, link_name: str) -> None:
        self._set_link(link_name, up=True)

    def _set_link(self, link_name: str, *, up: bool) -> None:
        try:
            link = LAB_LINKS[link_name]
        except KeyError as exc:
            choices = ", ".join(sorted(LAB_LINKS))
            raise ValueError(f"unknown link {link_name!r}; choose one of: {choices}") from exc

        changed: list[LinkEndpoint] = []
        for endpoint in (link.left, link.right):
            try:
                self._set_endpoint(endpoint, up=up)
                changed.append(endpoint)
            except FaultCommandError:
                if not up:
                    for changed_endpoint in reversed(changed):
                        try:
                            self._set_endpoint(changed_endpoint, up=True)
                        except FaultCommandError:
                            pass
                raise

    def _set_endpoint(self, endpoint: LinkEndpoint, *, up: bool) -> None:
        state = "up" if up else "down"
        container = f"clab-{self.lab_name}-{endpoint.router}"
        command = [
            "docker",
            "exec",
            container,
            "ip",
            "link",
            "set",
            "dev",
            endpoint.interface,
            state,
        ]
        proc = self.runner(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            message = proc.stderr.strip() or proc.stdout.strip() or "unknown docker error"
            raise FaultCommandError(
                f"{endpoint.router}:{endpoint.interface} -> {state} failed: {message}"
            )
