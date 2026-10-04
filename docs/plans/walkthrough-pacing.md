# Adaptive evaluation request pacing

Keep eight capture workers and reduce avoidable failures when an API is
temporarily overloaded. Gatling continues to own load-test arrival rates.

## Constraints

- Every evaluation searches freshly. Do not reuse results or suppress repeated
  searches across suites or runs.
- Pace each API independently. Retry only transient failures with a finite
  attempt/time budget. Preserve failed cases and execution diagnostics.
- Start without a fixed rate cap. Slow down on overload and recover gradually
  after successful responses. Do not reinterpret a slower API as better performance.
- Assess open-source components before adding a small custom controller. Avoid
  an asynchronous rewrite or dependencies that make capture Jobs harder to run.

## Acceptance

1. Compare fixed retry and adaptive pacing against an isolated HTTP service
   with a repeatable overload/recovery schedule. Retain attempts, failures and
   elapsed time; report the normal-service overhead too.
2. Verify eight workers, per-endpoint isolation, bounded recovery, retry-after
   handling and terminal errors. A partial capture never becomes complete.
3. Preserve source/query/filter/variant identities and add pacing diagnostics
   to retained execution records. Do not change Gatling's workers or phases.
4. Publish the source template batch, preserve the walkthrough's rewrite and
   tests, and document activation checks after human acceptance. Update diagrams
   from their editable sources and inspect their regenerated views.

## References

- [Feedback plan](walkthrough-feedback.md)
- [Remote delivery](../remote-delivery.md)
- `lab/variant_capture_worker.py`, `lab/evaluation_job.py`
- `lab/experiments/evaluation-throughput/`
- `lab/delivery/bootstrap/`, `lab/search-app/`
