# View retained Gatling reports

## Scope

Expose baseline and candidate native HTML reports and ZIP downloads from the
operation's promotion review and detailed performance comparison. Use the
archives already retained by the driver, including a completed driver whose
measurements failed the gate. Do not rerun a workload to add links.

## Implementation

The authenticated operation route resolves the selected variant's evidence,
performance comparison and native archive through their recorded hashes. It
serves individual ZIP members without extracting files. Archive/member size
limits and canonical member paths bound reads. HTML uses a restrictive policy
that permits local report charts and theme storage but blocks network requests,
forms, frames and workers. Report links open without an opener.

Missing driver archives are labelled unavailable. Existing gate outcomes and
immutable evidence remain authoritative.

## Validation

Twenty-five focused Python tests passed, including operation permissions,
verification of every evidence document, archive hashes, invalid paths and size
limits. The mocked Chrome operation/report fixture passed baseline/candidate
link checks and explicit unavailable states.

A read of the latest failed operation confirmed both native archives exist.
The retained candidate archive (176,695 bytes) rendered locally with the viewer's
response policy: eight overview charts and six normal-request charts, no script
errors or failed asset requests. A browser network request was blocked by that
policy. These checks read existing evidence; no load test was started.

## Review and activation

This batch follows PRs #193 and #194. Merge those batches first, then this batch.
Activate the control runtime when idle. Existing operations acquire links from
the new viewer; their evidence does not need regeneration.
