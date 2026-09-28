# MLflow and KServe judgement coverage

## Intent

Resolve judgement gaps exposed by either side of a relevance comparison. Keep search observations, source labels and model predictions separate. MLflow registers the model; KServe serves an exact registered version. The first model abstains for every pair, so this release proves the path without claiming new relevance evidence.

## Constraints

- Inputs and labels are synthetic. A missing label is unknown; `I` is an explicit irrelevant label. A model abstention and an inference failure are distinct from both.
- The judgement service is independent of the Search API and lab controller. It reads versioned query and product inputs and stored labels, then calls KServe only for gaps.
- Baseline and candidate search against frozen environments. Capture both result lists first, resolve the union of pairs needed at the metric cut-offs, then freeze one judgement snapshot and score both sides against it.
- A later candidate can introduce more pairs. Resolve those pairs into a new immutable snapshot and rescore both sides; never mutate a previous snapshot or report.
- Pin the catalogue, query suite, judgement rubric, model version and model artefact identity. Aliases may select a version for deployment but cannot identify a frozen evaluation.
- Do not place labels in the Search API, treat model predictions as human truth, or infer relevance from an absent judgement.
- Prefer KServe Standard mode for the local cluster. Use existing storage and secret delivery where compatible; measure incremental memory and start-up cost before keeping the stack active by default.

## Contract

| Result | Meaning | Stored as a judgement? |
| --- | --- | --- |
| `E`, `S`, `C`, `I` | Explicit ESCI label from a synthetic source or a model | Yes, with source and provenance |
| `abstain` | Model declines to label the pair | No; retain an inference-attempt receipt |
| `unjudged` | Service has no label after lookup and resolution | No |
| `inference_error` | KServe call or model loading failed | No; retain an error receipt |

The service lookup key includes the catalogue and query-suite identities, query and product IDs, locale and rubric version. Model results additionally record the exact registered-model version, artefact identity and input hashes. The existing evaluator's numeric grade mapping is versioned with the rubric; no new grade is assigned to an abstention.

## Evaluation sequence

1. Capture baseline and candidate API observations against the same frozen catalogue and query suite.
2. Form the unique union of returned query-product pairs through the deepest metric cut-off requested by the evaluation specification.
3. Resolve that pool in bounded batches: stored labels first, KServe for misses. Record labelled, abstained and failed counts and per-side coverage.
4. Publish one immutable judgement-set manifest and an attempt report, each tied to the observation hash and pinned dependencies.
5. Score both sides with the same judgement-set hash. Retain the observation, resolution, snapshot and evaluation hashes together.
6. For a later recall set, create another snapshot and rescore both sides. Retain earlier reports.

## Batches and acceptance

| Batch | Implementation | Acceptance |
| --- | --- | --- |
| 1. Contract and integration spike | Model schema and all-abstaining MLflow pyfunc; test registered-version retrieval through a KServe custom storage initializer; validate artefact-store compatibility and measure resources | Exact version loads in KServe and returns `abstain`; no judgement is created |
| 2. Registry and serving | Deploy MLflow metadata/artefact storage, KServe Standard mode, initializer and pinned InferenceService through the lab's Kubernetes/GitOps path | Clean bootstrap can register and serve the model; alias movement cannot change a running pinned version |
| 3. Judgement service | Stored-label lookup, batch gap resolution, bounded inference, provenance and attempt receipts; synthetic source import | Stored labels win; misses call KServe; abstentions remain unjudged; failures stay explicit |
| 4. Evaluation integration | Pool both result sets, resolve gaps, freeze a new judgement snapshot, score both sides; expose coverage and snapshot lineage | A recall change can add required pairs; both sides are rescored against the same immutable snapshot |
| 5. Reference documentation | Update contract, operating guide, design and diagrams, including the two-phase evaluation and model promotion path | A reader can trace a pair from observation through resolution to a frozen report |

Finish each batch with evidence, a commit and a reviewable PR. The user has authorised autonomous progression through this plan; do not merge a branch into protected main without its normal review path.

## References

- [Independent data and evaluation contracts](../data-evaluation-contracts.md)
- [Developer evaluation loop](developer-evaluation-loop.md)
- [KServe custom storage initializers](https://kserve.github.io/website/docs/model-serving/storage/storage-containers)
- [KServe MLflow runtime](https://kserve.github.io/website/docs/model-serving/predictive-inference/frameworks/mlflow)
- [MLflow registry workflow](https://mlflow.org/docs/latest/ml/model-registry/workflow)
