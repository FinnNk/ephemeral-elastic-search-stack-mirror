# Close the remaining ESCI judgement gaps

Status: CPU surveys and the residual audit are measured. Category and prompt
inference is being coordinated with the research session. No new model labels
are qualified or active.

## Intent

Reach 80% qualified coverage of the frozen Search API result pool. Use successive
specialists where they add useful labels; each stage receives only pairs still
unresolved after published labels and earlier qualified stages.

The retained comparison has 9,915 unique returned pairs. Published labels cover
2,946 pairs (29.71%). Both variants returned the same pool, so **4,986 additional
qualified labels** would bring both to 80%. A metadata scan of all English ESCI
source rows found no additional published matches.

## Constraints

- Keep published, human and model sources distinguishable. A neighbour's label
  used to predict another product remains a model prediction.
- Keep unknowns unknown. Model agreement and confidence are evidence to assess,
  rather than independent reference labels.
- Preserve the 80% gate and current quality requirements during experiments.
  A temporary exception needs its own recorded human decision.
- Use the exposed 400-query development cohort for quick surveys. It cannot
  become fresh confirmation after selecting models or rules from its results.
- Exclude all original and fresh confirmation reservations, official test,
  research assessments and specialist confirmation queries from new fitting.
  The isolated lab-inference exception covers 6,920 residual pairs; 49 specialist
  pairs remain excluded.
- Share CPU work within explicit thread and memory limits. Coordinate GPU jobs
  with the research owner; retain checkpoints and existing numerical checks.
- Pin inputs, releases, prompts, fitting partitions, thresholds and artefacts.
  Preserve unsuccessful attempts in new ignored directories. Keep pair records,
  query text and model weights out of Git.
- Implement current contracts directly. Do not add old-data adapters or change
  deployed defaults while a candidate remains unqualified.

## Survey and selection

| Work | Measure | Decision |
| --- | --- | --- |
| Source-label audit | Exact product and normalised same-query matches; actual coverage and rank/category gaps | Complete: no additional labels available for this pool |
| Confidence and input rules | Accuracy, accepted pairs, I → E and Exact contamination; stability across query halves | Numeric-model veto merits follow-up; other filters give little benefit |
| Selective recalibration | Whole-query fitting, calibration and checking partitions; incremental labels after Exact ≥0.95 | Simple probability and lexical model adds a useful 910 hypothetical gap labels |
| Category roles and embeddings | Added labels over the simpler model, precision and cost | Three extra development labels do not justify adopting the added features |
| Published support retrieval | Predict withheld products from a fixed 30% same-query support set | Title similarity alone is insufficiently precise |
| Compact NLI and instruction models | Short CPU throughput and matched prompt surveys before larger runs | Complete: NLI decoder lacks a useful signal; both prompt runtimes exceed their inference budget |
| CPU pair-model adaptation | Separate published fitting/calibration queries; incremental precision on development | Complete: one epoch selects no class at the required precision and adds zero labels |
| Granular Decider categories and prompts | Broad category, leaf, hierarchy and role instructions on matched inputs | Await measured inference; prepared contracts are not results |

Freeze each small survey before opening its outcomes. Retain all candidates,
including unsuccessful ones. Use these screens to choose the next experiment;
their intervals do not confirm a winner selected from many alternatives.

## Next batch: qualify complementary stages

The [larger fitting-pool screen](esci-fitted-specialists.md) is complete: six
fixed classifiers add no useful labels at the required precision.
[CPU pair models and prompt inference](esci-cpu-pair-judges.md) are also complete:
neither adds qualified labels. Next prioritise
[category-aware cascade selection](esci-category-cascade-selection.md) at the
research owner's saved GPU boundary. The separate 1,000-query training pool
remains excluded from confirmation.

| Work | Acceptance criterion |
| --- | --- |
| Select a fitting pool | Research-owner receipt confirms whole-query exclusions and immutable source membership before labels are opened |
| Develop the candidate | Freeze the complete feature contract and fit/calibration split; add no features from reference labels or identifiers |
| Measure residual value | Report actual additional accepted pairs and cost on the retained unlabelled pool, separately from accuracy on referenced pairs |
| Freeze the cascade | Pin stage order, model releases, runtimes, source precedence, thresholds and abstentions before confirmation |
| Confirm quality | Fresh published references and independently blinded actual-gap references; adequate query/class support; current accuracy and I → E requirements |
| Verify serving | Numerically consistent isolated inference, exact MLflow/KServe release, tracing and source-separated persistence |
| Re-run the gate | Fresh capture and signed evidence for the exact source revision, selected variants and frozen qualified judgement set |

The [cascade confirmation specification](esci-cascade-confirmation.md) defines
cohorts, error denominators, sample support and handling of rare errors. A
zero-error bootstrap or model agreement cannot establish gap quality.

Stop expanding an approach when it adds negligible coverage, lacks adequate
precision or consumes disproportionate compute. Spend the next GPU window on
the strongest category/prompt signals and necessary confirmation, rather than
repeating failed threshold searches.

If these stages cannot meet the gate, report the remaining gap and measured
quality trade-offs. Prepare a clearly bounded exception for human review. Do
not issue that decision automatically or hide the coverage shortfall.

## More information

- [Survey evidence](../research/evidence/esci-gap-surveys.md)
- [Original quality requirements](esci-label-quality.md)
- [Quality commands and contracts](../model-label-quality.md)
- [Experiment tools](../../lab/experiments/esci-gap-surveys/README.md)
- [Recorded exceptions](../evaluation-runbook.md#human-exceptions)
- Research-owned category study:
  `.lab/esci-model-agent-repo/esci-tfm-experiment/reports/category-input-study-plan.md`
  and its ignored `data/category-input-study.json`.
