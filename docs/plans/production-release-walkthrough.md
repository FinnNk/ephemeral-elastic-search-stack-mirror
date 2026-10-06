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

## More information

- [Release to production](../delivery.md#release-to-production): developer instructions.
- `lab/production_release.py`: slot and final-evidence contracts.
- `lab/verify_production_slots.py`: isolated four-query topology rehearsal.
- [Roadmap](roadmap.md): accepted batches and outstanding validation.
