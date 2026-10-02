# Offline evaluation experiments

Measure fresh Search API captures against the installed synthetic million-product
index. These finite workloads compare evaluator completion time; Gatling owns
load profiles and capacity verdicts. Read the [plan](../../../docs/plans/evaluation-throughput.md)
for the acceptance rules.

## Run the campaign

Use the experiment PR revision when reproducing its baseline: `server.py` imports
the Search API at that revision. A later API implementation changes that baseline.
The recorded image/source hashes identify the measured bytes; rebuilding a tag
is a new experiment, not the original result.

Prerequisites: the local k3d lab, `lab-variant-managed/search` serving
`retail-gb-1m-v1`, its read-only ES credentials/CA, the retained frozen release,
the existing Blob forward on port 14577, and Python dependencies from
`lab/requirements-azure.txt` and `lab/requirements-eval.txt`. The host tests also
need `httpx==0.28.1`. The harness pins APIs and workers to the two named k3d nodes;
change and record placements for a different cluster.

In PowerShell, from the repository root:

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
$env:PYTHONPATH = "$env:LAB_STATE_DIR/python-libs;lab;lab/search-app"
$experiment = Join-Path $env:LAB_STATE_DIR ('throughput-' + (Get-Date -Format yyyyMMdd-HHmmss))
$harness = 'lab/experiments/evaluation-throughput'
docker build -t relevance-throughput-experiment:20261002 -f "$harness/Dockerfile" .
& "$env:LAB_STATE_DIR/tools/k3d.exe" image import relevance-throughput-experiment:20261002 -c relevance-lab
python "$harness/run.py" setup --directory $experiment
python "$harness/campaign.py" transport --directory $experiment
python "$harness/campaign.py" scheduling --directory $experiment
python "$harness/campaign.py" confirmation --directory $experiment
python "$harness/deadline.py" --directory $experiment
```

Setup creates a labelled disposable namespace and prints its name. Each capture
prints duration, error/retry counts and a semantic hash of ordered IDs and totals.
It writes `ledger.jsonl`, local compressed raw records and hash-verified immutable
Blob copies. Hash agreement is evidence for those requests only, not a guarantee
that future searches are deterministic. Do not run stages concurrently.

For resource samples, run `campaign.py resources --directory $experiment` in a
second terminal. Stop it with Ctrl+C before cleanup. Resource samples support the
run ledger; missing samples cannot establish absence of contention.

Optional judgement batching uses the installed abstaining KServe model and an
isolated judgement API/cache. It leaves source labels and the installed cache
unchanged:

```powershell
python "$harness/judge_run.py" prepare --directory $experiment
python "$harness/campaign.py" judgements --directory $experiment
```

Preparation scans the source catalogue to select missing recalled pairs. The
batch test uses that fixed pair workload without repeating search; it does not
replace any fresh search capture. A no-op model cannot qualify concurrency for a
future real inference model. Setup retries and a failed clone are separate from
timed successful runs.

Write the summary after all stages finish:

```powershell
python "$harness/analyse.py" --directory $experiment --output "$experiment/analysis.json"
```

The analyser verifies each raw-record hash, retains every option and checks the
predeclared confirmation rules. It also compares complete observations between
fresh repetitions. A failure or changed query cannot disappear behind a median.

Clean up this campaign's namespace after retaining its evidence:

```powershell
python "$harness/run.py" cleanup --directory $experiment
```

The namespace ownership check prevents cleanup of an unrelated namespace.
Frozen input indices and retained Blob records survive cleanup. If a Job fails,
inspect its events/logs before cleanup; do not count missing output as a pass.

## Read the measurements

| Measurement | Boundary |
| --- | --- |
| Capture | Client construction, fresh requests, validation and observation assembly |
| Job startup | Job creation timestamp to worker process start; image was already imported |
| End to end | Job creation/wait, log collection, scoring against synthetic pooled labels, serialisation and Blob read-back |
| Judgement preparation | Host catalogue scan, recorded separately |
| Judgement resolution | Fixed missing-pair batches against the real service with its installed abstaining model |

End-to-end timing excludes API deployment, ConfigMap creation, source preflight
and optional judgement resolution. It is a retained experimental report, not a
complete release gate. Raw request latency includes retries/backoff after
admission; queue waiting is not instrumented in this prototype. Adaptive control
uses windows of 32 completions, per-variant median latency and transient failures.

Run the functional checks from the same checkout:

```powershell
python -m unittest discover -s lab/experiments/evaluation-throughput -p test_worker.py -v
```

They exercise request freshness, result instability, selectors, bounded retries,
slow variants and overlapping allocations. Research alternatives stay here;
only measured winners enter the normal capture/API implementations.
