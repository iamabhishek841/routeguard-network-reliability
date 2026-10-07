from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReachabilityTarget:
    name: str
    router: str
    source: str
    target: str


@dataclass(frozen=True, slots=True)
class ReachabilitySummary:
    target: ReachabilityTarget
    samples: int
    successful: int

    @property
    def failed(self) -> int:
        return self.samples - self.successful

    @property
    def loss_percent(self) -> float:
        if self.samples == 0:
            return 0.0
        return (self.failed / self.samples) * 100.0


REACHABILITY_TARGETS: dict[str, ReachabilityTarget] = {
    "dub1-to-lon1": ReachabilityTarget(
        name="dub1-to-lon1",
        router="dub1",
        source="10.100.0.1",
        target="10.200.0.1",
    ),
    "lon1-to-dub1": ReachabilityTarget(
        name="lon1-to-dub1",
        router="lon1",
        source="10.200.0.1",
        target="10.100.0.1",
    ),
}


class PingCommandError(RuntimeError):
    pass


class DockerPingProbe:
    def __init__(
        self,
        lab_name: str = "routeguard",
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.lab_name = lab_name
        self.runner = runner

    def sample(self, target: ReachabilityTarget) -> bool:
        container = f"clab-{self.lab_name}-{target.router}"
        command = [
            "docker",
            "exec",
            container,
            "ping",
            "-I",
            target.source,
            "-c",
            "1",
            "-W",
            "1",
            target.target,
        ]
        proc = self.runner(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        if proc.returncode == 0:
            return True
        if proc.returncode == 1:
            return False

        message = proc.stderr.strip() or proc.stdout.strip() or "unknown ping error"
        raise PingCommandError(
            f"{target.name}: reachability probe failed to run: {message}"
        )


def sample_reachability(
    probe: DockerPingProbe,
    target: ReachabilityTarget,
    *,
    duration_seconds: float,
    interval_seconds: float = 0.5,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> ReachabilitySummary:
    if duration_seconds < 0:
        raise ValueError("duration_seconds must be non-negative")
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")

    start = clock()
    deadline = start + duration_seconds
    samples = 0
    successful = 0

    while True:
        samples += 1
        if probe.sample(target):
            successful += 1

        now = clock()
        if now >= deadline:
            break

        sleeper(min(interval_seconds, deadline - now))

    return ReachabilitySummary(
        target=target,
        samples=samples,
        successful=successful,
    )
