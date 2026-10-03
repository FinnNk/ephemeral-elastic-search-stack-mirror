# Qualify ESCI labels on lab gaps

Status: development inference and the predeclared class-threshold search are
complete. No tested threshold combination met the development requirements.
Independent confirmation of the original 0.90 rule stopped at the agreed
cutoff with 6,336 of 6,494 predictions; it remains incomplete. Owned GPU
resources were removed before the deadline and explicit handback was sent. Version 4 remains inactive. The assessment tools, workflow diagram
and narrow result-preservation fallback are implemented for review; the fallback
is not installed in protected source CI. See the
[execution evidence](../research/evidence/esci-label-quality.md).

## Intent and constraints

Fill enough judgement gaps to meet the lab's 80% coverage gate while limiting
Irrelevant → Exact errors. Measure existing models first, then accept labels
using independently confirmed rules for each ESCI class. Preserve the original
0.90 assessment as a separate experiment. Unknown judgements remain unknown.

- Keep published labels authoritative and assess missing labels separately.
- Reserve confirmation queries before inference. Exclude normalised query overlap
  with LoRA training, score-mapping fitting/tuning, historical model selection,
  the ongoing research final assessment and SPECIALIST-01.
- Treat an unavailable cohort manifest as an unresolved independence constraint,
  not evidence of no overlap. The research session owns its reservations.
- The 7,393-pair diagnostic cohort across 457 queries is already exposed; do not
  reuse it as independent quality confirmation.
- Pin version 4, its release and serving image to the
  [qualification receipt](../research/evidence/esci-frozen-kernels.json). A new
  release requires its own serving qualification.
- Keep threshold development and confirmation on disjoint normalised queries.
  Do not select examples or alter thresholds after viewing confirmation results.
- Run only during another agreed GPU window; retain inputs, model identity,
  predictions and assessment hashes in ignored frozen evidence.

## Work and acceptance

| Work | Result required |
| --- | --- |
| Audit provenance | Hash each cohort manifest; record query normalisation, exclusions and overlap counts without publishing query text |
| Freeze assessment | Separate published-label confirmation from representative unlabelled search results; select deterministically by query before opening model outputs |
| Obtain independent gap labels | Record human ESCI labels without exposing model predictions; do not use the candidate to label its own assessment |
| Run the exact candidate | Pin registration, runtime and policy; retain accepted labels and abstentions for every selected pair |
| Assess quality | Report query-bootstrap intervals, accepted accuracy, coverage, confusion matrix and Irrelevant-to-Exact errors; give separate results for published and newly labelled cohorts |
| Decide first-pass use | Activate only after review of serving and quality evidence; otherwise retain the bootstrap model and record the remaining work |

Freeze these initial acceptance criteria before opening confirmation results:

- Lower bound of the 95% query-bootstrap interval for accepted accuracy: at least 95%.
- At most 1% of independently labelled Irrelevant pairs accepted as Exact.
- At least 200 distinct confirmation queries and 300 accepted pairs; insufficient
  evidence remains inconclusive. Report outcomes per class even if acceptance
  is concentrated in Exact.
- Demonstrate additional coverage on representative gaps. Report residual gaps
  for later cascade passes; do not claim that historical coverage transfers to them.

If independent human gap labels are unavailable, complete the overlap audit and
published-label assessment, then leave gap-quality acceptance unresolved.
Changing the model or policy requires a newly reserved confirmation cohort.
The original frozen assessment cannot qualify a threshold selected from its results.

## Sources

- [Overall qualification](esci-model-qualification.md) and
  [inference-contract qualification](esci-inference-contract.md).
- [Model installation](../esci-model-installation.md): retrospective quality
  evidence and the exact registered release.
- [Catalogue evidence](../research/evidence/esci-catalogue.md): current missing
  judgements and the unchanged coverage gate.
- Release `release.json` and registration receipt under the ignored
  `esci-packaging` directory.
- Research records under ignored `esci-model-agent-repo`: the v3 training
  manifest and `manifests/esci-decider-us-v1.json`; round-2
  `decision-fit/tuning-report.json`, `cohorts-v2/manifest.json` and
  `round-freeze.json`; TFM `data/interim/final/assessment-manifest.json` and
  `freeze.json`; SPECIALIST-01 cohort manifest and sealed query list; the
  conservative `exposure-audit-v2/manifest.json`.

Reconstruct historical membership before applying `esci_tfm.lexical.normalize`
for overlap checks. LoRA membership is the first 8,192 eligible rows in the
pinned training parquet, excluding development queries. Mapping uses 4,565
fitting and 1,210 tuning queries, with the recorded hash assignment. Protect all
424,142 final assessment pairs and all 400 SPECIALIST-01 queries. Historical
confirmation is already exposed. An older context contained 396 specialist
queries; exclude these as well, without claiming that the sealed assessment was
scored. Verify recorded hashes rather than relying on these counts alone.

## Frozen execution choices

- Candidate version 4, release, GPU runtime and 0.90 threshold are unchanged.
- The label-free capacity audit identified 42,531 locally unused query groups
  and 771,431 pairs in official train. Official test remains entirely reserved.
  This is local exposure independence; upstream pretraining exposure is unknown.
