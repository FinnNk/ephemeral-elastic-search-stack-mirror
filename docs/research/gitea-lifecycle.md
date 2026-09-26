# Self-contained Git lifecycle with Gitea

Desk research on 26 September 2026. The prototype uses local Gitea so that a branch, pull request, build, container image, environment, relevance/result/performance comparison and teardown can all be shown on the lab machine or cluster. The target organisation later uses GitHub Enterprise. This is a design and spike checklist, not a claim that the stack has already run.

## Component fit

| Capability | Gitea component | Implementation check |
| --- | --- | --- |
| Git repositories and pull requests | Gitea server installed by its [Helm chart](https://docs.gitea.com/installation/install-on-kubernetes/) | Persistent repository and database storage, stable in-cluster and browser URLs |
| Build automation | [Gitea Actions](https://docs.gitea.com/usage/actions/) and a registered [runner](https://docs.gitea.com/runner/) | Runner networking, cache, resource limits, image build and multi-architecture output |
| Container images | [Gitea OCI registry](https://docs.gitea.com/usage/packages/container/) | Runner push, cluster pull credentials, digest capture and image retention after environment deletion |
| Events | Signed [Gitea repository webhooks](https://docs.gitea.com/usage/repository/webhooks) | Verify signatures over the raw body, deduplicate delivery, reconcile missed events and test private-cluster reachability |
| Desired state | Gitea repository read by Argo CD | Measure Git change to Application readiness; verify repository credentials and refresh mechanism |

Run Gitea as a persistent platform service outside ephemeral namespaces. A disposable namespace must never contain the Git server, registry or runner it needs for recreation. Keep the frozen product and query release in Floci AZ; store only manifest references and hashes in Git. Retain built image digests for at least as long as any environment or saved comparison may need recreation. The lab should record registry storage consumption and a deliberate retention policy.

## Research status

The [platform spike](platform-spike.md) exercised Gitea PR builds, retained image digests, Argo deployment, API comparison, deletion/recreation and an analyser Job. Signed webhook handling was tested separately. Automated build-completion orchestration, leases, the UI and all three full evaluation modes remain implementation work.

The tested runner is rootless Docker-in-Docker but still uses a privileged pod. The spike also required service DNS for Git because curl treats `.localhost` specially; the runnable slice should replace that workaround with consistent TLS-enabled naming. Every retained build needs a unique tag as well as a recorded digest.

## Proposed demonstration

1. Start the local Kubernetes cluster and its persistent services: Gitea, runner, Argo CD, ECK, shared Elasticsearch and Floci AZ. Verify the runner and Kubernetes nodes can resolve the same Gitea registry address.
2. Branch from the baseline search API; change query normalisation; open a Gitea pull request. Run tests, build an image, push it to the local registry and record its digest.
3. Receive a signed pull-request or workflow-completion event. The lab API resolves the exact commit and digest, combines them with a frozen dataset release, and creates an isolated environment through the chosen Argo CD path. It must support a direct UI/API request against an already built digest as well.
4. Compare the candidate's public search API with the baseline using the same original queries. Exercise relevance, result preservation and Gatling performance as defined in the [design](../prototype-design.md#search-and-comparison), with separate verdicts and expected outcomes. Store results and provenance, exercise activity extension, then delete and recreate the environment from the pinned inputs.
5. Repeat with an analyser or mapping change that builds a distinct index. Close the pull request, confirm its source status is reflected in the lab, and let the environment follow its independent lease until deletion or expiry.

The [Gitea runner documentation](https://docs.gitea.com/runner/2/installation/kubernetes/) describes Kubernetes options including Docker-in-Docker and rootless Docker. Privileged Docker-in-Docker is an avoidable risk for untrusted pull-request code; choose and measure a runner/build configuration during the spike. The runner, job containers and Kubernetes nodes need a stable, shared hostname for Gitea. Avoid `localhost` in runner registration or registry references because it resolves separately inside each container.

Gitea can send HMAC-signed webhooks for push, pull-request and workflow events. Its [webhook documentation](https://docs.gitea.com/usage/repository/webhooks) requires verification using signature headers rather than expecting the secret in the body. For a cluster-local receiver, configure an allowlist for its host as Gitea's [default webhook host policy](https://docs.gitea.com/administration/config-cheat-sheet/) is restrictive. Do not assume Argo CD recognises a Gitea webhook as a GitHub payload: Argo CD documents Git webhooks for several providers and [polls Git about every three minutes by default](https://argo-cd.readthedocs.io/en/stable/operator-manual/webhook/). Measure Gitea event to Argo refresh; a validated lab API may trigger an explicit refresh if webhook compatibility is insufficient. Polling remains the recovery path for a missed event.

## Provider boundary for GitHub Enterprise

The domain model stores `sourceRevision` as a Git SHA and `imageDigest` as an OCI digest. It stores repository and pull-request links as provider metadata. A `SourceProvider` implementation owns:

- webhook signature and event parsing;
- revision and pull-request lookup;
- commit or pull-request status publication;
- repository credentials and URL construction.

Implement the Gitea provider first. A GitHub Enterprise provider should satisfy the same contract and conformance checks. CI build steps should use portable shell or scripts in the repository, with thin provider-specific workflow files. Argo CD should consume a configurable Git URL rather than a Gitea-specific path. The image registry can remain Gitea temporarily or move to the organisation's registry independently of the Git migration; environment fingerprints use the resolved digest, not a registry tag.

Migration rehearsal: mirror or push the repositories to a GitHub Enterprise test instance; configure its credentials, webhooks and build runner; build the same commit; create an environment; run the same comparison; check provenance and lease/delete behaviour. Repository migration alone does not prove that Actions workflows, PR event formats or registry credentials have migrated.

## Research impact on platform candidates

Lifecycle's [API-created environments](https://uselifecycle.com/docs/features/api-environments) require an onboarded repository. The [documented onboarding](https://uselifecycle.com/docs/getting-started/onboard-repository) requires a GitHub App installation, and its local development guide uses GitHub App credentials. No supported Gitea integration was found in the reviewed Lifecycle documentation. Therefore Lifecycle is not the leading *self-contained* implementation unless the research spike demonstrates a supported Gitea path. A custom GitHub-compatible bridge would need explicit justification against the simpler Argo CD-native path.
