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
