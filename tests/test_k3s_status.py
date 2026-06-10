from k3s_status import (
    count_abnormal_pods,
    ksvc_reachable,
    parse_deployment_ready,
    parse_ksvc_ready,
    parse_node_status,
    parse_pod_ready,
)


def test_parse_node_status_sorts_control_plane_first_and_tracks_ready():
    lines = "\n".join(
        [
            "pi4-r-2 Ready <none> 1d v1.35.4",
            "pi5-w-1 Ready control-plane 10d v1.35.4",
            "pi4-r-1 NotReady <none> 1d v1.35.4",
        ]
    )

    nodes = parse_node_status(lines)

    assert [node.name for node in nodes] == ["pi5-w-1", "pi4-r-1", "pi4-r-2"]
    assert [node.ready for node in nodes] == [True, False, True]


def test_parse_workload_readiness():
    ksvc_lines = (
        "knative-pool hotosm-imagery-tile http://example created ready True\n"
        "knative-pool poc-cesg-poi-search http://example created ready False"
    )
    deploy_lines = (
        "traccar traccar 1/1 1 1 1d\n"
        "cng-storage cng-storage-rustfs 0/1 1 0 1d"
    )
    pod_lines = "\n".join(
        [
            "kourier-system 3scale-kourier-gateway-abc 0/1 CrashLoopBackOff 12 1d",
            "knative-serving activator-xyz 1/1 Running 0 1d",
            "default some-ok 1/1 Running 0 1d",
            "default some-pending 0/1 Pending 0 1d",
        ]
    )

    assert parse_ksvc_ready(ksvc_lines) == {
        "hotosm-imagery-tile": True,
        "poc-cesg-poi-search": False,
    }
    assert parse_deployment_ready(deploy_lines) == {
        "traccar/traccar": True,
        "cng-storage/cng-storage-rustfs": False,
    }
    assert parse_pod_ready(pod_lines) == {
        "kourier-system/3scale-kourier-gateway-abc": False,
        "knative-serving/activator-xyz": True,
        "default/some-ok": True,
        "default/some-pending": False,
    }
    assert count_abnormal_pods(pod_lines) == 2


def test_ksvc_reachable_requires_gateway_and_activator():
    pod_ready = {
        "kourier-system/3scale-kourier-gateway": False,
        "knative-serving/activator": True,
    }
    assert not ksvc_reachable(True, pod_ready)

    pod_ready = {
        "kourier-system/3scale-kourier-gateway": True,
        "knative-serving/activator": True,
    }
    assert ksvc_reachable(True, pod_ready)
    assert not ksvc_reachable(False, pod_ready)
