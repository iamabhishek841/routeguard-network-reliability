import subprocess

import pytest

from routeguard.faults import DockerLinkController, FaultCommandError


def test_link_fault_changes_both_endpoints_and_restores_them():
    commands = []

    def runner(command, **_):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    controller = DockerLinkController(runner=runner)
    controller.fail("core1-dub1")
    controller.restore("core1-dub1")

    assert commands == [
        [
            "docker",
            "exec",
            "clab-routeguard-core1",
            "ip",
            "link",
            "set",
            "dev",
            "eth2",
            "down",
        ],
        [
            "docker",
            "exec",
            "clab-routeguard-dub1",
            "ip",
            "link",
            "set",
            "dev",
            "eth1",
            "down",
        ],
        [
            "docker",
            "exec",
            "clab-routeguard-core1",
            "ip",
            "link",
            "set",
            "dev",
            "eth2",
            "up",
        ],
        [
            "docker",
            "exec",
            "clab-routeguard-dub1",
            "ip",
            "link",
            "set",
            "dev",
            "eth1",
            "up",
        ],
    ]


def test_partial_failure_rolls_back_the_endpoint_already_changed():
    commands = []

    def runner(command, **_):
        commands.append(command)
        if command[2] == "clab-routeguard-dub1" and command[-1] == "down":
            return subprocess.CompletedProcess(command, 1, "", "permission denied")
        return subprocess.CompletedProcess(command, 0, "", "")

    controller = DockerLinkController(runner=runner)

    with pytest.raises(FaultCommandError):
        controller.fail("core1-dub1")

    assert commands[-1] == [
        "docker",
        "exec",
        "clab-routeguard-core1",
        "ip",
        "link",
        "set",
        "dev",
        "eth2",
        "up",
    ]
