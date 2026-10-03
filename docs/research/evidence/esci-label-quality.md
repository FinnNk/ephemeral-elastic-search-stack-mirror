# ESCI label quality — 3 October 2026

## Result

The predeclared development search found no feasible class-threshold policy.
Threshold changes alone have not established a safe route to 80% eligible
coverage. Version 4 remains inactive; previous model predictions remain
exploratory. Independent confirmation of the original 0.90 rule is incomplete: 6,336 of
6,494 predictions were retained when the agreed cleanup cutoff was reached.
No confirmation assessment or completed-cohort claim was made.

## Experiment

| Item | Frozen choice |
| --- | --- |
| Model | `synthetic-esci-judge/4`, release `44235684d820fc12feee84c36e9f8b0e0bb85bccf77d0c34f489672ab9bd0719` |
| Development | 400 normalised queries, 6,525 pairs; 24 minutes 36 seconds of inference |
| Confirmation | 400 disjoint normalised queries, 6,494 pairs |
| Ground truth | Published English US ESCI train labels; official test and research reservations excluded |
| Inputs | Actual fields from the full lab catalogue; reference labels never sent to inference |
| Selection | Fixed per-class grid; 20,000 whole-query bootstrap repetitions; independent confirmation required |
| Local evidence | Ignored `esci-packaging/label-calibration-20261003` and `label-quality-20261003` directories |

The research owner verified exact query membership and protected exclusions
before inference. Local exposure independence does not establish absence from
upstream model pretraining. No independently blinded actual-gap labels have
been collected, so transfer quality remains unresolved.

## Development diagnostics

| Exact threshold | Accepted pairs | Accepted query groups | Observed accepted accuracy | Irrelevant → Exact |
| --- | ---: | ---: | ---: | ---: |
| 0.90 | 2,545 | 321 | 94.93% | 24 / 626 (3.83%) |
| 0.95 | 1,046 | 193 | 97.90% | 2 / 626 (0.32%) |
| 0.975 | 1 | 1 | Insufficient sample | Insufficient sample |

At 0.90, the query-bootstrap 95% accuracy interval was 93.17–96.50%.
The Irrelevant → Exact interval was 0.98–8.14%. Only 137 query groups
contained Irrelevant references. The more conservative 0.95 region trades
coverage for observed precision but has insufficient query support for the
predeclared bounds. These development intervals are diagnostic, not independent
confirmation of a threshold selected from the same data.

At a 0.50 threshold, Substitute accepted 791 pairs with 58.53% accuracy,
Complement 35 with 57.14%, and Irrelevant 238 with 70.17%. Lower thresholds
for those classes did not supply a reliable residual filler. A larger, fresh,
Irrelevant-rich assessment could qualify a conservative Exact policy, but it
would not establish that this model alone can close the coverage gap.

## Checks and traces

- 60 focused tests passed across judgement provenance, evaluation, gate guards,
  cohort assessment, HTTP inference and class-threshold selection/confirmation.
- Ruff and whitespace checks passed for the changed Python files.
- The Archify qualification workflow passed its delivery and browser checks;
  its rendered diagram was inspected.
- SigNoz stored the connected client → model HTTP → prediction trace
  `ebfaf9013d9b8d7c7f203dab8d7a810f`. The ignored trace receipt retains parent
  identities; no query or product text is published here.

[Immutable file hashes](esci-label-quality.json) identify the retained evidence.

## Follow-up

The runner completed cleanup at 18:15:02 BST, before its 18:17:16 deadline.
The candidate Pod, InferenceService, ServingRuntime and own client containers
were absent; own port forwards were terminated. Explicit handback was sent.
A requested extra two minutes was rejected by automatic approval review because
it required explicit human approval; the existing cutoff was honoured.
Retain the incomplete confirmation directory. A future authorised retry needs
a new output directory; do not silently assess a reduced cohort or overwrite
the retained pass. Development already found no feasible revised policy, so
finishing this original-rule assessment would not qualify a revised cascade.
[The next batch](../../plans/esci-quality-next.md) separates trusted checker
rollout, the real ESCI coverage decision and residual model qualification.
The prepared coverage fallback is limited to strictly preserved captured results
and requires a recorded human decision; ranking changes still require 80%.
