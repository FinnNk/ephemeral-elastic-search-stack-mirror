# Documentation D2: evaluation and delivery

## Intent

Give a relevancy engineer a complete route from a source change to a retained comparison and merge decision. Give the lab operator complete procedures for providing inputs and publishing evidence. Keep exploratory notebook results separate from gate decisions.

## Constraints

- Apply [technical authorship guidance](../technical-authorship.md), including sparse, faithful screenshots.
- Keep variant default, metric baseline and selected release independent where the contract permits. Baseline cannot be a selected gate candidate.
- Do not change evaluation thresholds, bypass missing exact-commit evidence or manufacture human decisions to illustrate the workflow.
- Preserve frozen reports and dated evidence; remove machine-specific run IDs from current procedures.
- Do not add compatibility adapters or alter services to make an example command appear successful.
- Source README and gate README templates must agree with published source documentation. Changes to the source repository require their own review batch.

## Work

1. Trace capture, pooled judgement resolution, scoring, attestation, publication and the trusted gate using CLI help and current code. Identify which artefacts the engineer supplies and which the operator creates.
2. Restructure `docs/delivery.md` around build, evaluate, promote and rollback. Move reference fields into concise tables and link their owning contracts. Provide paths for obtaining build receipts, recipe hashes and signed evidence rather than copying a local run.
3. Restructure data publication and judgement guides. Give every runnable example its directory, dependencies, complete flags, input origins, expected output and recovery. Replace ignored `.lab/offline-7j` fixtures with a documented preparation/download step.
4. Align `docs/variant-evaluation.md` and source `gate/README.md` with those procedures. Explain low coverage, invalid evidence, bounded exceptions and deployment approval beside the next action.
5. Put Gatling prerequisites before commands and explain probe versus measured load. Retain arrival, counter, shared-resource and inconclusive-result limits.
6. Explain how to select/download/open the exploratory notebook. Reuse the two [existing illustrations](../screenshots/README.md); add another image only if it clarifies a different necessary step.
7. Inspect the complete rendered reading path and related unchanged pages. Use read-only checks or disposable fixtures where practical; record any workflow that cannot be verified without a new approved deployment.

## Acceptance criteria

- A new engineer can identify where to start, what to supply and when an operator is needed.
- Each published procedure has obtainable inputs, complete commands, expected outputs and likely recovery.
- Report scores, coverage, changed results and gate outcomes are distinct and understandable.
- Replacement releases and N-way variant evaluation both fit the instructions; online testing is not required.
- Human exceptions retain their reason and identity and cannot override hard blocks.
- Notebook failure does not change the normal comparison verdict; saved output is not presented as gate approval.
- Templates and published copies are either aligned or their separate pending PR is explicit.
- The PR records instruction, link and visual checks, with untested platforms and live-workflow limits.

## Sources

- [Review](../reviews/documentation-2026-10-01.md), [remediation sequence](documentation-authorship.md), [lab workflow](../../lab/README.md).
- [Delivery](../delivery.md), [variant evaluation](../variant-evaluation.md), [gate policy](../relevance-gate.md), [input contracts](../data-evaluation-contracts.md), [judgement resolution](../judgement-resolution.md), [Gatling](../../lab/gatling/README.md).
- `evaluation/capture.py`, `evaluation/offline.py`, `judgements/evaluate.py`, `lab/delivery/`, `lab/run_notebook.py`, `lab/notebook_task.py` and CLI help from the checkout.
- Source templates under `lab/delivery/bootstrap/`; the `delivery-source` repository and its actual Actions status.
- Historical [managed gate evidence](../research/evidence/managed-variant-gate.md) and [notebook evidence](../research/evidence/exploratory-notebook.md), whose limits must remain intact.

After this batch, update the roadmap and create the detailed D3 model/observability documentation plan.
