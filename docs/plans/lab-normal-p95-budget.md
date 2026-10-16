# Normal-load latency budget for the lab

## Decision

Increase the normal-load p95 budget from 250 ms to 300 ms, as requested after
the build 204 Integration retry missed the baseline threshold at 254 ms.
This is an explicit lab policy change, not evidence that the previous attempt
passed or that application performance improved.

Both baseline and candidate use the new limit. It applies wherever the shared
normal-phase budget is used: probes, smoke checks, normal load and the fallback
budget for stress phases. Simulated Production validation imports the same
budget. The normal p99 limit remains 500 ms and failed requests must remain
below 1%. Peak and recovery phase budgets are unchanged.

Historical reports retain their recorded budgets and verdicts. Fresh installs
inherit the new default from the source; the running control runtime needs
activation after this change is merged.

## Verification and next step

Boundary tests check 254 ms, exactly 300 ms and 301 ms independently for both
sides, and verify that p99 and error-rate failures still block the gate.
All 29 comparison, production-load validation and delivery-gate tests passed
in the locked uv environment. The first invocation hit Windows sandbox temporary
file permissions; rerunning with the project test temporary directory passed.
No live performance run was started and no historical report was rescored.

Review the change, activate when idle and submit a new Integration
attempt using the current reviewed plan if its inputs remain unchanged.
