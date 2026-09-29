# Control UI integration for pooled judgement resolution

## Intent

Expose the verified two-stage evaluation as a finite in-cluster action from a retained comparison. An engineer selects an observation set and exact model version, starts resolution, then inspects coverage, attempts, a frozen judgement set and the report in the control UI. Keep the existing selected-judgement comparison path available.

## Constraints

- Reuse the `judgements/` contract and offline scorer. The control API orchestrates a Job; it does not embed inference, grade mapping or metric logic.
- Pin the observation, catalogue, query suite, original labels, specification, evaluator image and numbered model artefact. Fail closed if any selected input differs.
- A Job contacts the judgement API and Blob, then publishes content-addressed results. It never calls a Search API after observation capture.
- A model failure makes the report incomplete. Abstention remains unknown and coverage policy still decides whether a relevance claim is usable.
- Keep credentials in ESO-backed Secrets. Use the existing control identity, job quotas, retained links and OTel outcome-event pattern. Avoid a model service per environment.

## Acceptance

1. From the UI, a user can resolve gaps for a retained B/C observation and see the exact input/model pins before launch.
2. A finite Job publishes one immutable snapshot, attempt receipt and report; both sides reference the same judgement-set hash.
3. Repeating the same request returns the retained result or a byte-identical run. A changed recall set creates a different snapshot without altering the earlier one.
4. Stored labels, abstention, model failure, cancellation and low coverage are distinct in the UI and API. Delivery policy rejects incomplete or insufficient evidence.
5. The 10k and 1M synthetic fixtures pass an in-cluster run. Test a candidate-only recall pair and a model outage; retain hashes and timings.

## Where to look

- [Current judgement workflow](../judgement-resolution.md)
- [Implementation and evidence](mlflow-kserve-judgement-coverage.md)
- [Independent data and evaluation contracts](../data-evaluation-contracts.md)
- `lab/control_comparison.py`, `lab/control_api.py`, `evaluation/run_job.py`, `evaluation/offline.py`, `judgements/evaluate.py`
