# Gatling reports on failed operation pages

## Outcome

Show native Gatling HTML and ZIP links directly on terminal operation pages,
including failed checks. Group links by variant and side. Explain missing
archives, skipped checks and temporarily unavailable evidence.

Operation `5bbace1bcc2fba3db88d4828abeaa144` retained both driver archives after
the candidate missed its latency budgets. The detailed comparison already
linked them, but the failed operation page did not. The new page reads those
existing report references; no rerun or evidence migration is needed.

## Verification

- In-memory JavaScript tests cover failed, completed and interrupted operations,
  individual missing archives, skipped checks, unavailable evidence and legacy
  paired reports. Active operations do not fetch terminal reports.
- All 27 Gatling archive and control API tests pass, including failed-operation
  archive access, hash checks and operation permissions.
- Evaluation history tests and JavaScript syntax checks pass.

These are automated checks. The changed page has not yet been activated or
visually checked in the running lab. Performance budgets and retained evidence
are unchanged.

## Next step

Review and merge this batch, then activate the control runtime when idle. Open
the failed operation and follow its baseline and candidate report links before
resuming the walkthrough.
