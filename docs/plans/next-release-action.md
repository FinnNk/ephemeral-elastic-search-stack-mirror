# Make the primary release control show the next action

## Behaviour

For each selected stage, identify the latest check attempt by its creation time
within the selected release's bound activity. Do not mistake an operation on
another target, or a later update to an older attempt, for a new attempt.

Show the original check action before the first attempt, **View progress** while
queued/running, **Run checks again** after failure/interruption, and **Review
proposal** when a review remains open. Keep the latest outcome, time, error and
attempt link beside the primary control. Existing access restrictions, stage
prerequisites and approval checks remain authoritative.

## Submission handling

Progress and review controls navigate without submitting a request. The server
also rejects a new command while that action is navigation-only. A retry key
includes the failed attempt's identity, making the first retry a new operation
while repeated transport submissions reuse that operation. No retry field is
added to the persisted request or release binding. After submission, update the
control immediately; periodic refreshes obtain the authoritative latest state.

## Validation

Thirty-one Python release/submission tests passed. The Chrome fixture checks
initial submission, stable transport retry keys, direct retry after reload,
progress/review navigation without POSTs, immediate control updates, escaped
error text, permissions, keyboard use and mobile layout.

Candidate logic was also run in an isolated read-only process against the live
build-184 snapshot. It selected **View progress** for running Integration attempt
`e3393364eadc2251549db710195022da`. No operation was submitted or interrupted.

## Next action

Review and merge this batch. Activate when all current operations are idle,
then refresh the release dashboard. Continue the walkthrough from the primary
control indicated by the latest evidence and review state.
