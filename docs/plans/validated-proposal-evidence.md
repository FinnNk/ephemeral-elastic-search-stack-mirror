# Build proposal details from validated evidence

PR #185 corrects the local evidence-reference file. Inspection before live
recovery found another instance of the same contract error: proposal construction
read baseline and variant details directly from that reference. Its validation
already returns the hash-verified report, but the caller discarded it.

Use the validated report for the baseline, per-variant summaries and final
production checks. Keep only the original hash/blob reference as the proposal's
evidence link. No gate or approval requirement changes.

## Verification and next step

The new fixture follows the recorded evaluation reference through CLI dispatch,
proposal file creation and PR description construction, including the explicit
baseline, candidate intent and storage reference. External storage, Git and
provider writes are mocked; proposal construction itself runs. All 50 delivery,
variant-selection and production-gate fixtures pass in the locked Windows uv
environment.

PR #185 is active. Review this follow-up before retrying proposal creation.
Revalidate the retained passing build 184 evidence against the current target
immediately before recovery. Preserve both failed operations and their artefacts;
create a separate recovery record linked to the new proposal. Human approval
and deployment remain the next walkthrough steps.
