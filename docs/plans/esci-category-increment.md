# Measure additional category-aware labels

Status: the four GPU passes and frozen residual analysis are complete. All four
contracts make the same 14 additional-label errors; richer categories supply no
useful precision improvement. See the [measured results](../research/evidence/esci-category-survey-results.md)
and original [preparation evidence](../research/evidence/esci-category-increment.md).
No labels are qualified or active.

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

## Verify the retained analysis

The registered protocol and original result already exist. To repeat the fixed
analysis, use the retained protocol and a fresh output file. These commands are
for the lab operator, from this repository checkout in PowerShell. They use the
existing CPU analysis environment; the Windows host is the checked platform.

First verify the owner's per-job completion, numerical and cleanup receipts
for the retained run. The statistical tool does not perform host cleanup.

```powershell
$state = 'D:\codex\Ephemeral Elasticsearch\.lab'
$owner = Join-Path $state 'esci-model-agent-repo\esci-tfm-experiment'
$analysis = Join-Path $state 'esci-category-increment\registered-01'
$python = Join-Path $state 'esci-packaging\.venv\Scripts\python.exe'
$runs = Join-Path $owner 'data\interim\category-input-study-20261003\gap-quick-launcher-01'
$repeat = Join-Path $analysis ('result-recheck-' + [guid]::NewGuid().ToString('N') + '.json')
& $python lab/experiments/esci-category-increment/analyse_increment.py run `
  --protocol "$analysis\protocol.json" --runs-root $runs `
  --output $repeat
Get-FileHash -LiteralPath $repeat -Algorithm SHA256
```

The command prints the new result path and additional counts A=80, B=79, C=76,
D=77. Unchanged inputs and source produce result hash
`81da80fa5b313bcafc247fb1d5452e8c3b8a9b9699fe58554c0163baf5884684`.
It leaves the original `result.json` intact.

The existing research validator checks all four completed inference outputs
and successful numerical repeats before this tool opens reference values. A
missing or changed output stops analysis. The tool checks source and input
hashes and refuses to replace a result. Host ownership and cleanup remain
separate operating checks; this statistical tool does not manage GPU execution.

The original `freeze` command was executed before outcomes were opened. It
created `registered-01` and refused replacement. Do not recreate or overwrite
that registration. A changed method needs a new protocol and must record that
these development outcomes have already been exposed.

## Next batch

The next proposal is a [small cached-model Exact check](esci-exact-veto-survey.md).
The quick category results do not justify the full four-pass study. Independent
[cascade confirmation](esci-cascade-confirmation.md), including actual-gap human
references, remains required before activation.
