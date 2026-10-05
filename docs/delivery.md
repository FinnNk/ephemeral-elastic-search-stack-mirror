# Build, promote and roll back a release

Develop the Search API in `delivery-source`. Actions builds it and the coordinator
compares its results with the baseline. After source merge, promote the new build
through integration, staging and simulated production. Argo CD deploys reviewed
state; the coordinator checks the image, index and public API.

The lab's remote workflow is installed; see [current status](plans/roadmap.md)
for remaining validation. Developers do not need a kubeconfig. Operators install and repair
the lab using [control runtime](control-runtime.md).

![Source build, frozen comparison and merge decision](diagrams/rendered/variant-merge-gate.png)

## Make and evaluate a change

1. In `delivery-source`, create a branch, change the API or ranking settings and
   run its application tests. The [source contributors guide](../lab/delivery/bootstrap/README.md#contributors-guide)
   includes a copyable query rewrite and test.
2. Declare variants and intent in `gate/selection.json`. Use `ranking-change`
   for intentional changes, or `preserve-results` for a release expected to
   return the same products in the same order. `gate/evaluation.json` names the
   baseline and default; `configurations/` contains their settings.
3. Push and open a PR. **Reference release CI** builds its exact commit and stores
   the image, bundle and receipt in Nexus. **Offline relevance gate** submits
   a comparison; its completion alone is not a relevance verdict.
4. Open the PR comment's storefront and report links. Review relevance, label
   coverage and changed results using the [variant guide](variant-evaluation.md).
   Add report-only queries for your change, or explicitly require a labelled set.
5. Wait for `relevance-lab/merge-gate` on the current head. Every new commit needs
   fresh evidence. A bounded exception uses the [Git decision procedure](variant-evaluation.md#accept-a-bounded-regression) without changing
   scores; invalid evidence and hard blocks cannot be approved away.
6. Merge when the required checks pass. CI builds the merged commit separately.
   Use that successful run for deployment, rather than the PR-head build.

Changes confined to the two source README paths receive the
[documentation exemption](relevance-gate.md); tests and builds still run.
Source repositories default to no required approvals for the lab, while setup
preserves stricter existing rules. Deployment proposals require a separate reviewer.

## Preview or compare manually

In `delivery-source` → **Actions** → **Lab delivery** → **Run workflow**, select
**main** and choose `preview` or `compare`. Supply the successful build run ID
from its `/actions/runs/<id>` URL; compare also needs a baseline run.

The workflow prints a durable progress URL and releases the runner. Follow that
record to completion and open the returned storefront or report. Browser links
show a readable progress page with the current stage and outcome. Report pages separate relevance,
result overlap and judgement coverage. The recorded merge gate appears at the
top; a passed gate needs no relevance decision. The PR offers a decision link only
when a bounded decision is required. An old decision link for a passed gate
also shows that no decision is needed. RBO and Jaccard compare each variant with
the baseline; relevance scores are shown per variant. Delivery evidence links to each
retained check. Use **View JSON data** for the underlying record. **Submitted**
does not mean evaluated or deployed. Both comparison revisions must contain the
current evaluation/configuration contract.

For workstation commands and retry behaviour, see [remote delivery](remote-delivery.md).
Both paths call the same coordinator; neither requires kubectl.

## Promote a merged release

![Reviewed release deployment across three local targets](diagrams/rendered/release-promotion.png)

The three targets share one cluster. They are separate deployment namespaces,
not separate failure domains or performance-isolated systems.

1. Run **Lab delivery** on **main** with `propose-promotion`. Enter the successful
   merged-source run ID, target `integration`, frozen dataset and intent.
2. Follow the operation to its `delivery-state` PR. The coordinator first
   evaluates the candidate against the target, then proposes the pinned release.
   A failed evaluation cannot create a valid promotion.
3. Review the evidence and wait for `delivery/validation`. A permitted reviewer
   must approve the exact PR head. Approval does not deploy it.
4. Run **Lab delivery** with `merge-reviewed` and that **desired-state PR number**.
   The coordinator rechecks the proposal and approval, merges it, then waits for
   Argo CD and the public API. The operation must finish with `state: verified`.
5. Repeat for `staging`, then `production`, using the **same merged build** and
   frozen inputs. Each preceding target must be verified first. No image is rebuilt.

If desired-state main or the target baseline changes, create a fresh proposal.
Evidence must match the exact inputs and intent and be no more than three days old.
A merge without successful deployment verification is not a completed promotion.
Use `verify` with the target to recheck after an operator repairs a failed deployment.

| Target | Gatling profile | Required evidence |
| --- | --- | --- |
| Integration / staging | `probe` | Short wiring/regression check |
| Simulated production | `production-load` | One minute warmup, five minutes at 10 requests/s and fifteen minutes at 20 requests/s, for each release |

Production tests run sequentially against temporary baseline/candidate previews,
not the deployed production service. They take at least 42 minutes plus setup.
Both runs must complete every scheduled arrival and satisfy the pinned
[workload](../lab/traffic/production-load-v1.json). Normal-load budgets are
p95 ≤250 ms and p99 ≤500 ms; peak budgets are p95 ≤400 ms and p99 ≤800 ms.
Both phases require fewer than 1% failed requests. These are lab thresholds,
not production capacity claims. Probes, smoke checks and stress tests cannot
replace this gate. Validation checks the load evidence again before merge.

## Roll back

1. Find the previous verified fingerprint under
   `delivery-state/history/<target>/`. Its retained definition pins the old
   image, configuration, inputs and index recipe.
2. Run **Lab delivery** with `propose-rollback`, the target, fingerprint and intent.
   The coordinator evaluates **current → previous** and creates a new PR.
   Reversing an old report is insufficient. Production rollback uses the full
   `production-load` profile too.
3. Review, approve and run `merge-reviewed` as for promotion. A historical schema
   uses its retained index recipe; it cannot silently use the latest mapping.

## Artefacts and administration

| Repository or store | Contents |
| --- | --- |
| `delivery-source` | API/UI, tests, ranking settings, index contract and Actions workflows |
| `delivery-state` | Reviewed target definitions, relevance decisions, proposals and deployment history |
| Nexus | Digest-pinned images, deterministic bundles, build receipts and signed merge evidence |
| `search-spike` / `environment-state` | Separate leased experiment workflow in the control UI |

Operators bootstrap empty targets, install the coordinator, manage credentials
and recover failed resources. See [control runtime](control-runtime.md) and
[activation](plans/walkthrough-activation.md). Previews expire after 72 hours;
stable targets do not. Removing a preview retains its source and frozen evidence.

For GitHub Enterprise, retain the shared Actions syntax and frozen contracts,
replace provider-specific repository/run/PR/status calls, and configure runner
credentials and protection. Local Gitea execution does not establish GHES compatibility.
See [dated delivery evidence](research/evidence/promotion-deployment.md) and
[remaining native/cloud checks](plans/native-cloud-validation.md).
