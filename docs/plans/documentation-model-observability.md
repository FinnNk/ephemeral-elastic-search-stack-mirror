# Documentation D3: models and observability

## Intent

Help the model operator package, qualify and activate a model, and help an engineer investigate search and judgement behaviour using connected telemetry.

## Constraints

- Apply the [authorship guidance](../technical-authorship.md). Keep current procedures separate from dated evidence.
- Do not imply an abstaining model provides accuracy evidence, input-selection shift proves model drift, or interval charts establish seven-day SLO compliance.
- Preserve model qualification requirements and provider limits. Do not activate models, invite users or change telemetry services solely for an editorial check.
- Reuse screenshots only when they show a useful step; credentials and private artefacts must remain excluded.

## Work

1. Check model packaging and activation instructions against scripts, manifests and CLI help. Separate obtaining assets, creating an immutable package, qualification and serving.
2. Review signal names, bounded attributes, SLO arithmetic and unknown-on-gap behaviour against source and tests.
3. Put current SigNoz access first. Give a short metric → trace → log investigation path, followed by dashboard interpretation and diagnosis.
4. Explain finite arrival ledgers, readiness probes and seven-day assessment without presenting mock fixtures as live coverage.
5. Check New Relic export settings and describe the remaining real-provider validation.
6. Inspect rendered pages, links and related judgement/evaluation guides; record which commands and UI paths were actually checked.

## Acceptance criteria

- Every procedure has prerequisites, obtainable inputs, complete commands, outputs and recovery.
- Packaging, registry publication and serving activation are distinct.
- Engineers can choose the right dashboard and understand missing data, failure rates, coverage and shift signals.
- Current access and documented signal contracts match the implementation.
- Historical measurements retain their conditions; unverified native/cloud behaviour is explicit.

## Sources

- [Model installation](../esci-model-installation.md), [judgement resolution](../judgement-resolution.md).
- [Signal contract](../observability-foundation.md), [SigNoz operation](../observability-backend.md).
- `judgements/package_*`, `judgements/kubernetes/`, `lab/observability/`, model/dashboard installers and actual CLI help.
- [Review findings](../reviews/documentation-2026-10-01.md), [remediation sequence](documentation-authorship.md), dated model/observability evidence under `docs/research/evidence/`.

Complete this batch with a PR, roadmap update and a detailed D4 design/navigation plan.
