# RouteGuard

RouteGuard is a small network-reliability lab for answering a practical question: **when the control plane changes, can I tell what broke, whether traffic was affected, and whether the network recovered the way I expected?**

It uses FRRouting and containerlab for the network and a small Python CLI for state collection, baseline checks, bounded fault injection, routed reachability sampling, and experiment reports. The topology is intentionally small enough to understand end to end while still having redundant paths and separate IGP/BGP failure modes.

## Topology

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
- OSPF inside Dublin and London for router-loopback reachability
- independent site exits so an external-link failure has a real alternate path
- separate router loopbacks and advertised service prefixes so the traffic test does not reuse the iBGP transport addresses

The addressing and the topology correction discovered during live fault testing are documented in [docs/design-notes.md](docs/design-notes.md).

## Bring up the lab

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

containerlab deploy -t lab/routeguard.clab.yml
routeguard check all --wait 30
```

The bounded wait matters because a fresh deployment can expose OSPF and iBGP while they are still converging.

You can inspect one router directly:

```bash
routeguard snapshot dub1
```

## Run a failure experiment

```bash
routeguard experiment link-failure core1-dub1 \
  --hold 5 \
  --probe dub1-to-lon1
```

The experiment will:

1. refuse to start unless the BGP/OSPF baseline is healthy;
2. refuse to start if the selected routed path is already unreachable;
3. take both endpoints of the named lab link down;
4. sample routed reachability while the fault is present;
5. capture which baseline checks fail;
6. restore the link in a `finally` path;
7. wait for BGP/OSPF recovery;
8. verify routed reachability again after recovery.

A successful redundant-path run can therefore show a real control-plane fault while classifying the traffic result separately.

## Structured evidence

Add `--report` to save a versioned JSON record:

```bash
routeguard experiment link-failure core1-dub1 \
  --hold 5 \
  --probe dub1-to-lon1 \
  --report reports/core1-dub1.json
```

The report records the failed checks, control-plane recovery, packet success/loss totals, timestamped probe samples, first/last observed failed sample, and final reachability. Local reports are ignored by git so runtime evidence does not become source-code noise.

The experiment lifecycle, outcome meanings, and timing limitations are described in [docs/experiment-model.md](docs/experiment-model.md).

## Outcome meanings

- `control-plane-only`: routing state changed but no failed traffic sample was observed at the configured cadence.
- `traffic-impact`: at least one traffic sample failed, followed by successful recovery.
- `recovery-failed`: the control-plane baseline or final reachability did not recover within the experiment.
- `no-observed-impact`: neither a failed baseline check nor a failed traffic sample was observed.

These are observations from one bounded run, not production convergence guarantees.

## Validation history

The lab has been exercised end to end on WSL2 with Docker, containerlab, FRR 10.2.1, and Python 3.14.

One validated external-link scenario took `core1-dub1` down after a healthy baseline. The expected BGP checks failed on `core1` and `dub1`, while the corrected service-prefix path stayed reachable for all 9 sampled probes during the 5-second fault window. After the link was restored, the control-plane baseline and routed reachability returned healthy. Those numbers describe that specific local run rather than a benchmark.

The same testing also exposed and fixed a topology mistake: the original design reused the iBGP router loopbacks as advertised payload prefixes, which broke the intended return-path redundancy. The corrected design separates infrastructure loopbacks from service prefixes instead of masking the failure.

## Scope

RouteGuard is deliberately not a full network controller. It does not generate router configuration, make autonomous remediation decisions, or add protocols simply to broaden the feature list. The current project focuses on a smaller reliability loop:

**expected state -> controlled failure -> observed control-plane impact -> observed traffic impact -> deterministic recovery verification -> structured evidence**

That is the completion boundary for this version.

## Requirements

- Linux host capable of running containerlab
- Docker
- containerlab
- Python 3.11+

FRR is pinned in the topology so lab behavior does not silently change with a floating image tag.
