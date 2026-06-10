"""Helpers for summarising k3s health for the e-paper display."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeStatus:
    name: str
    ready: bool


def parse_node_status(lines: str) -> list[NodeStatus]:
    nodes: list[NodeStatus] = []
    ordered = sorted(
        [line for line in lines.splitlines() if line.strip()],
        key=lambda line: (0 if "control-plane" in line else 1, line),
    )
    for line in ordered:
        parts = line.split()
        if len(parts) < 2:
            continue
        nodes.append(NodeStatus(name=parts[0], ready=parts[1] == "Ready"))
    return nodes


def parse_ksvc_ready(lines: str) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for line in lines.splitlines():
        parts = line.split()
        if len(parts) < 6:
            continue
        result[parts[1]] = parts[5] == "True"
    return result


def parse_deployment_ready(lines: str) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for line in lines.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        ready_col = parts[2]
        current, _, desired = ready_col.partition("/")
        result[f"{parts[0]}/{parts[1]}"] = (
            bool(desired) and current == desired and desired != "0"
        )
    return result


def parse_pod_ready(lines: str) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for line in lines.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        namespace, name, ready_col, status = parts[:4]
        current, _, desired = ready_col.partition("/")
        is_ready = (
            status == "Running" and bool(desired) and current == desired and desired != "0"
        )
        result[f"{namespace}/{name}"] = is_ready
    return result


def count_abnormal_pods(lines: str) -> int:
    count = 0
    for line in lines.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        ready_col, status = parts[2], parts[3]
        current, _, desired = ready_col.partition("/")
        if status != "Running":
            count += 1
            continue
        if not desired or desired == "0" or current != desired:
            count += 1
    return count


def ksvc_reachable(ksvc_ready: bool, pod_ready: dict[str, bool]) -> bool:
    if not ksvc_ready:
        return False
    required = (
        "kourier-system/3scale-kourier-gateway",
        "knative-serving/activator",
    )
    return all(pod_ready.get(name, False) for name in required)
