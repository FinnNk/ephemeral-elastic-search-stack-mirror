# Codebase and documentation simplicity review

## Conclusion

The current operating documentation contains substantial implementation history
that makes the system harder to use. The code has local areas of accumulated
complexity, especially request routing and UI orchestration, but a wholesale
rewrite or removal of old-format readers would be unsafe. Retained releases,
reports and rollback definitions are supported inputs, not dead code.

This batch fixes the clearest documentation drift and makes one bounded
comparison refactor. It does not certify every file as clean, change the live
lab or close the follow-up work below.

## Scope and evidence

Reviewed main at `b63f3b52bcdac59b5f2c3867eb8cb405af2f7eb1`, independently of the
pending preview feature. The pass used the tracked file inventory, the last
100 commits and a static function/module inventory to choose inspection targets.
Size and change frequency were treated as leads, not automatic reasons to split.

Inspected the control API, lifecycle ownership, comparison capture/scoring,
release operation queue, gate/query-set handling, release plans, production
release flow and fresh-install/observability boundaries. Read the README,
roadmap, environment guide, delivery/control procedures, Mac/transfer guidance,
fresh-install guidance and diagram ownership/rebuild instructions.

The 17 large interactive HTML files contain the delivered Archify viewer.
Their size is expected generated output. Editable JSON/DSL specifications and
the pinned renderer are the maintenance boundary; hand-editing or splitting
those generated files would add work without simplifying the source model.

This was a targeted source and documentation review, not an exhaustive
line-by-line audit of all research scripts, vendored assets, separate source
repositories or pending PRs. It ran no live migration, comparison or deployment.

## Findings and action

### 1. Current status was an implementation diary — corrected

The roadmap mixed completed batches with repeated “review and activate” and
“next” instructions. It described different builds as current in different
sections. A reader could not reliably choose the next operation.

Moved the previous text intact into a clearly labelled
[historical record](../plans/roadmap-history-2026-10-16.md), in the same directory
so its relative links retain their meaning. The current roadmap now identifies
ongoing work, operating guides and remaining acceptance checks. The release
dashboard and verification receipts own observed deployment state.

### 2. The environment guide contradicted current controls — corrected

The guide used obsolete **Frozen release**, **Index** and **Delete** labels,
said delivery previews could not be expired from the page, and described queries
as part of catalogue restoration.

Aligned it with **Catalogue and rewrite data**, **Index type**, retained index
selection and **Expire now**. Explained the distinct ephemeral deletion and
queued delivery-preview expiry paths, including the stable environments that
have no expiry controls. Query selection remains a comparison decision.

### 3. Operator instructions mixed host and container assumptions — corrected

The control smoke commands invoked `uv run --locked` inside the image, which
installs its pinned dependencies into system Python and does not copy the host
project files. They now use the installed container Python. Host commands
continue to use the locked uv environment.

The Mac guide described one source host's resource inventory as current for all
transfers. It now directs fresh operators to fresh-install allocations and
transfer operators to their actual inventory. The observability and diagram
guides distinguish the dedicated-worker and existing-node demo profiles.

### 4. Comparison scoring had accumulated inside capture orchestration — simplified

`evaluate_pair` combined input checks, capture, scoring, coverage, diagnostic
replay and report storage in one 225-line function. Three identical mode and
completion conditions separated parts of the same scoring operation.

Moved those calculations into `relevance_summary` in the same module, with an
explicit result object. Captured rankings are constructed once for score,
per-query nDCG and significance. The caller still decides whether results are
complete enough to score; the helper annotates those rows as before. No new
service, configurable strategy or forwarding compatibility layer was added.

Compared the original and refactored calculations on mixed provenance,
fully judged, unjudged and empty-result fixtures. JSON summaries and annotated
rows matched exactly. Existing comparison regression tests also passed.

### 5. Exception handling obscured the expected failure — simplified

Release-plan ancestry discovery caught every exception and then checked whether
it was a Gitea 404. Catalogue bootstrap did the same for an existing Azure
container. They now catch the relevant exception type directly. Missing historic
selections and existing containers retain their handling; unrelated provider
failures still propagate. A focused test covers missing, forbidden and
unexpected provider failures.

### 6. HTTP routing and compressed UI code remain hotspots — follow-up

`control_api.py` has a 288-line GET dispatcher and changed in 16 of the sampled
commits. `control-ui.html` and `delivery_results.js` also change frequently and
contain dense orchestration and rendering code. Finding a state transition or
review rule takes more effort than it should.

Extract one route or rendering responsibility at a time. Keep the existing
public entry points, authentication order, report ownership/hash checks and
operation response shapes. Do not introduce a generic routing/plugin framework
or rewrite all pages at once. The next batch below begins with read-only report
serving because it has a concrete responsibility and an existing API test net.

### 7. Supported history is not the same as unnecessary history — retained

Keep these boundaries:

- Recipe format 1/2 readers and retained source-bundle checks support historical
  rebuilds and rollbacks. Stop producing an old format before considering its
  removal, then inventory retained consumers and provide an explicit migration.
- Standalone lifecycle environments and GitOps delivery environments have
  different ownership and mutation rules. Their shared UI needs clear names;
  combining their stores or controllers would change behaviour.
- Canonical JSON used for fingerprints, manifests and evidence has different
  newline/encoding contracts. Identical-looking helpers cannot be unified by
  name alone without invalidating existing hashes.
- Source bootstrap templates and generated copies intentionally represent the
  same deployed contract. Verify synchronisation; do not replace them with a
  runtime dependency on this workstation checkout.
- Recovery helpers for retained installations remain useful. Fresh setup should
  call its current installation path, with historical recovery procedures kept
  in troubleshooting rather than the normal task sequence.

## Verification and limits

All 122 focused locked-uv tests passed. The cleanup regression suite covers
control comparisons, target identities,
comparison evaluation, release plans, fresh application/foundation setup,
control API access, delivery gates and input selection. Exact scoring parity
was checked separately against the original code on four fixtures.

After reconciling merged preview changes on 18 October, all 176 combined
cleanup and preview tests passed. JavaScript syntax, local links, UTF-8 and
conflict-marker checks also passed. No live activation was performed.

Local tests establish fixture behaviour, not native Mac installation, Docker
restart recovery, judgement accuracy or a fresh full promotion. Those acceptance
checks remain on the roadmap. Documentation review compared instructions with
current labels, source and container build files; it did not execute mutating
runbook commands against the live lab.

## Next detailed plan

1. Review and accept this cleanup after the merged preview changes (#44/#220).
2. Extract operation/comparison report serving from the HTTP dispatcher while
   preserving authentication, owner checks, content negotiation and hashes.
   Run the API/report test net before and after the split.
3. Separate evaluation-progress rendering from final evidence/report rendering
   in `delivery_results.js`. Preserve recorded phases, links on failed runs and
   refresh behaviour; verify actual browser fixtures.
4. Review the two environment creation paths behind a shared presentation
   contract. Keep their separate ownership and lease semantics explicit.
5. After those seams are established, reassess operation dispatch and installer
   stages using actual change coupling. Avoid a new abstraction unless it
   removes repeated decisions or makes a correctness boundary easier to inspect.

Each code refactor is a separate reviewable batch with behaviour checks. None
requires changing gate budgets, regenerating evidence or redeploying the lab
merely to complete a source review.
