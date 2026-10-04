# Activate and rehearse the developer workflow

Install the accepted feedback batches, then demonstrate a fresh source PR,
additional queries and a manually submitted preview. Keep the deployed search
release unchanged unless a separate deployment proposal is approved.

## Constraints

- Human acceptance precedes source/main merges and runtime installation.
- Preserve the walkthrough rewrite, frozen evidence, signing keys and existing
  deployment approval policy. No Gitea version upgrade is planned.
- Add no fallback for old source configurations. The source's current contract
  must be on main before automatic comparisons use it as their baseline.
- Keep eight workers, fresh requests and the existing Gatling production gate.
  Report-only queries cannot satisfy the standard suite or a required extra set.

## Sequence

1. Review source PR #27's passing release and relevance checks. Its base predates
   the new remote client and configuration files, so its fresh exact-image
   evidence used the existing operator publication procedure. See the
   [verification record](../research/evidence/walkthrough-feedback-verification.md).
2. After acceptance, merge the updated source/template PR and the lab review stack. Build
   and install the accepted control image using `lab/install_control_oidc.py
   --image <digest-pinned-image>`. Check the existing deployment and PVC first.
3. Run `lab/setup_delivery_actions.py` and `lab/setup_relevance_gate.py` from
   the lab repository root with `LAB_STATE_DIR` pointing to retained lab state.
   Confirm External Secrets is healthy before removing old source signing
   secrets. Reconfigure the proxy to admit verified bearer tokens. Confirm the
   configured client/code/policy pins match source main's exact published bytes.
4. Apply the accepted allowlist correction with `lab/update_gitea_allowlist.py`.
   Inspect the effective sections without printing secret values; confirm the
   warning disappears and Gitea's version remains unchanged.
5. Open a demonstration PR with a report-only additional query set. Record its
   build, automatically created previews, public report links, standard/extra
   metrics, combined weighting, similarity values and required backend status.
6. Submit a preview through the manual workflow and the workstation client.
   Exercise `merge-reviewed`, `verify`, `propose-rollback` and `gate-check`
   through Actions too. A merge must reject missing or stale separate approval;
   a rollback must create fresh direction-specific evidence before its PR.
   Check device sign-in, machine scope, TLS verification, progress and retry
   safety. A completed submission workflow must not claim evaluation success.
7. Exercise a required extra set with reviewed labels and a deliberate failing
   case. Verify the failure remains independent of the standard demo allowance.
   Close the demonstration PR without deploying it.

## Acceptance and evidence

| Check | Required result |
| --- | --- |
| Exact commit | A new source commit creates fresh evidence; a moved head cannot receive an earlier verdict |
| Extra queries | Separate and combined metrics; report-only by default; required sets checked independently |
| Credentials | Source Actions receives its scoped delivery client, not coordinator signing keys |
| Remote actions | Public URLs and durable progress; duplicate submissions do not repeat promotion |
| Pacing | Eight workers, per-API diagnostics and visible terminal failures; Gatling unchanged |
| Delivery | Actions proposes, merges after separate exact-head approval and verifies; rollback retains fresh evidence. No developer kubectl step |
| Gitea | Supported allowlist section and unchanged application version |

Retain live receipts separately from isolated software tests. Review the current
guides and diagrams against the observed workflow, then update the roadmap and
next detailed plan with any remaining issue.

## References

- [Remote delivery commands](../remote-delivery.md)
- [Operator evidence publication](../evaluation-runbook.md)
- [Feedback batches](walkthrough-feedback.md)
- [Pacing evidence](../research/evidence/evaluation-pacing.md)
- `lab/setup_delivery_actions.py`, `lab/setup_relevance_gate.py`
- `lab/install_control_oidc.py`, `lab/update_gitea_allowlist.py`
