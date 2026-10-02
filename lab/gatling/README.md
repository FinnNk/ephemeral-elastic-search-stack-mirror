# Compare API performance with Gatling

Gatling replays one frozen synthetic workload against baseline and candidate APIs and retains native reports plus a paired verdict. A probe verifies the runner; it is not a capacity result.

## Choose a route and profile

| Route | Prerequisites |
| --- | --- |
| Control UI **Gatling performance** | Installed lab, two ready environments on one frozen catalogue |
| Kubernetes CLI Jobs | Same lab, frozen APIs, Blob Storage emulator port-forward/credentials and pinned runner image |
| Local Docker runner | Docker, baseline/candidate API forwards on 18080/18081; original 10k aliases |

| Profile | Purpose |
| --- | --- |
| `probe` | Short wiring/readiness check |
| `smoke` | Five measured minutes at 10 requests/s |
| `normal`, `peak`, `stress` | Short runner calibration |
| `normal-full`, `sustained-peak`, `stress-full` | Longer phases from the 30-minute million-release trace |

No host Java is needed. The pinned simulation uses Gatling's Java SDK and Maven inside its container.

## Run a local pair

Use PowerShell from the repository root. Have the two original 10k API forwards running, then select the retained state directory:

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
python lab/traffic.py generate
python lab/traffic.py compile --profile probe
python lab/run_gatling.py probe baseline
python lab/run_gatling.py probe candidate
python lab/compare_gatling.py probe
```

The compiler writes schedules/feeders under retained `workloads/`. Each runner writes native HTML and arrival records; the comparator prints the paired result. For a Kubernetes pair over the original aliases:

```powershell
python lab/run_gatling_job.py probe baseline
python lab/run_gatling_job.py probe candidate
$baselineRun = Read-Host 'run_id printed by the baseline Job'
$candidateRun = Read-Host 'run_id printed by the candidate Job'
python lab/compare_gatling_jobs.py probe $baselineRun $candidateRun
```

Use the control UI for arbitrary ready environments and the million release. Its runner resolves the selected in-cluster services. To compile a million-release schedule explicitly, use `python lab/traffic.py compile --profile sustained-peak --release retail-gb-1m-v1`.

## Frozen request context

Phase feeders contain `planned_ms`, `query_id`, `query`, `country`, `currency`
and `filters`. The compiler resolves these from the frozen query suite; the
simulation sends them to the API. Filters use the [current contract](../../docs/search-request.md).
Recompile with the current compiler before a run. Changed feeder bytes get a new
workload hash; old native reports remain historical evidence. There is no reader
for older feeder layouts.

## Read the result

Warm-up/ramp intervals are excluded from measured budgets. The adapter checks planned versus actual arrivals and phase counts before evaluating latency/errors. Missing events, unstable baselines or incomplete runs make the result inconclusive; they are not a pass. Shared indices/host resources can cause contention.

Jobs copy reports from a temporary PVC, retain them in Azure Blob Storage by hash, then remove temporary Jobs, ConfigMaps and PVCs. A retained report survives environment removal. If a run fails, inspect its Job/runner error and arrival ledger before retrying with a new run ID.

See [traffic modelling](../../docs/research/synthetic-traffic.md), [performance contract](../../docs/prototype-design.md#performance-check-the-search-api-with-gatling) and [dated measurements](../../docs/research/evidence/gatling.md) for profile assumptions, budgets and evidence limits.
