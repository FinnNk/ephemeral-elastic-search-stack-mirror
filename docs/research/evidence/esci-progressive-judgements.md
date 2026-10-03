# Progressive ESCI judgement pass — 3 October 2026

A fixed candidate-4 pass added **2,099 exploratory Exact predictions** to the
recorded comparison. It did not qualify their accuracy or change merge-gate
coverage.

## Measured results

| Measure | Result |
| --- | ---: |
| Eligible missing pairs | 6,920 |
| Accepted predictions | 2,099 (30.3%) |
| Abstentions | 4,821 |
| Inference errors | 0 |
| Excluded specialist pairs | 49 across six queries |
| Published labels in each variant's recall pool | 2,946 / 9,915 (29.7%) |
| Published plus exploratory predictions | 5,045 / 9,915 (50.9%) |
| Remaining unknown pairs | 4,870 |
| Further accepted labels needed to reach 80% exploratory coverage | 2,887 |
| Measured pass duration | 940.55 seconds (15 minutes 41 seconds) |

Both variants returned the same frozen recall pool. These numbers demonstrate
coverage and the retained-source workflow, not an improvement in ranking.
All accepted predictions were `E`; the 0.90 threshold was unchanged. Abstentions
remain unknown rather than being relabelled Irrelevant.

## Pins and research boundary

The input pool uses the full English ESCI catalogue and the unchanged captured
comparison from [catalogue verification](esci-catalogue.md). The candidate is
`synthetic-esci-judge/4`, with its numerically verified release and GPU image
from [serving qualification](esci-frozen-kernels.md).

The user authorised isolated inference on 944 reserved final-assessment queries.
All six overlapping specialist confirmation queries were excluded. Research
labels and prediction caches were not read. The research owner retained the
original frozen 18-model matrix, verified its 83 frozen files and recorded the
exposure amendment for future adaptive work. These exposed queries cannot be
presented as fresh independent confirmation for later model selection.

The model, prompt, score mapping, runtime and policy stayed fixed. The GPU owner
checkpointed research and granted a documented ten-minute extension of the
original window. Temporary candidate/API resources were removed and the GPU
explicitly handed back before the amended deadline.

## Retained evidence and verification

The ignored `esci-packaging/progressive-20261003` directory retains input hashes,
reservation audits and exception, exposure-ledger identity, GPU-window receipts,
canaries, actual Pod/image identity, incremental attempts, the complete pass,
SQLite evidence and source-separated report exports. Public hashes and
aggregate results are in [the receipt](esci-progressive-judgements.json).

- The full pass was imported into the shared full-catalogue Judgement API with
  every prediction and abstention. Reimport and a Deployment restart preserved
  the same 6,920 candidate evidence hashes. Sampled label and abstention records
  remained distinguishable through the records endpoint. Import did not activate candidate 4; the
  default inference model remains the abstaining version 1.
- Frozen shared-API reports confirmed 50.9% exploratory and 29.7% gate coverage.
  The actual exploratory report contains 2,099 unqualified labels and is
  rejected by the gate eligibility guard. The gate report contains none.
- Search API source PR #20 passed release CI. Its relevance check correctly
  remains blocked because no signed report exists for that exact source head;
  the earlier comparison cannot be reused as evidence for a different commit.
- 72 focused judgement, evaluation and gate tests passed, with five upstream
  warnings. Ruff passed. The packaged pass command started successfully.
- Demo and full deployed API smoke checks passed: published labels returned,
  gaps remained unknown under default gate selection, and forged input records
  were rejected.
- The workflow passed Archify showcase validation and browser visual checks.
  Its rendered preview was inspected. Six PowerShell blocks parsed without
  errors; local documentation links were checked, including generated gate
  policy/selection links in the source checkout.
- SigNoz retained one verified six-span trace chain across the pass client,
  Judgement API and KServe, with matching parent identities.

Two startup attempts stopped before lab-gap inference because of missing host
OTel and container contract dependencies. The corrected image packages the
contract and includes it in its source hash. A supervision monitor briefly read
`pass.json` during its final write and logged a read error; the CLI finished,
and the complete 6,920-record file was independently verified before import.
Original failed-attempt logs and the completion check remain retained.

## Next decision

The first pass fills 30.3% of the eligible gaps. Independent label quality is
still required before any candidate prediction becomes gate-eligible. Continue
with the [quality plan](../../plans/esci-label-quality.md), then choose another
pinned model for the remaining gaps using measured acceptance and cost. The
80% gate and its coverage denominator are unchanged.
