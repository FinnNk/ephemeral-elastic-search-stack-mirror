# Complete fresh source comparison inputs

The Mac delivery watcher failed before scoring because the exact candidate
commit lacked `gate/selection.json`. The fresh source seed copied evaluation
settings and policies but omitted the required variant selection.

## Repair

Seed `ranker-a` with `preserve-results`, matching the supplied identical ranking
configurations. Deliberate ranking changes must declare `ranking-change`.
Preserve existing source repositories and require their missing files to be
added through a branch and PR.

Retain Gitea HTTP status in a typed adapter error. Translate a 404 for either
required gate input into a bounded public recovery message. Other provider
errors remain private; no missing-file fallback changes the exact-commit check.

## Verification and next step

Run the source seed, comparison and operation fixture suites. Check that the
seeded selection names an existing configuration, existing human selections
survive, missing inputs explain recovery and arbitrary provider messages stay
out of public operation records.

Result: all 22 focused fixture tests passed on Windows. The seed was exercised
in a temporary repository with remote writes mocked; operation tests exercised
local HTTP and SQLite state. No live cluster or Mac repository was changed.

After review and merge, pull the installer for the clean Mac rehearsal. Add
the selection file to the current Mac source PR and push to start a new
comparison. The public error improvement needs an updated control runtime;
adding the file fixes this failure in the existing runtime. Native Mac rerun
and end-to-end comparison acceptance remain outstanding.
