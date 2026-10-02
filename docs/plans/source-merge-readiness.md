# Prepare source PRs for merge

Source PRs #13–#15 are now merged to source main. This completed plan and its
evidence record are retained for review; no source merge steps remain.

## Intent

Make the three source implementation PRs pass their required checks without
changing search behaviour or weakening the relevance policy.

## Constraints and acceptance

| Work | Acceptance |
| --- | --- |
| Check the stack | Record each PR head, base and latest required check; distinguish the negative test fixture |
| Supply missing evidence | Fresh 1,000-query comparisons use the exact source images and preceding-version baselines; report and build receipt match the evaluated head |
| Evaluate historical API contracts | Pin the pre-filter capture worker explicitly for the no-filter suite; add no compatibility fallback to current runtime |
| Publish and recheck | Sign the reports, publish to Nexus and rerun the protected relevance checks; no override or policy change |
| Retain evidence | Archive observations, configuration and worker hashes, verdicts and CI status; describe synthetic-label limits |
| Prepare review | Update the PR notes and roadmap; leave source merges to the user; explain sequential squash handling |

The filter PR's existing real Elasticsearch/browser checks cover the new filtered
requests. The frozen gate suite checks preservation for requests without filters;
these are distinct checks.

See [source readiness evidence](../research/evidence/source-merge-readiness.md),
[delivery](../delivery.md) and [variant evaluation](../variant-evaluation.md).
After this batch, the next detailed implementation plan remains
[canonical HTTPS control sessions](reference-https-control-session.md).