- Select 400 normalised query groups by SHA-256 order using seed
  `esci-lab-quality-20261003-v1`; select up to 20 distinct products per query
  with a separate product hash. Freeze the resulting 6,494 pairs before labels
  or predictions are opened. Use actual full lab catalogue fields.
- The harmful-error denominator is all independently labelled Irrelevant pairs,
  including abstentions. Keep published and human-gap measurements separate.
- Use 20,000 whole-query bootstrap repetitions with seed 20261003. The
  [byte-pinned policy](../../evaluation/specs/esci-label-quality-v1.json) retains
  the criteria above; do not change them after viewing results.
- Retain the research owner's exact-membership reservation receipt before opening
  reference labels, then coordinate a checkpointed GPU window. Reference labels
  never enter the inference payload.

The [operating guide](../model-label-quality.md) describes the current CLI and
contracts. Missing independently blinded human-gap labels leave that part of
qualification unresolved; a published-label pass alone cannot activate version 4.

## Calibrate and confirm the cascade

A cascade applies successive models only to unresolved pairs. Freeze its order,
model releases and acceptance rules before testing the combined decisions.

| Stage | Work | Acceptance |
| --- | --- | --- |
| Development | Reserve 400 separate query groups with seed `esci-lab-calibration-20261003-v1`; keep them disjoint from all 400 original confirmation groups | Verified exclusions and hashes before labels or predictions are opened |
| Class-specific calibration | Compare coverage and errors across candidate thresholds for Exact, Substitute, Complement and Irrelevant | Select rules using development results only; insufficient class evidence means abstention |
| Residual pass | Assess a complementary model on unresolved pairs; challenge proposed Exact labels where useful | Record every model decision and the final source; model agreement does not replace reference labels |
| Cascade confirmation | Reserve fresh, untouched published-label queries and independently blinded actual-gap labels | Freeze the complete cascade before inference; assess its combined decisions separately from each component |
| Gate evidence | Re-evaluate the frozen search comparison using qualified sources only | At least 80% eligible coverage for the exact source revision; retain unknown pairs and source attribution |

Preserve the existing 400-query, 6,494-pair confirmation cohort, its 0.90 rule
and original policy bytes. Retain its original fixed-candidate assessment
separately. The same reservation
may confirm class-specific rules only with the research owner's agreement,
after selection is byte-frozen and before anyone opens its outputs or uses its
labels for selection. The research owner approved this bounded use before confirmation outputs were opened; no feasible development selection was found, so no revised policy is being confirmed. If independence cannot be
preserved, reserve fresh confirmation queries. Never tune from confirmation
results and claim that revised rules passed the same confirmation.

Development can run independently of that fixed assessment. GPU inference must
stay within the agreed checkpointed window.

Before opening fresh cascade confirmation results, freeze these criteria:

- At least 200 confirmation query groups and 300 accepted pairs per required
  cohort, with adequate support for each reported class.
- A 95% query-bootstrap lower bound of at least 95% for accepted accuracy.
- A 95% upper confidence bound of at most 1% for both Irrelevant → Exact rate
  and contamination of accepted Exact labels by Irrelevant products.
- Retain query clustering when estimating uncertainty. A zero-error bootstrap
  interval is insufficient evidence for either risk bound; insufficient support
  leaves qualification inconclusive.
- Report coverage, the full confusion matrix and Exact → Irrelevant errors as
  well as the two targeted risks. Record any unsupported class separately.

Published ESCI labels establish agreement on those pairs. They do not establish
quality on unlabelled retrieved products. Human gap references must be assigned
without seeing model predictions; until they exist, transfer to actual gaps
remains unresolved. No model may supply its own ground truth.

Retain pair-level published, human and model provenance behind the API. Pin
model versions, runtime images, policies and cascade decisions in frozen
artefacts. Implement current contracts directly; do not add adapters for old
lab artefacts. Recreate disposable artefacts where needed.

## Fallback if coverage remains below 80%

Do not lower Exact quality requirements to increase coverage. First consider
independent human review or a stronger model for the remaining pairs.
Semi-supervised training is a later option: use a separate training pool, give
pseudo-labels less weight than published labels, and reserve fresh confirmation.

The prepared checker and policy allow a low-coverage `decision_required`
result only for `preserve-results`: zero changed queries, identical ordered
product IDs and total counts at capture depth, exactly equal scores and coverage,
qualified labels only, and signed evidence for the exact source build. The
administrator's signed approval binds the report, policy, selection, source
revision, variant, reviewer and reason. No automatic approval is created.

The normal coverage requirement remains 80%. Low-coverage ranking changes,
changed results, unqualified predictions and invalid evidence stay blocked.
The verdict discloses actual candidate/baseline coverage and required coverage.
Unknowns cannot become Irrelevant labels, and a preserved captured list does
not establish that every result in the catalogue is unchanged.

The fallback requires review, propagation into delivery-source and protected
policy/code pin updates. Those updates and a real human decision have not been
performed. This plan does not claim either source PR is ready or its gate green.

See the [operating guide](../model-label-quality.md) for implemented assessment,
calibration and confirmation commands, and the
[evaluation runbook](../evaluation-runbook.md#human-exceptions) for authenticated
approval. A full complementary cascade still needs separate implementation and
independent confirmation.
