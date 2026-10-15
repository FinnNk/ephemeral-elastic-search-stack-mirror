# Group evaluation progress

## Observed problem

Operation `a1558b3f2bc40257348bbf788be8378e` completed its Staging checks and
created deployment proposal 29. Its result-regression capture's last sampled
counter was 841/1,000; its separate completion event reported 1,000/1,000 with
zero failures. Relevance capture likewise sampled 822 before completing all
1,000. Both retained reports confirm `complete: true`, 1,000 completed queries
and no errors. The sneakers set captured all four queries and resolved 40
query–product pairs from cache. The retained phase list made intermediate
samples look like unfinished independent work.

## Change

Group preparation events, each query-set check and performance handover.
Combine worker startup, sampled capture updates and capture completion into one
capture step, judgement service/batch/snapshot events into one resolution step,
and scoring/significance into one scoring step. Use unnumbered task headings.
Keep the original phase entries under expandable details; retain the user's
expanded steps across refreshes. Different capture Jobs remain separate checks,
so repeated suites or variants cannot replace an earlier completed capture.

Use the final capture counter only when it was actually reported. Otherwise
retain the sampled counter and disclose the absence of a final count. Failed
queries remain visible and are included in the completed capture total. Scoring
counts identify captured inputs, not completed scoring. Query and pair units
remain distinct. No worker, evaluation, gate or retained evidence changes.

## Verification and next step

The in-memory DOM tests cover final counts replacing sampled summaries, retained
sample details, scoring inputs, judgement grouping, repeated Jobs, stale samples,
preparation grouping and status-refresh reconstruction. Eight existing capture
progress tests pass. JavaScript syntax and Git whitespace checks pass.

A browser replay uses the actual operation's retained evaluation events through
an isolated local server. It shows the final 1,000-query captures and the separate
four-query and 40-pair counts. No live check was rerun and no evidence was changed.

After review and merge, activate the runtime when idle. Reopening the existing
operation reconstructs the grouped view; no evaluation rerun is needed. This
batch is independent of the reviewed release check plan implementation.
