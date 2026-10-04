# CPU query–product model experiment

Train one small four-class ESCI model, then measure whether it adds accurate
labels after the retained comparator. This is an experiment, not a serving
model or gate source. See the [results](../../../docs/research/evidence/esci-cpu-pair-judges.md)
and [batch plan](../../../docs/plans/esci-cpu-pair-judges.md).

## Inputs and runtime

The Windows lab run uses two existing Python environments. The research
environment supplies Torch and Transformers for training and scoring; the
packaging environment supplies NumPy and scikit-learn for assessment. The script
uses four CPU threads and does not allocate a GPU.

| Input | Required record |
| --- | --- |
| Fitting pool | Frozen inputs, published references and manifest from the separately reserved 1,000 queries |
| Development | Frozen inputs and published references for the already exposed 400 queries |
| Model | Local `cross-encoder/ms-marco-MiniLM-L6-v2` snapshot at revision `233902d25c440f23af6f7d6e94d2946bac0bee0a` |
| Comparator | Row-aligned prior-stage predictions and their hash receipt |
| Output | A new directory; preserve every completed or interrupted attempt |

The model receives query, title, brand, category hierarchy, bullets and
description. Missing text stays missing. Identifiers, labels and synthetic
serving fields do not enter those strings. A fresh four-class head replaces the
retrieval head; all encoder weights are trained for one epoch.

## Run on the Windows lab host

Run PowerShell from the **ephemeral stack checkout containing these tools**.
These commands use the host's retained inputs and environments. Choose a new
output name before repeating an experiment.

```powershell
$state = 'D:\codex\Ephemeral Elasticsearch\.lab'
$modelPython = Join-Path $state 'esci-model-agent-repo\.venv\Scripts\python.exe'
$metricsPython = Join-Path $state 'esci-packaging\.venv\Scripts\python.exe'
$pool = Join-Path $state 'esci-fitted-specialists\fitting-pool-01'
$development = Join-Path $state 'esci-packaging\label-calibration-20261003'
$prefix = Join-Path $state 'esci-fitted-specialists\development-prefix.jsonl'
$cache = Join-Path $state 'esci-fitted-specialists\reranker-cache'
$snapshotPath = 'models--cross-encoder--ms-marco-MiniLM-L6-v2\snapshots\233902d25c440f23af6f7d6e94d2946bac0bee0a'
$snapshot = Join-Path $cache $snapshotPath
$output = Join-Path $state 'esci-fitted-specialists\cpu-crossencoder-new-attempt'
$tool = 'lab\experiments\esci-gap-surveys\cpu_crossencoder_fit.py'

& $modelPython $tool train --pool $pool --development $development `
  --output $output --snapshot $snapshot
if ($LASTEXITCODE -ne 0) { throw 'Training failed; preserve this attempt.' }
& $modelPython $tool score --pool $pool --development $development `
  --output $output --prefix $prefix
if ($LASTEXITCODE -ne 0) { throw 'Scoring failed; preserve this attempt.' }
& $metricsPython $tool evaluate --pool $pool --development $development `
  --output $output --prefix $prefix
if ($LASTEXITCODE -ne 0) { throw 'Assessment failed; preserve this attempt.' }
```

1. Training freezes its contract and whole-query partition before loading
   published labels. The optimiser uses only the 700 fitting groups. The
   implementation loads calibration references into the same tensor but never
   selects their rows for optimiser updates; calibration is excluded from fitting,
   not claimed to have remained unread throughout the process.
2. After 64 updates, a throughput projection must fit the 30-minute training
   budget. A stopped run retains its weights but cannot enter assessment.
3. Scoring writes separate calibration and development probability arrays.
   Assessment selects each class's threshold from calibration only, then reports
   development accuracy, support, harmful errors and additional labels after the
   comparator.

Expect `training-receipt.json`, `scoring-receipt.json` and `report.json` in the
output directory. Each record identifies its input and artefact hashes. A process
failure or incomplete receipt is not a completed candidate; keep it and start a
new attempt after fixing the cause.

This procedure was exercised on Windows. Linux and macOS execution, serving
parity and independently referenced actual-gap quality were not checked.
