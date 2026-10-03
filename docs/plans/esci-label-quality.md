# Qualify ESCI labels on lab gaps

Status: next batch. Candidate `synthetic-esci-judge/4` passed
[numerical serving qualification](../research/evidence/esci-frozen-kernels.md) and
remains inactive. Freeze and audit the independent cohorts before requesting
another GPU window. The isolated lab inference exception does not change the
confirmation exclusions: its 944 exposed final-assessment queries remain
unavailable for fresh adaptive confirmation. See the
[progressive pass plan](esci-progressive-judgements.md).

## Intent and constraints

Measure whether a numerically qualified registered release can safely supply a selective first
pass of missing judgements. Keep its frozen 0.90 acceptance threshold and the
lab's 80% judged-coverage gate. A first pass need not close every gap.

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
- Do not select examples or alter thresholds after viewing confirmation results.
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
