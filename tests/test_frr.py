from routeguard.frr import parse_bgp_peers, parse_ospf_neighbors


def test_parse_bgp_summary_keeps_peer_state():
    payload = {
        "ipv4Unicast": {
            "routerId": "10.100.0.1",
            "as": 65100,
            "peers": {
                "10.0.10.0": {
                    "remoteAs": 65000,
                    "state": "Established",
                    "pfxRcd": 2,
                },
                "10.100.0.2": {
                    "remoteAs": 65100,
                    "state": "Established",
                    "pfxRcd": 3,
                },
            },
        }
    }

    peers = parse_bgp_peers(payload)

    assert [peer.address for peer in peers] == ["10.0.10.0", "10.100.0.2"]
    assert peers[0].remote_as == 65000
    assert peers[0].established is True
    assert peers[0].prefixes_received == 2


def test_parse_ospf_neighbor_uses_router_id():
    payload = {
        "default": {
            "10.100.0.2": [
                {
                    "neighborId": "10.100.0.2",
                    "nbrState": "Full/Backup",
                    "ifaceName": "eth2:10.1.0.0",
                }
            ]
        }
    }

    neighbors = parse_ospf_neighbors(payload)

    assert len(neighbors) == 1
    assert neighbors[0].router_id == "10.100.0.2"
    assert neighbors[0].full is True
    assert neighbors[0].interface == "eth2:10.1.0.0"
