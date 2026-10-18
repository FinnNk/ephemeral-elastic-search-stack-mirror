# Release walkthrough follow-ups

Recorded on 16 October 2026 during the build-204 walkthrough. The text below
retains the observations and acceptance criteria at that point; its deployment
checkpoint is historical. The walkthrough has since completed. Implementation
and judgement data are reviewed separately in lab PR #219; this record changes
no controls or release state. Use the release dashboard for current deployments.

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

## Carry reviewed check selections forward

When the immediately preceding environment still serves the same verified
candidate, inherit its reviewed query selections, reasons and variant choices
for the next destination. Avoid requiring the reviewer to compose the same plan
again. Keep environment-specific amendments available and record the inherited
plan, its origin and any amendments in source control.

An unchanged preceding environment is necessary but does not prove that the
next comparison has the same scope. Recompute accumulated changes against the
destination's current baseline. Check candidate image/configuration/data,
baseline variant, query and judgement snapshots, current mandatory sets,
policy and destination-specific requirements. Show material differences and
request a focused review when they affect intent or coverage. Never silently
reuse an approval tied to another baseline or omit mandatory sets. Fresh
destination checks and deployment approval still apply.

The current walkthrough demonstrates the distinction: Integration compared
build 204 against build 194 with preserve-results intent. Staging compares the
same build against build 158, so the accumulated Redis rewrite change warrants
ranking-change intent. Query selections can carry forward while that intent
needs reconsideration.

Acceptance: unchanged, compatible selections carry forward without repeated
composition; a reviewer can inspect or amend them. Material destination
differences are explicit and require the appropriate review. Decide the precise
rules for carrying review authorisation forward during implementation; this
feedback record does not authorise bypassing the current exact-plan checks.

## Start checks when an approved plan is recorded

Consider a combined **Record plan and start checks** action, with **Record only**
available when the operator wants to run later. State before submission that it
will start relevance and performance checks and create a deployment proposal
only if the required gates pass. Deployment remains a separately approved action.

Start after the coordinator has verified exact-head approval and successfully
recorded the plan. A Gitea approval by itself must not launch work. Recheck the
candidate, target baseline and plan freshness before scheduling; if they have
changed, explain why review is needed rather than launching stale checks.

Acceptance: recording and scheduling are durable and idempotent. Duplicate
clicks or coordinator restarts return the same attempt; an active operation is
queued visibly. If recording succeeds but scheduling fails, retain the recorded
plan and offer an explicit retry without requiring another approval. Show the
new attempt and progress link immediately. Never merge or deploy a promotion
proposal automatically as a consequence of plan approval.

This is a possible workflow improvement requested during the running Staging
checks. Decide whether the combined action should be the default after the
walkthrough; no automatic start is enabled by this feedback record.

## Historical walkthrough checkpoint

Build 204 (`1.2.2+build.204.1`, source `c83307104982`) is verified in Integration
through delivery-state proposal #31. Read-only checks found one ready replica,
Argo CD **Synced / Healthy**, and the matching frozen image and index. Staging
still runs build 158. Continue with a fresh reviewed Staging check plan.
