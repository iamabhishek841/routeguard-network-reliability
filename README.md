# RouteGuard

A small network-reliability lab for answering a practical question: **when the control plane changes, can I tell what broke and whether the network recovered the way I expected?**

I am building this around FRRouting and containerlab rather than trying to model a full production network. The topology is just large enough to have redundant paths and two routing layers, then the Python tooling treats the intended peer state as something that can be checked rather than something that only exists in a diagram.

## Current topology

```text
                    AS65000
              core1 -------- core2
               |  \          /  |
               |   \        /   |
               |    \      /    |
             dub1---dub2  lon1---lon2
                AS65100      AS65200
```

- eBGP between each site edge and the backbone
- iBGP between the two routers inside each AS
- OSPF inside Dublin and London to provide loopback reachability for the site iBGP sessions
- independent exits from each site so later failure tests have a real alternate path

The addressing and the reasons for keeping the first topology this size are in [docs/design-notes.md](docs/design-notes.md).

## What works in this first cut

The lab configuration defines the expected BGP/OSPF adjacencies. `routeguard` collects FRR's JSON output from the running containers and compares the observed state with that baseline.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

sudo containerlab deploy -t lab/routeguard.clab.yml

routeguard check all
routeguard snapshot dub1
```

The checks intentionally fail on missing, unexpected, or non-established peers. A bounded wait is also available because the first real lab run showed that checking immediately after deployment can catch OSPF and iBGP while they are still converging:

```bash
routeguard check all --wait 30
```

## Failure experiments

The first failure experiment takes a named lab link down on both endpoints, samples the resulting control-plane failures, restores the link in a `finally` path, and waits for the original baseline to recover.

```bash
routeguard experiment link-failure core1-dub1 --hold 5
```

The command refuses to inject a fault if the lab is already unhealthy or if the selected routed probe is unreachable before the experiment starts.

During the fault, RouteGuard samples an end-to-end routed path as well as the control-plane baseline. The default probe sends sourced ICMP traffic from the Dublin loopback to the London loopback:

```bash
routeguard experiment link-failure core1-dub1 --hold 5 --probe dub1-to-lon1
```

The report keeps the two signals separate: BGP/OSPF recovery time describes the control plane, while the probe summary reports whether routed traffic was actually interrupted during the failure window. A final probe is run after the baseline recovers.

## Requirements

- Docker
- containerlab
- Python 3.11+
- Linux host capable of running containerlab

FRR is pinned in the topology so lab behavior does not silently change with a floating image tag.
