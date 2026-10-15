# Restore functional capture completion detection

## Observed failure

Operation `47383bbb3db68db96789e19c1f142b56` failed both standard functional
captures with a 300-second timeout and zero collected results. During the run,
the result-regression capture Job was already Complete after 35 seconds while
the coordinator continued reporting that it was waiting for the worker.

In the deployed client, adding `kubectl --request-timeout=10s` caused a fallback
to `http://localhost:8080`, despite the Pod having in-cluster service-account
configuration. The identical authenticated Job read succeeded without that
override. The new progress poll swallowed these command failures as an empty
Job status and waited until its deadline.

The same operation's retained performance check passed: baseline p95 101 ms,
candidate p95 107 ms, 60 measured requests per side and no failed measured
requests. This was a separate capture-control failure, not a performance-budget
failure. The older failed reports remain intact.

## Fix and validation

Bound the subprocess in Python rather than changing kubectl request settings.
Keep the finite 300-second capture wait. Retry status-read failures up to three
consecutive attempts with explicit progress, then fail with a coordinator-access
error. Read completion before optional logs; unavailable log samples must not
hide completion or Job failure.

Forty-one affected tests passed in the locked uv environment. Regression tests
cover command timeout propagation without CLI overrides, successful completion,
three failed reads, process timeouts and optional log timeouts.

An isolated process in the running API Pod loaded the candidate modules in memory
and ran a two-query capture against the existing previews. It finished in 5.623
seconds, returned both queries successfully for both APIs, detected completion
and removed its Job and ConfigMap. The baseline needed two transient retries:
four successful responses came from six total HTTP attempts. This test performed
no scoring, inference or load test, and did not deploy the unmerged modules.

## Next action

Review and merge this batch, then activate when the coordinator is idle. Start
a fresh Integration attempt through the release dashboard. The isolated check
verifies completion detection; the full functional, relevance, additional-query
and performance gates still need their normal complete evidence.
