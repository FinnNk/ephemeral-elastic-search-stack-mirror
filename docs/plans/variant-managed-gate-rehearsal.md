# Next batch: managed variant gate rehearsal

## Intent

Close the remaining integration boundary between a frozen environment and an opt-in source PR gate. Reuse the synthetic million-product index and the current variant observation contract.

## Constraints

- Create the proof variant environment through the normal desired-state and Argo CD path so `evaluation/capture.py` can verify its frozen definition and serving deployment.
- Keep one runtime default and a separately named baseline. The same API deployment may serve several pinned ranking configurations.
- Publish signed report bytes only after the exact delivery-source PR commit exists. Keep evidence in Nexus under that SHA; do not put a self-referential SHA inside the PR.
- A live low-coverage report must remain blocked. Use a clearly labelled deterministic synthetic fixture to exercise passing and bounded-exception branches; do not present fixture scores as measured live quality.
- Keep CI code and policy pinned by protected Actions variables. The runner is for trusted same-repository contributors only.
- Preserve source and Gitea PR review history. Do not merge any PR without acceptance.

## Acceptance

1. An Argo-managed definition, deployment image and index identity pass `evaluation/capture.py` for two or more named variants; a changed image or echo fails.
2. The exact source PR head SHA selects a Nexus evidence bundle. A missing or tampered bundle fails CI; a complete live report with insufficient coverage returns `blocked`.
3. A deterministic adequate-coverage fixture exercises `pass`, `decision_required` and `approved_exception` through the same CLI. The exception records authenticated reviewer, reason and measured delta.
4. CI results, source revision, report hashes and environmental limits are recorded without copying old observation formats into the current path.
5. The reference and delivery-source batches are committed and offered as PRs. Main remains unchanged until acceptance.

## Where to look

- [Live proof and limits](../research/evidence/offline-variants-million.md)
- [Frozen variant capture](../../evaluation/capture.py)
- [Merge gate](../../lab/variant_gate.py)
- [Evidence store command](../../lab/delivery/ci/variant_gate_store.py)
- [Delivery workflow](../../lab/delivery/workflows/release.yaml)
