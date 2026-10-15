# Distinguish existing release attempts from new submissions

## Problem and behaviour

The dashboard reused a failed submission safely but showed only “Operation
failed”, which looked like a newly failed action. Label each response as an
existing or new attempt. State explicitly that reopening an attempt starts no
checks, and show its original submission time and recorded error.

For existing queued/running attempts, link to their progress. For terminal
attempts, link to their previous outcome. Failed or interrupted attempts expose
**Start a new attempt**, explaining that it runs the checks again using current
settings and retains the earlier result.

## Implementation and validation

Submission responses carry a transient `submission_reused` flag; it is not
persisted as an operation outcome. The operations transaction determines whether
it inserted a row, including concurrent submissions with the same key. The
dashboard's earlier deduplication path supplies the same flag. Network retries
retain their existing key; explicitly starting again obtains a fresh one.

Twenty-eight Python release/submission tests passed. The Chrome fixture checks
transport retry keys, reopening a failed attempt after a page reload, explicit
fresh submission, existing queued progress, escaped error text and mobile layout.
These checks used local fixtures and did not touch the running evaluation.

## Next action

Review and merge this batch. Activate only after the current operation has
finished, then refresh the release dashboard to load the new feedback.
