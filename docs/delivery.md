# Reference CI/CD

The reference workflow builds an exact source revision, publishes an immutable Nexus release and deploys that release through reviewed Git changes. Gitea runs the local demonstration. Argo CD owns deployments. The [delivery contract](plans/reference-ci-cd.md) defines promotion and evaluation rules.

## Repositories and services

| Resource | Purpose |
| --- | --- |
| [delivery-source](https://gitea.localhost:34443/elastic-agent/delivery-source) | Search API/UI, tests, chart, schema contract and shared Actions workflow |
| [delivery-state](https://gitea.localhost:34443/elastic-agent/delivery-state) | Reviewed deployment and promotion state |
| [Nexus](https://nexus.localhost:34443/) | Private image digests, bundles and release descriptors |
| Existing `search-spike` / `environment-state` | Historical builds and the existing leased comparison UI |

These are demonstration repositories. Their test PRs may be merged by the demonstration harness; project implementation PRs remain for your review. All source templates and setup code are retained in this project.

## Bootstrap and build

From the repository root in PowerShell, with the existing k3d platform, [HTTPS ingress](https-ingress.md), Python dependencies and frozen data available:

```powershell
python lab/setup_nexus.py
python lab/setup_delivery.py
```

The setup creates private repositories and a repository-scoped `lab-delivery` runner. It seeds source only once; subsequent source changes use branches and PRs. Both `finnnk` and the agent can access the demonstration repositories. The runner uses the existing privileged rootless Docker-in-Docker lab pattern; it is for trusted local contributors, not arbitrary public fork code. Its mounted lab root CA verifies the internal HTTPS Gitea address retained in runner registration.

1. Open a source branch and PR in `delivery-source`.
2. **Reference release CI** checks out the exact PR head SHA. Its first step has only a source-read token.
3. The build script runs application tests, builds amd64/arm64 images and publishes them to Nexus under a unique SHA/run/attempt tag.
4. CI publishes the deterministic deployment bundle, then the release descriptor, then the successful-build receipt. Environments use the descriptor's digest reference.
5. Merge the accepted source PR. CI builds the merged SHA and records a separate release. Promotion uses the merged-source release and its own evaluation.

A failing test stops publication. The source PR may still have older successful runs: select a run that matches the current head exactly. The [retained CI evidence](research/evidence/portable-ci.md) demonstrates both successful and failed paths.

The separate **Offline relevance gate** runs trusted target-branch code. Changes limited to `README.md` and `gate/README.md` pass with a recorded documentation exemption. Every other change needs frozen evaluation evidence, including changes to the gate itself. The [relevance gate guide](relevance-gate.md) explains the rule and installation of the two required checks.

For a behaviour change, the source PR commits `gate/selection.json` without a source SHA. Its exact PR build supplies the image; an independent evaluator then publishes a signed report and attestation to Nexus under that SHA. Rerun the relevance check after publication. It checks the versioned policy, named baseline, coverage, metric deltas, changed-result fraction and any signed administrator exception. A missing bundle or a blocked result fails the gate. An approved exception keeps the measured score and reason in separate fields. The [variant guide](variant-evaluation.md) defines the frozen inputs and decision contract.

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

Run these commands from the repository root in PowerShell after installing `lab-control`. The Pod owns the delivery checkout and evidence-reference files; its watcher runs automatically. For a fresh demonstration, seed all targets from a successful merged-source run. Repeating bootstrap is allowed only while every target still declares that same baseline. Once promotion changes state, use promotion or rollback PRs.

```powershell
$kube = '.lab/kubeconfig.yaml'
kubectl --kubeconfig $kube -n lab-control exec deployment/lab-control -c api -- python lab/delivery_cli.py bootstrap --run 15 --dataset retail-gb-1m-v1
```

Run IDs below are retained examples from this host. On a new installation, choose the successful **push** builds for your baseline and candidate. A PR-head build is not a substitute for the merged-source release.

```powershell
kubectl --kubeconfig $kube -n lab-control exec deployment/lab-control -c api -- python lab/delivery_cli.py evaluate-target integration --run 21 --dataset retail-gb-1m-v1 --recipe 83877e5435059716539493991aad365104f9251d80c545b1f02f5ce6e2021c6e --intent ranking-change
# Use the reference_file printed by evaluate-target:
kubectl --kubeconfig $kube -n lab-control exec deployment/lab-control -c api -- python lab/delivery_cli.py promote integration --run 21 --dataset retail-gb-1m-v1 --recipe 83877e5435059716539493991aad365104f9251d80c545b1f02f5ce6e2021c6e --evidence /state/delivery/evidence-<sha256>.json --intent ranking-change
```

`evaluate-target` reads the exact current desired definition for its baseline. With `--run`, it resolves a new candidate; with `--fingerprint`, it reads a retained prior definition for rollback. Use the latter when an older target has fields or an index name that a new run-derived definition would not reproduce. The general `evaluate` command remains available for two explicitly selected run-derived environments.

Evaluation prepares **two frozen API environments**. New deployment definitions pin a catalogue manifest and format-2 index recipe; each check receives the selected independent query suite and, for relevance, its compatible judgement set. The same compiled Gatling workload runs against each API in sequence. Reports remain in Floci under content hashes. The default `probe` profile measures ten seconds at 2 rps after warmup; it exercises the delivery check, not capacity. Use `--profile smoke` for the longer existing smoke profile. Failed evaluations retain and print their report reference but cannot pass promotion validation.

To evaluate a revised synthetic suite, pass `--query-manifest <sha256>` and `--judgement-manifest <sha256>` to `evaluate-target --run` or `evaluate`. Pass the same options to `promote`; the candidate definition, reports and promotion evidence must agree. A retained rollback definition already pins its selected inputs. A new preview name includes the complete deployment fingerprint, so different selected inputs cannot reuse an earlier preview by accident.

- **Preserve results:** the full suite must complete with identical ordered results. RBO/Jaccard remain diagnostics in the retained query reports.
- **Intentional ranking change:** add `--intent ranking-change` to both evaluation and promotion. Changed results are allowed, but review must assess relevance, changed queries and judgement coverage. Synthetic judgements are a proxy, even at 100% coverage.
- **Fresh evidence:** reports must match both deployment fingerprints, the candidate's catalogue, query and judgement manifest hashes, and the declared intent; contain all three complete checks; and be no more than three days old. A moved desired-state main invalidates the proposal; recreate it. Re-evaluation is needed when the baseline, candidate, selected inputs, intent or evidence window changes.

Open the returned PR using your `finnnk` account, inspect its diff and evidence, and approve its exact head. The Kubernetes coordinator can then run `merge-reviewed <pr-number>` to revalidate, squash merge and verify the deployment. The watcher validates open proposals and verifies merged deployments; it does not approve or merge them. Once integration is verified, repeat `promote staging`, then `promote production`, using the **same run, dataset and recipe**. Evidence can be reused only if each target has the same evaluated baseline and the reports remain fresh.

```powershell
kubectl --kubeconfig $kube -n lab-control exec deployment/lab-control -c api -- python lab/delivery_cli.py status
kubectl --kubeconfig $kube -n lab-control exec deployment/lab-control -c api -- python lab/delivery_cli.py validate <pr-number>
kubectl --kubeconfig $kube -n lab-control exec deployment/lab-control -c api -- python lab/delivery_cli.py verify integration
```

On the installed Kubernetes runtime, run the reviewed merge in the authoritative control Pod:

```powershell
kubectl --kubeconfig $kube -n lab-control exec deployment/lab-control -c api -- python lab/delivery_cli.py merge-reviewed <approved-pr-number>
```

Validation failures return a non-zero exit code. The target's current verification must match its serving fingerprint before onward promotion. A failed deployment is recorded separately and is retried by the watcher; it never becomes a successful source stage merely because its PR merged.

For an **explicit automated demonstration only**, run `python lab/delivery_cli.py demonstrate-merge <pr-number>` from a host with the separate `lab-admin` fixture credential. It labels that approval as simulated, then performs the same reviewed merge and verification. The control Pod has no reviewer credential. The adapter only accepts `delivery-source` and `delivery-state`; project implementation PRs are excluded. The demonstration identities are local administrators, so this is a workflow reference, not a hostile-user security boundary.

## Schema changes and rollback

| Change | Required inputs |
| --- | --- |
| API/query change | New immutable release; reuse a compatible recipe and concrete frozen index |
| Mapping/analyser/indexer change | Publish a recipe using the [schema workflow](research/evidence/historical-index-recipes.md); update the source release's `contracts/index.json` and pinned indexer source, then build a new release |
| Historical comparison | Select the retained recipe explicitly with `--baseline-recipe` / `--candidate-recipe` during evaluation |
| Promotion of that schema | Pass the same `--recipe <sha256>` to preview/promotion; engine, mapping/settings and indexer contract must match |
| Rollback | Select a previous verified deployment for that target, including its release, configuration, dataset and recipe |

The coordinator uses existing exact reuse, clone, snapshot and rebuild selection. It never substitutes the latest mapping for a historical recipe. Frozen release indices outlive previews and are retained for comparisons and rollback.

Rollback needs fresh evidence **from the current target to the previous deployment**. Reversing the direction of an old report is not sufficient. The old fingerprint comes from that target's retained desired-state history. For the measured example:

```powershell
kubectl --kubeconfig $kube -n lab-control exec deployment/lab-control -c api -- python lab/delivery_cli.py evaluate-target production --fingerprint 00cd57233b8a30a6e452a82e7237e97892553c1408af21fc9aa1deb7e2845dea --intent ranking-change
kubectl --kubeconfig $kube -n lab-control exec deployment/lab-control -c api -- python lab/delivery_cli.py rollback production --fingerprint 00cd57233b8a30a6e452a82e7237e97892553c1408af21fc9aa1deb7e2845dea --evidence /state/delivery/evidence-<reverse-sha256>.json --intent ranking-change
```

Review and merge the rollback PR in the same way. The previous complete definition comes from Git history and must have a retained verification record for that target. Schema-changing rollbacks select the old recipe and materialise its index before deployment.

## Operate the local demonstration

| Operation | Command or location |
| --- | --- |
| Create/reuse a frozen preview; extend its lease by 72 hours | `python lab/delivery_cli.py preview --run <run> --dataset retail-gb-1m-v1` |
| Remove a preview on demand | `python lab/delivery_cli.py delete-preview <lab-delivery-run-name>` |
| Process expired previews once | `python lab/delivery_cli.py expire-previews` |
| Run validation, deployment verification and expiry once | `python lab/delivery_cli.py watch --once` |
| Inspect the active watcher | `kubectl --kubeconfig .lab/kubeconfig.yaml -n lab-control logs deployment/lab-control -c delivery-watcher --tail=30` |
| Inspect a target UI/API | `kubectl --kubeconfig .lab/kubeconfig.yaml -n lab-delivery-integration port-forward service/search 18088:8080`, then open `http://127.0.0.1:18088/` |
| Inspect deployment | Existing Argo CD login; Applications named `lab-delivery-*` |

Preview creation and evaluation renew the lease; background validation does not. Expiry removes the preview namespace, Argo application and Elasticsearch credential. Immutable source, release artifacts, reports and frozen indices remain. Stable promotion targets have no preview lease.

The coordinator now runs in the single `lab-control` Pod with its guarded Git checkout on a retained PVC. Ports 18086/18087 still serialise operations; a concurrent operation may ask you to retry. The watcher polls every 30 seconds. Verification reports are also retained in Blob storage. Export the control PVC as described in the [runtime guide](control-runtime.md); restoration must preserve report references and the separate retained services. Multi-replica coordination is outside this local demonstration.

Delivery targets rendered before the control move retain an earlier Search API NetworkPolicy. The control installer adds a scoped, additive ingress policy to the three existing targets, while the delivery renderer includes it in future proposals. This preserves old frozen release bundles and protected desired-state history. Re-run `install.py stage` after restoring those targets into a cluster with an active control Pod. Argo does not update an unchanged historical rendered target just because the chart source changes.

The [measured walkthrough](research/evidence/promotion-deployment.md) covers promotion, rollback, denied unreviewed merge, stale proposals, incompatible schema and preview recreation. No artifact cleanup is enabled. Back up Nexus/PostgreSQL volumes, Git, credentials and Floci separately from project source.

### Offline variant merge gate

A source PR opts in with `gate/selection.json`. The workflow builds the exact PR commit, then runs the pinned Python gate in a disposable container. Nexus retains the report, signed attestation and CI build receipt under the source SHA. The selected variant's captured image must equal the attested build image. Missing or changed evidence fails the job; low judged coverage blocks it. A CI rerun can read evidence issued after the first build without changing the commit. The [managed rehearsal](research/evidence/managed-variant-gate.md) shows a blocked live report and a separate deterministic fixture pass.

The environment-state ApplicationSet passes a frozen variant configuration to the Search API as base64 text so Helm's parameter parser does not split JSON commas. The chart decodes it into `SEARCH_VARIANTS_JSON`. The environment fingerprint covers that configuration, image, index and image-pull identity. Existing Gitea image environments use `registry-read`; the Nexus-backed proof uses `nexus-read`.

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
