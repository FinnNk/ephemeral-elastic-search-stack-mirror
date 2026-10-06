# Production release walkthrough

## Intent

Take the next relevancy change from verified staging through the blue–green release UI. Record preparation, final comparison, approval and route-switch timings.

## Preconditions and constraints

- Accept the [implementation batch](production-blue-green.md) first.
- Use a merged source build that differs from active production, already promoted and verified in staging.
- Keep the same concrete catalogue/index and its write block throughout the release.
- Use the pinned ESCI fixture for simulated recent queries. Model labels retain their existing provenance and qualification status.
- Keep the required normal/peak Gatling gate. Human review remains required for both desired-state PRs.
- Perform developer actions through the control UI and Gitea. Leave operator recovery commands in the administration guide.

## Steps and acceptance criteria

| Step | Evidence to retain |
| --- | --- |
| Prepare and approve candidate | Preparation PR pins staging; stable production URL still reaches the original slot |
| Deploy approved preparation | Argo verifies both exact images and shared catalogue; candidate slot is ready |
| Check and request release | Full gates pass; final capture calls active/candidate services and retains one shared label snapshot |
| Review final comparison | Friendly report shows nDCG, deltas/significance, RBO/Jaccard, coverage, inference outcomes and timings |
| Approve and deploy route switch | Exact-head approval; stable service reaches the candidate's ready Pods; prior slot remains available |
| Verify storefront | Production URL returns the intended result change; source commit and release fingerprint match |

Rollback remains available through a separately reviewed request. Demonstrate it only if requested; it runs the full load gate again.

## Production load recovery

On 6 October, the first full gate completed but the build 108 baseline missed
the peak budget and was OOM-killed at its 96 MiB limit. Build 158 passed.
Both evaluation previews now use a separately committed 192 MiB diagnostic
configuration, with CPU unchanged at 250m. Active production and the prepared
production slots keep their original resource configuration.

The short screen completed with no failures or restarts, but both sides missed
peak latency limits. See the [investigation evidence](../research/evidence/production-load-memory-2026-10-06.md).
Next, isolate CPU throttling and shared-node contention with equal resources and
placement before spending another full-gate run. The screen is not a gate pass.

Run a short matched Gatling screen using retained ESCI traffic, recording memory,
CPU throttling, failures and restarts. This diagnostic cannot satisfy or replace
the full production gate. If it passes, repeat the unchanged full gate from the
release UI; retain the failed evidence and the resource configuration used for
the new run. If failures persist, investigate the measured bottleneck before
changing further resources or policy.

Acceptance for the next release attempt: complete normal and peak evidence,
no API restarts, both sides within the existing budgets, then the final shared
judgement comparison and a human-approved route switch. Assess any permanent
resource-default change in a separate reviewed batch.

## More information

- [Release to production](../delivery.md#release-to-production): developer instructions.
- `lab/production_release.py`: slot and final-evidence contracts.
- `lab/verify_production_slots.py`: isolated four-query topology rehearsal.
- [Roadmap](roadmap.md): accepted batches and outstanding validation.
