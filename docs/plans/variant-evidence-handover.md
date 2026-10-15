# Pass retained evidence references into promotion proposals

The Integration check for build 184 completed and retained passing per-variant
evidence, but proposal creation failed with `KeyError: 'blob'`. The local
`evidence-<hash>.json` file contained the complete report. Promotion expects a
reference containing `sha256` and `blob`, then verifies the stored report itself.

Save the reference, matching the existing single-comparison CLI contract.
Continue reading back the retained report before returning the reference file.
The stored report, its hash, variant checks and approval rules remain unchanged.

## Verification and recovery

The regression fixture follows the evaluation's reference file through the
actual `promote` CLI dispatch and checks that the proposal receives the hash and
blob reference. All 30 delivery gate, operation and per-variant fixtures passed
in the locked Windows uv environment. The HTTP fixture required loopback access
outside the filesystem sandbox. The tests do not establish live proposal success;
activation and retained-evidence validation follow acceptance.

The failed operation is `163f4f67879d29ace366df0eef69ef3c`. Its retained report
`b847667379ebc8ee5bb89bdd1db4f90ac41c9e14a75f620eb0807ff12d1b508f`
records baseline build 158, candidate 184 and a passing `ranker-a` ranking-change
check, completed at 2026-10-15T11:43:06Z. Read-back verified its hash; no new
desired-state PR was created. After acceptance, validate the retained evidence
against the current target and exact candidate before reusing it to create a
proposal. Keep the failed operation and original local file intact. If any
binding changed or the evidence expired, run fresh checks instead.

## Follow-up UX

The user requested clearer failed-attempt behaviour: show the failure time and
reason as a previous attempt, make **Retry checks** the primary action and let
**Check and propose** create a fresh attempt after a terminal failure. Continue
deduplicating requests while queued or running. This UX change is recorded for
the next batch; it is not implemented by this hand-off repair.
