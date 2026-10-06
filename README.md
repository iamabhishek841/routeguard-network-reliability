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

The checks intentionally fail on missing, unexpected, or non-established peers. I want failures to be explicit before adding automatic recovery logic.

## Direction

The next step is not adding more protocols. It is breaking this network in controlled ways: external link loss, BGP session loss, internal OSPF failure, and bad route advertisement. For each case I want to record detection time, route convergence, affected prefixes, and whether traffic has a usable alternate path.

That data will drive the monitoring and remediation pieces instead of starting with a dashboard and inventing metrics afterwards.

## Requirements

- Docker
- containerlab
- Python 3.11+
- Linux host capable of running containerlab

FRR is pinned in the topology so lab behavior does not silently change with a floating image tag.
