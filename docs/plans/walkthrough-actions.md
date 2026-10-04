# Remote developer operations

Run previews, comparisons and promotion proposals from Actions or a workstation
without kubectl. Preserve the coordinator's exclusive delivery slot and reviewed
Git deployment path.

## Intent and constraints

- Expose bounded, authenticated operations through the control API. Persist
  requests, progress, results and identity on the control PVC. Reject unknown
  commands; never accept arbitrary shell arguments or server-side paths.
- Use existing OIDC for people and a scoped service credential for protected
  Actions. Keep signing credentials inside the coordinator.
- A portable Python client submits an operation and follows progress, public
  preview URLs and report links. TLS verification stays enabled.
- Manual workflows create a preview, compare successful builds or evaluate and
  propose a promotion. A production proposal requires full Gatling evidence.
- The protected relevance workflow waits for the exact source build, requests a
  fresh comparison, publishes signed evidence and then evaluates the gate.
  A moved PR head cannot publish evidence as the current head.
- Read selection and query files from the exact commit. Additional suites use
  the frozen contracts from the preceding batch.

## Acceptance

Verify authentication, reader rejection, duplicate submission, operation failure,
busy-slot recovery, immutable receipt signing and stale-source rejection. Exercise
the HTTP client against the real handler with isolated state. Add manual workflows
using functionality common to Gitea and GitHub Actions. Update the source and lab
guides and delivery workflow diagrams. Retain live evidence separately from tests.

## References

- [Feedback plan](walkthrough-feedback.md)
- [Query-set contract](walkthrough-query-sets.md)
- `lab/control_api.py`, `lab/control_oidc.py`, `lab/delivery_cli.py`
- `lab/delivery_release.py`, `lab/variant_gate.py`, `evaluation/query_sets.py`
- `lab/delivery/workflows/`, `lab/setup_delivery.py`
