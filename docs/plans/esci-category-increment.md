# Measure additional category-aware labels

Status: the analysis tool is prepared and tested on synthetic fixtures. The
four GPU passes and their quality results are pending. This batch adds no labels.
See the [preparation evidence](../research/evidence/esci-category-increment.md).

Measure which category inputs add useful labels after the frozen experimental
prefix: the Exact 0.95 stage followed by the retained recalibrator. All four
variants use the same 512 exposed development pairs; 362 remain after that
prefix. The prefix itself is unqualified and partly fitted on development data.

## Constraints and acceptance

| Check | Required result |
| --- | --- |
| Frozen method | Register tool, helper and input hashes before reading category results or reference values |
| GPU execution | Research owner completes the approved exclusive hand-over, numerical repeats and host cleanup; retain those receipts before analysis |
| Matched inputs | All four variants join exactly to the 512 input pairs and their normalised query keys; every pair joins to the retained prefix |
| Additional decisions | Keep all accepted prefix decisions; count a category label only where the prefix abstained |
| Fixed mapping | Use saved mapped decisions at confidence ≥ 0.90 for every class; select no threshold and perform no recalibration |
| Quality evidence | Open only the hash-bound published development references after completed numerical and inference checks; keep independent confirmation sealed |
| Report | Additional accepted and correct pairs, errors, class/query support, I → E, C → E, E → I and Irrelevant contamination of accepted Exact labels |
| Uncertainty | Existing 2,000 whole-query resamples for statistics; existing 20,000 paired resamples for B−A, C−B and D−C differences |

Coverage differences and gold-class error denominators use **all 512 pairs**.
Additional-label accuracy uses only additional accepted pairs. Empty support
remains unavailable; zero observed errors do not establish a rare-error bound.
The fixed contrasts are exploratory and do not qualify a model or change the gate.

## Run the analysis

These commands are for the lab operator, from this repository checkout in
PowerShell. They use the existing CPU analysis environment; no GPU is needed.
The Windows host is the checked platform.

```powershell
$state = 'D:\codex\Ephemeral Elasticsearch\.lab'
$owner = Join-Path $state 'esci-model-agent-repo\esci-tfm-experiment'
$packet = Join-Path $owner 'data\interim\category-input-study-20261003\quick-512-registration-01'
$analysis = Join-Path $state 'esci-category-increment\registered-01'
$python = Join-Path $state 'esci-packaging\.venv\Scripts\python.exe'
& $python lab/experiments/esci-category-increment/analyse_increment.py freeze `
  --packet $packet --prefix "$state\esci-fitted-specialists\development-prefix.jsonl" `
  --owner $owner --output $analysis
```

Freeze prints the protocol hash and the prefix/residual counts. It creates a
fresh directory and refuses to replace an existing registration. Preserve a
failed attempt and use a new directory if the registered code needs correction.

Before running, verify the active grant's output directory and the owner's
per-job completion, numerical and cleanup receipts. Set `$runs` to **that exact
output directory**, rather than guessing it from an earlier plan.

```powershell
& $python lab/experiments/esci-category-increment/analyse_increment.py run `
  --protocol "$analysis\protocol.json" --runs-root $runs `
  --output "$analysis\result.json"
```

The existing research validator checks all four completed inference outputs
and successful numerical repeats before this tool opens reference values. A
missing or changed output stops analysis. The tool checks source and input
hashes and refuses to replace a result. Host ownership and cleanup remain
separate operating checks; this statistical tool does not manage GPU execution.

## Next batch

Complete the [category survey and signal selection](esci-category-cascade-selection.md).
Use measured additional labels, harmful errors and compute cost to choose deeper
work. Retain inconclusive results without declaring a winner. Independent
[cascade confirmation](esci-cascade-confirmation.md), including actual-gap human
references, remains required before activation.
