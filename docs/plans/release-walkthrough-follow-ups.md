# Release walkthrough follow-ups

Recorded on 16 October 2026. Implement these after the current promotion
walkthrough finishes. This batch records feedback only; it changes no controls
or release state.

## Identify releases clearly when choosing a proposal

The approved-proposal selector currently emphasises the PR number. Show a
recognisable release name alongside the version, build and PR number, and
provide a link to the release changelog. Keep the exact source commit available.
If a changelog is unavailable, say so rather than inventing a link.

Acceptance: a reviewer can distinguish proposals by the release being deployed,
read its changes and confirm the destination before selecting it. The PR remains
the reviewed deployment record; its number alone is not the release identity.

## Distinguish superseded deployments from pending deployments

An older release dashboard can say **Proposal merged; matching current rollout
is not yet observed.** even when that build was deployed and later replaced.
Build 184 was the reported example. This makes deployment history look like
unfinished work.

Acceptance: use retained verification history to distinguish never deployed,
deployed and still current, and previously deployed but superseded. Show the
previous deployment time and the current replacement release when known. A
missing current rollout alone must not imply that a verified historical
deployment never happened; uncertain history should be explicit.

## Walkthrough checkpoint

Build 204 (`1.2.2+build.204.1`, source `c83307104982`) is verified in Integration
through delivery-state proposal #31. Read-only checks found one ready replica,
Argo CD **Synced / Healthy**, and the matching frozen image and index. Staging
still runs build 158. Continue with a fresh reviewed Staging check plan.
