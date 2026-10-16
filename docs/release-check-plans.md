# Review a release check plan

Use a plan when several source changes have accumulated before a promotion.
The plan records which additional query sets measure the combined change against
the current destination, and the expected intent for every candidate variant.
All standard query sets remain mandatory, independently of this selection.

## Review and record

1. Open the release dashboard, select the successful merged-source build and
   its next stage: Integration or Staging. For Production, first prepare and
   deploy the inactive candidate using verified Staging.
2. Select **Suggest checks from accumulated changes**. Follow the plan operation,
   then refresh the dashboard after it completes.
3. Review the exact baseline and candidate, accumulated commit list and mandatory
   sets. The suggestion includes additional sets declared at the baseline and
   at every intervening source commit, even when later commits removed them.
   Different contents under the same name appear separately, with pinned files.
4. Confirm each candidate variant's release intent. The suggestion conservatively
   uses an intentional ranking change if any accumulated declaration does so.
   Choose the intent appropriate to the complete change against this baseline;
   the plan cannot change the build's selected variants or configurations.
5. Mark each suggested additional set **Required**, **Report only**, or
   **Retire / supersede**. Explain retirements and reductions of inherited
   requirements. Add existing evaluation files from the candidate commit if
   necessary. Required sets need a matching reviewed judgement file. Explain
   why the complete selection covers the release in the overall review reason.
6. Select **Create plan PR for review**. The coordinator creates a pretty-printed
   JSON file in `delivery-state/release-check-plans/` and links its Gitea PR.
   Review the changes and approve the exact head as the named administrator who
   proposed the plan. A bot or delivery service account cannot provide this review.
7. Refresh the dashboard and select **Record approval and start checks**. The
   coordinator verifies approval, records the plan and queues one check attempt.
   You can leave the page; the queued checks are durable. To defer checks, choose
   **Record approved plan only**, then use **Check and propose** later.
8. Follow the promotion-check link from the completed plan operation. Review and
   approve the separate deployment proposal, then deploy through the usual flow.

Plan operations have progress links in the dashboard and release activity. The
editor retains unsent selections during refreshes within the current page; save
them as a plan PR before leaving. Opening a new browser session does not recover
unsaved edits. Recorded plans can be recovered from source control independently
of operation history.

## What remains mandatory

The trusted lab policy supplies at least one standard set for the catalogue.
Every selected variant must pass every standard set and every required additional
set, or meet the existing explicitly allowed exception policy. Report-only sets
remain informational. Combined averages cannot open a gate. A plan cannot remove
standard sets, change their labels, or relax the gate policy.

The source PR's gate still uses its own declared intents and additional sets.
Release plans apply to promotions, where the candidate may include several PRs
relative to the destination. Declaring a set in source makes it a reviewable
suggestion for later plans; it does not establish that it sufficiently measures
every future combination of changes. The reviewer makes that judgement.

## Changes and invalidation

Each plan pins the full candidate and destination deployments, the named default
baseline configuration, protected standard group, policy hash, historical query
and judgement contents, dispositions, reasons and reviewer. Evidence records the
plan PR, exact head, merged commit and approval. A new destination, candidate,
policy or newly recorded replacement plan requires a fresh reviewed plan and
fresh evidence. A draft replacement alone does not amend a recorded plan.

When the exact release is still deployed in the immediately preceding stage,
the suggestion carries forward its reviewed intents and query-set choices. It
links the previous plan and keeps the editor available for destination-specific
changes. New required declarations remain required. Different candidate data,
configuration, policy or standard sets prevent reuse. Unlabelled advisory copies
are suggested for retirement when a labelled version of the same queries exists;
the plan records the reviewer’s choice and reason.

Review and approve a separate plan for each destination: carried selections do
not transfer approval or evidence across different baselines. Production's load gate and final
active-versus-candidate comparison share the same reviewed intents. Rollback
requires a plan for the retained inactive release against active production.

The coordinator inspects at most 250 accumulated commits and permits eight active
additional sets. It stops explicitly when these bounds are exceeded. Review and
retire superseded suites rather than silently dropping them. Missing historical
selection files and divergent Git histories are displayed for review. Suggestions
need access to the retained source repository and its pinned query files.

## Existing labs

After activation, historical operation reports remain readable. New promotion
checks require a plan, including calls through Actions or the production page.
Pre-plan evidence cannot authorise a new deployment: record a plan, rerun checks
and use the new deployment proposal. Existing deployments are retained. Fresh
installation includes the same workflow without an additional service or flag.
