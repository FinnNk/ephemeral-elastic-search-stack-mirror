# Prepare independent reviews of judgement gaps

Create a packet of query–product pairs for human review without showing model
predictions. The command uses the current frozen gap-input contract and keeps
the pair mapping in a separate operator directory. It creates **no labels** and
does not reserve a confirmation cohort or qualify a model.

## Prepare the packet

Use Python with the [model-quality dependencies](../evaluation/model-quality-requirements.txt)
installed. Run from the lab repository root. You need:

- Frozen `judgement-pass-inputs` from the [progressive judgement workflow](plans/esci-progressive-judgements.md).
- A complete exclusion audit whose `inputs_sha256` matches those bytes and
  whose `query_ids` names protected queries.
- A sample size and seed chosen before inspecting labels or model outcomes.

The following PowerShell example uses an operator-supplied directory containing
`inputs.json` and `exclusions.json`:

```powershell
$gapDir = Read-Host 'Absolute frozen gap-input directory'
$packetDir = Read-Host 'New absolute review-packet directory'
python evaluation/prepare_gap_review.py `
  --inputs "$gapDir/inputs.json" --exclusions "$gapDir/exclusions.json" `
  --queries 100 --seed gap-review-fixed-01 --output "$packetDir"
```

Use the same Python command on Linux/macOS with shell-appropriate path variables.
The tool was exercised on Windows. The seed is an experiment choice; do not
reroll it after viewing answers.

The command selects whole normalised query groups and includes all their gap
pairs. It excludes every alias of a protected query. It prints the selected
query/pair counts and a manifest hash. An invalid audit, duplicate pair or
existing output directory stops the command. Preserve earlier packets and use
a new directory for a different registered preparation.

| Directory | Contents | Who receives it |
| --- | --- | --- |
| `reviewer/` | Input-only `items.jsonl`, blank `labels.csv` and review instructions | Independent reviewers, each with their own answer copy |
| `operator/` | Original pair mapping, sampled `inputs.jsonl`, source hashes and sampling manifest | Operator only |

The reviewer sees query text, market, filters, title, brand, description, bullets
and category hierarchy when available. Ratings, synthetic stock/popularity,
catalogue prices, model scores, stage identities and source pair IDs are omitted.
The complete original request/product fields remain in the operator's inference inputs.

## Collect and use answers

1. Before obtaining answers for confirmation, freeze the candidate cascade and
   obtain the independent reservation and query-overlap audit required by the
   [confirmation specification](plans/esci-cascade-confirmation.md).
   A gap-inference exclusion receipt is not an independence audit.
2. Give each reviewer only `reviewer/`. They record E, S, C or I and a short
   reason. Insufficient information stays uncertain; never replace it with
   a model prediction or infer Irrelevant from missing text.
3. Retain the separate reviewer files, reviewer identities and adjudication
   record. Have a second reviewer resolve disagreement; preserve unresolved
   answers and report their count.
4. The data producer freezes agreed human references with
   `provenance.kind: human` and its pinned `source_id`. Keep that source distinct
   from published labels and every model stage.
5. Assemble and assess the complete cohort using the
   [label-quality contracts](model-label-quality.md). The current assessor needs
   an ESCI reference for every frozen pair; incomplete answers are unfinished
   evidence, not a smaller silently filtered cohort.

The packet tool does not import answers, construct a confirmed quality manifest
or mark labels gate-eligible. The current exploratory pass-import endpoint
accepts model evidence only; it is not an upload route for these human reviews.
Human reference collection and source publication remain producer responsibilities.

## Scope and evidence

Equal query selection includes all pairs from selected groups. Keep this
sampling design and query dependence when estimating quality. A 100-query
preparation does not establish the required sample support or rare-error bounds.

The current lab gaps overlap a research reservation under a separately recorded
inference exception. Preparing their input-only packet does not extend that
exception to independent confirmation or permit opening research references.
The [preparation evidence](research/evidence/esci-gap-review-packet.md) records
the exercised sample and its limits.
