# CPU pair-model and prompt results

Measured on 4 October 2026 on the Windows lab host. **Neither trial supplies
qualified labels.** The trained pair model fails the precision screen; the
prompt probe is too small and lacks calibrated acceptance scores. Actual gate
coverage remains 2,946 / 9,915 pairs (29.71%).

## Trained query–product model

Adapt the pinned 22.7M-parameter MS MARCO MiniLM encoder with a fresh four-class
ESCI head. One CPU epoch uses 11,749 published pairs from 700 reserved queries;
300 separate queries supply 5,019 calibration pairs. The exposed development
cohort contains 6,525 pairs across 400 queries and is excluded from fitting.

| Measurement | Result |
| --- | ---: |
| Training | 735 updates; 1,453.83 s (24.23 min) |
| Calibration and development scoring | 418.56 s (6.98 min) |
| Development argmax accuracy | 4,554 / 6,525 (69.79%); query-bootstrap 95% interval 67.14–72.60% |
| Always predict Exact, for comparison | 4,552 / 6,525 (69.76%) |
| Calibration Exact predictions at 0.95 | 836 accepted; 93.90% accuracy, below the required 98% |
| Selected classes / additional labels | None / zero |

Argmax means always taking the highest-scoring class. It is a diagnostic,
not the selective acceptance policy. Its full confusion includes 222 Irrelevant
pairs predicted Exact out of 626 Irrelevant references: 35.46%, with a query
bootstrap interval of 26.92–43.65%. Of 4,815 Exact predictions, 913 are incorrect;
222 of those are Irrelevant. No Complement is predicted.

The frozen calibration grid selects no class. Thresholds above 0.95 accept no
Exact examples; Substitute, Complement and Irrelevant have no support even at
0.70. Zero accepted labels means no useful coverage or measurable accepted
accuracy. It does not establish that the model is safe.

The optimiser selects only fitting rows. The implementation loads the permitted
calibration references into the same tensor, so they were read but unused in
training; this is not a claim of lifetime unopened calibration labels. Exact
training, scoring and assessment sources, weights and optimiser-index checks
are retained. The [model receipt](esci-cpu-pair-judges-model.json) contains aggregate
results and hashes; no pair examples or membership are committed.

## Quantised prompt probe

Use official Qwen 2.5 1.5B Q4_K_M weights in the pinned llama.cpp Windows CPU
runtime, with four threads, one slot and zero GPU layers. The same 32 pairs from
32 exposed query groups receive each prompt. Their published references contain
25 Exact, five Substitute, one Complement and one Irrelevant example.

| Prompt | Correct pairs | Accuracy | Truncated inputs |
| --- | ---: | ---: | ---: |
| Title and broad category | 22 / 32 | 68.75% | 0 |
| Title, hierarchy and product-role instructions | 25 / 32 | 78.13% | 0 |
| The same role instructions with brand and body text | 20 / 32 | 62.50% | 11 |

Hierarchy and role instructions correct five broad-prompt errors and introduce
two. Their paired accuracy difference is +9.38 percentage points, with a
descriptive query-bootstrap interval of −6.25 to +25 points. This does not
establish an improvement. Only one Irrelevant reference makes zero I → E errors
uninformative. Grammar-constrained class choices supply no calibrated confidence.

The 96 scores take 213.36 seconds. The projected full 256-pair matched survey
would take 28.45 minutes, exceeding the fixed 15-minute inference budget, so it
stops after the probe. The owned server exits and its loopback port is confirmed
closed. The [prompt receipt](esci-cpu-pair-judges-prompts.json) retains publisher,
runtime, contract and outcome hashes, complete confusion matrices and the
post-probe paired diagnostic. Runtime parity with the earlier PyTorch model and
isolated hardware speed are not claimed.

## Decision and validation

Stop these two trials. The trained model adds no useful labels, and the small
prompt probe does not justify a longer run. Preserve both outcomes and prioritise
the research owner's [matched granular-category study](../../plans/esci-category-cascade-selection.md).
Its prepared inputs and watcher are not measured results. GPU execution must
wait for the frozen classifier's completed, saved boundary.

Nine focused software tests and Ruff passed. The
[CPU model guide](../../../lab/experiments/esci-gap-surveys/CPU-PAIR-MODEL.md)
and [prompt guide](../../../lab/experiments/esci-llamacpp-survey/README.md)
describe the exercised Windows commands and their limits. Rendered documentation
review is recorded with the [batch validation receipt](esci-cpu-pair-judges.validation.json).
Software checks do not
qualify labels. No new model release, serving activation, source policy or gate
change occurs in this batch.

Raw artefacts remain under ignored `.lab/esci-fitted-specialists/cpu-crossencoder-01/`
and `.lab/esci-fitted-specialists/llamacpp-survey/`. The
[confirmation specification](../../plans/esci-cascade-confirmation.md) still
requires adequate independent references and harmful-error support before a
complete cascade can supply gate labels.
