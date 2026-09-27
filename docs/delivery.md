# Reference CI/CD

The reference workflow builds an exact source revision, publishes an immutable Nexus release and deploys that release through reviewed Git changes. Gitea runs the local demonstration. Argo CD owns deployments. The [delivery contract](plans/reference-ci-cd.md) defines promotion and evaluation rules.

## Repositories and services

| Resource | Purpose |
| --- | --- |
| [delivery-source](http://127.0.0.1:31800/elastic-agent/delivery-source) | Search API/UI, tests, chart, schema contract and shared Actions workflow |
| [delivery-state](http://127.0.0.1:31800/elastic-agent/delivery-state) | Reviewed deployment and promotion state |
| [Nexus](http://127.0.0.1:18183) | Private image digests, bundles and release descriptors |
| Existing `search-spike` / `environment-state` | Historical builds and the existing leased comparison UI |

These are demonstration repositories. Their test PRs may be merged by the demonstration harness; project implementation PRs remain for your review. All source templates and setup code are retained in this project.

## Bootstrap and build

From the repository root in PowerShell, with the existing k3d platform, Python dependencies and frozen data available:

```powershell
python lab/setup_nexus.py
python lab/setup_delivery.py
```

The setup creates private repositories and a repository-scoped `lab-delivery` runner. It seeds source only once; subsequent source changes use branches and PRs. Both `finnnk` and the agent can access the demonstration repositories. The runner uses the existing privileged rootless Docker-in-Docker lab pattern; it is for trusted local contributors, not arbitrary public fork code.

1. Open a source branch and PR in `delivery-source`.
2. **Reference release CI** checks out the exact PR head SHA. Its first step has only a source-read token.
3. The build script runs application tests, builds amd64/arm64 images and publishes them to Nexus under a unique SHA/run/attempt tag.
4. CI publishes the deterministic deployment bundle, then the release descriptor, then the successful-build receipt. Environments use the descriptor's digest reference.
5. Merge the accepted source PR. CI builds the merged SHA and records a separate release. Promotion uses the merged-source release and its own evaluation.

A failing test stops publication. The source PR may still have older successful runs: select a run that matches the current head exactly. The [retained CI evidence](research/evidence/portable-ci.md) demonstrates both successful and failed paths.

## Retained release contract

| Artifact | Pinned contents |
| --- | --- |
| `releases/<release-id>.json` | SHA-256-addressed descriptor: source SHA/repository, image digest, bundle hash, file hashes and index compatibility |
| `bundles/<sha256>.tar.gz` | Deterministic API/UI source, chart and complete index/indexer contract |
| `builds/<source-sha>/<run>-<attempt>.json` | Provider run receipt, event type and release ID; published last |
| Container image | API, UI and query-understanding/ranking code; revision label and multi-platform digest |

The current API keeps query logic in `app.py`; its hash is part of the bundle and its code is inside the image. There are no unversioned external synonyms or models. Future external query assets must join this frozen contract before promotion can use them.

Release verification checks every bundle member and checksum, rejects path traversal and mutable images, and verifies the indexer source against its compatibility contract. A release does not contain credentials, target namespace or dataset selection. Those belong to the deployment definition.

## Evaluate and promote

The three stable targets are `lab-delivery-integration`, `lab-delivery-staging` and `lab-delivery-production`. Production is a local simulation. They share the cluster and compatible frozen indices; they do not provide separate failure domains or performance isolation.

| State | Evidence |
| --- | --- |
| Proposed | Open PR in `delivery-state`, containing deployment JSON, rendered resources, prior definition and report references |
| Validated | `delivery/validation` passes for the exact PR head and current desired-state main |
| Approved | A permitted reviewer approves; Gitea requires that review and the passing status before merge |
| Deploying | Merged desired state differs from the serving deployment; Argo CD reconciles it |
| Verified | Argo is Synced/Healthy, the rollout has completed, the image/index fingerprint matches and a public API query succeeds |

For a fresh demonstration, seed all targets from a successful merged-source run. Repeating bootstrap is allowed only while every target still declares that same baseline. Once promotion changes state, use promotion or rollback PRs.

```powershell
python lab/delivery_cli.py bootstrap --run 15 --dataset retail-gb-1m-v1
python lab/start_delivery_watch.py
```

Run IDs below are retained examples from this host. On a new installation, choose the successful **push** builds for your baseline and candidate. A PR-head build is not a substitute for the merged-source release.

```powershell
python lab/delivery_cli.py evaluate --baseline-run 15 --candidate-run 17 --dataset retail-gb-1m-v1
# Use the reference_file printed by evaluate:
python lab/delivery_cli.py promote integration --run 17 --dataset retail-gb-1m-v1 --evidence .lab/delivery/evidence-<sha256>.json
```

Evaluation prepares **two frozen API environments**. Both receive the full query suite for result preservation and relevance, then the same compiled Gatling workload in sequence. Reports remain in Floci under content hashes. The default `probe` profile measures ten seconds at 2 rps after warmup; it exercises the delivery check, not capacity. Use `--profile smoke` for the longer existing smoke profile. Failed evaluations retain and print their report reference but cannot pass promotion validation.

- **Preserve results:** the full suite must complete with identical ordered results. RBO/Jaccard remain diagnostics in the retained query reports.
- **Intentional ranking change:** add `--intent ranking-change` to both evaluation and promotion. Changed results are allowed, but review must assess relevance, changed queries and judgement coverage. Synthetic pooled judgements are a proxy, even at 100% coverage.
- **Fresh evidence:** reports must match both deployment fingerprints and the declared intent, contain all three complete checks, and be no more than three days old. A moved desired-state main invalidates the proposal; recreate it. Re-evaluation is needed when the baseline, candidate, intent or evidence window changes.

Open the returned PR using your `finnnk` account, inspect its diff and evidence, approve and merge. The watcher validates open proposals and verifies merged deployments. It does not approve or merge them. Once integration is verified, repeat `promote staging`, then `promote production`, using the **same run, dataset and recipe**. Evidence can be reused only if each target has the same evaluated baseline and the reports remain fresh.

```powershell
python lab/delivery_cli.py status
python lab/delivery_cli.py validate <pr-number>
python lab/delivery_cli.py verify integration
```

Validation failures return a non-zero exit code. The target's current verification must match its serving fingerprint before onward promotion. A failed deployment is recorded separately and is retried by the watcher; it never becomes a successful source stage merely because its PR merged.

For an **explicit automated demonstration only**, `python lab/delivery_cli.py demonstrate-merge <pr-number>` uses the separate `lab-admin` identity to approve, labels the approval as simulated, merges the fixture PR and verifies deployment. The adapter only accepts `delivery-source` and `delivery-state`; project implementation PRs are excluded. The demonstration identities are local administrators, so this is a workflow reference, not a hostile-user security boundary.

## Schema changes and rollback

| Change | Required inputs |
| --- | --- |
| API/query change | New immutable release; reuse a compatible recipe and concrete frozen index |
| Mapping/analyser/indexer change | Publish a recipe using the [schema workflow](research/evidence/historical-index-recipes.md); update the source release's `contracts/index.json` and pinned indexer source, then build a new release |
| Historical comparison | Select the retained recipe explicitly with `--baseline-recipe` / `--candidate-recipe` during evaluation |
| Promotion of that schema | Pass the same `--recipe <sha256>` to preview/promotion; engine, mapping/settings and indexer contract must match |
| Rollback | Select a previous verified deployment for that target, including its release, configuration, dataset and recipe |

The coordinator uses existing exact reuse, clone, snapshot and rebuild selection. It never substitutes the latest mapping for a historical recipe. Frozen release indices outlive previews and are retained for comparisons and rollback.

Rollback needs fresh evidence **from the current target to the previous deployment**. Reversing the direction of an old report is not sufficient. For the measured example:

```powershell
python lab/delivery_cli.py evaluate --baseline-run 17 --candidate-run 15 --dataset retail-gb-1m-v1
python lab/delivery_cli.py rollback production --fingerprint <previous-deployment-sha256> --evidence .lab/delivery/evidence-<reverse-report-sha256>.json
```

Review and merge the rollback PR in the same way. The previous complete definition comes from Git history and must have a retained verification record for that target. Schema-changing rollbacks select the old recipe and materialise its index before deployment.

## Operate the local demonstration

| Operation | Command or location |
| --- | --- |
| Create/reuse a frozen preview; extend its lease by 72 hours | `python lab/delivery_cli.py preview --run <run> --dataset retail-gb-1m-v1` |
| Remove a preview on demand | `python lab/delivery_cli.py delete-preview <lab-delivery-run-name>` |
| Process expired previews once | `python lab/delivery_cli.py expire-previews` |
| Run validation, deployment verification and expiry once | `python lab/delivery_cli.py watch --once` |
| Start the hidden watcher | `python lab/start_delivery_watch.py`; log and PID: `.lab/delivery-watch.log`, `.lab/delivery-watch.pid` |
| Inspect a target UI/API | `kubectl --kubeconfig .lab/kubeconfig.yaml -n lab-delivery-integration port-forward service/search 18088:8080`, then open `http://127.0.0.1:18088/` |
| Inspect deployment | Existing Argo CD login; Applications named `lab-delivery-*` |

Preview creation and evaluation renew the lease; background validation does not. Expiry removes the preview namespace, Argo application and Elasticsearch credential. Immutable source, release artifacts, reports and frozen indices remain. Stable promotion targets have no preview lease.

The coordinator is one host process with a guarded local checkout. Ports 18086/18087 enforce one operation/watcher; a concurrent CLI operation may ask you to retry. The watcher polls every 30 seconds. Metadata under `.lab/delivery` and repository checkouts are local; verification reports are also retained in Blob storage. Restoring a lost local verification cache requires explicit reconciliation from those reports. [Batch 7i](plans/kubernetes-control-services.md) plans a single active Kubernetes control Pod, persistent state and recovery checks; it is not deployed yet. Multi-replica coordination and full host-loss recovery remain separate from that local move.

The [measured walkthrough](research/evidence/promotion-deployment.md) covers promotion, rollback, denied unreviewed merge, stale proposals, incompatible schema and preview recreation. No artifact cleanup is enabled. Back up Nexus/PostgreSQL volumes, Git, credentials and Floci separately from project source.

## Gitea to GHES

| Shared implementation | Provider configuration / adapter |
| --- | --- |
| `.github/workflows/release.yaml`, standard `push`/`pull_request`, jobs, steps, `run`, `env`, `secrets`, `vars`, `github` context aliases | Gitea discovers `.github/workflows` when `.gitea/workflows` is absent; verify discovery on the deployed version |
| `ci/build.sh` and Python release format | Register a GHES self-hosted Linux runner with `lab-delivery`; provide Docker/buildx and amd64/arm64 build support |
| Git checkout and source SHA verification | `SOURCE_USER`, scoped `SOURCE_TOKEN`; optional `SOURCE_BASE_URL` for an internal endpoint |
| Nexus publication | `RELEASE_REGISTRY`, `RELEASE_ARTIFACT_URL`, `NEXUS_USER`, `NEXUS_PASSWORD`; use HTTPS outside the private lab |
| Release/evaluation/promotion contracts | Replace `lab/delivery_provider.py` repository, PR, run and status API calls; require equivalent protected-branch rules |

No marketplace actions, provider artifact/cache actions, environment approvals or provider OIDC are required by this slice. The job deliberately excludes cross-repository fork PRs. Private same-repository contributors are trusted with the scoped publisher credential; production CI should separate untrusted testing from authorised publication.

The Gitea run proves local behaviour, not GHES compatibility. [Batch 8](plans/native-cloud-validation.md) includes a real GHES run, status/protection checks and migration of desired state. See [Gitea's differences](https://docs.gitea.com/usage/actions/comparison/) for version-specific behaviour.
