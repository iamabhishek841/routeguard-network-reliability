from routeguard.checks import check_bgp_peers, check_ospf_neighbors
from routeguard.models import BgpPeer, OspfNeighbor


def test_bgp_check_reports_a_peer_that_is_present_but_down():
    peers = [
        BgpPeer("10.0.10.0", 65000, "Established", 2),
        BgpPeer("10.100.0.2", 65100, "Active", 0),
    ]

    result = check_bgp_peers(peers, {"10.0.10.0", "10.100.0.2"})

    assert result.ok is False
    assert "not-established=10.100.0.2" in result.detail


def test_ospf_check_rejects_unexpected_neighbor():
    neighbors = [
        OspfNeighbor("10.100.0.2", "Full/DR", "eth2"),
        OspfNeighbor("10.100.0.99", "Full/DR", "eth2"),
    ]

    result = check_ospf_neighbors(neighbors, {"10.100.0.2"})

    assert result.ok is False
    assert "unexpected=10.100.0.99" in result.detail
