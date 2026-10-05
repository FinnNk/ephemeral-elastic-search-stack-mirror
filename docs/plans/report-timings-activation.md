# Activate and check report timings

After acceptance, follow the [runtime update procedure](../control-runtime.md#update-an-existing-runtime)
when delivery work is idle. Keep the installed baseline.

1. Verify rollout and smoke checks.
2. Open a retained source comparison. Confirm elapsed operation time is visible;
   do not rewrite its report to add missing capture timings.
3. Open a retained Gatling check and confirm workload duration, latency and failures.
4. Confirm promotion and rollback operation results link to their retained
   evidence and verification reports identify the deployed release.
5. During the next walkthrough comparison, verify both standard and additional
   suites retain and display their capture duration and request counts.

A new comparison is required to obtain newly retained capture metadata. Do not
run a load test merely to check presentation.
