# Experiment model

RouteGuard treats a network failure as a bounded experiment with explicit safety gates and separate control-plane and data-plane evidence.

## Lifecycle

1. **Readiness** — wait for the expected BGP and OSPF baseline to become healthy.
2. **Traffic precondition** — verify the selected routed probe succeeds before changing the lab.
3. **Inject** — administratively take both endpoints of one named lab link down.
4. **Observe** — sample routed reachability while the fault is present, then capture the baseline checks that are failing.
5. **Restore** — bring both endpoints back up in a `finally` path even if observation fails.
6. **Recover** — wait for the expected BGP/OSPF baseline to return.
7. **Verify** — run a final routed probe after control-plane recovery.
8. **Report** — classify the observed result and optionally write a structured JSON record.

## Outcome classification

The classification is intentionally deterministic:

- `control-plane-only` — a baseline check failed, no probe loss was observed at the configured cadence, and recovery completed.
- `traffic-impact` — at least one routed probe sample failed, but the control plane and final reachability recovered.
- `recovery-failed` — the baseline did not recover within the timeout or the final routed probe failed.
- `no-observed-impact` — the experiment completed without a failed baseline check or failed traffic sample.

These names describe what RouteGuard observed during one run. They are not claims about every packet or about production-grade convergence guarantees.

## Reachability timing

Each probe sample stores its elapsed time from the start of fault-period sampling. The report can therefore show the first and last failed sample.

The timing resolution is bounded by the configured probe cadence and by the execution time of the system `ping` command. A result such as "no observed traffic failure" means no failed sample was seen at that cadence; it does not imply mathematically zero packet loss.

## Report format

Use:

```bash
routeguard experiment link-failure core1-dub1 \
  --hold 5 \
  --probe dub1-to-lon1 \
  --report reports/core1-dub1.json
```

The JSON report contains:

- schema version and UTC generation time
- experiment type, link, hold duration, and outcome
- failed BGP/OSPF checks
- control-plane recovery attempts and elapsed time
- probe source/target
- success/loss totals
- first and last observed failed probe timestamps
- the full timestamped probe timeline
- final post-recovery reachability

The `reports/` directory is ignored by git because local experiment evidence is runtime data, not source code.
