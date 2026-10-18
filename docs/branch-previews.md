# Build a preview from a branch or commit

Try a committed Search API change without opening a PR. The control UI builds
the exact source revision, tests it and creates an isolated environment using
your selected frozen catalogue and matching Redis rewrite data.

## Create the preview

You need a human lab administrator account and a commit available in the local
`elastic-agent/delivery-source` repository. Push a local branch before using it.

1. Open [Search lab](https://control.localhost:34443/) and sign in.
2. Under **Build and create preview**, enter a branch name such as
   `feature/title-ranking`, or a full 40-character commit SHA.
3. Select **Catalogue and rewrite data**. The existing shared index is reused
   where compatible. **Index options** can pin a retained historical recipe.
4. Select **Build and create preview**. The branch is resolved immediately to
   a full SHA; later branch movement does not change the request.
5. Follow **Open build and preview progress**. The page shows the pinned commit,
   CI build link and current stage. After verification, select **Open preview
   storefront** or find the ready preview in **Environments**.

The preview uses the source revision's selected variants and default. Its
generated name includes its build number and frozen fingerprint. Its lease is
72 hours, with the existing early-expiry and lease controls available on its
environment card. Queries are chosen separately when running a comparison.

The source needs the ordinary build inputs: `VERSION`, application tests and
dependencies, index contract, chart and gate configuration. An older revision
missing those inputs fails its build or validation with a result link; the
service does not rewrite the chosen commit.

## Build identity and promotion

These builds use versions such as `1.2.3-preview.250.1`, retaining their exact
source SHA, image digest and build attempt. They do not reserve a stable release
version, so an experiment can use its existing base `VERSION` value.

A preview is an experiment, not a merged release. Promotion still requires a
source PR, successful merged-source build, the mandatory standard checks and
reviewed promotion plan/proposal. Neither the preview workflow nor its control
operation writes a merge approval or changes an Integration, Staging or
Production deployment. The normal release dashboard excludes these manual
preview builds from its promotable builds.

## Follow or recover a request

Refreshing the operation page does not start another build. The form retains
the request and operation link in this browser tab's session. Double clicks
are disabled; a retry after an uncertain HTTP response uses the same request
key and returns the original pinned work.

| Situation | Action |
| --- | --- |
| Build queued | Open its Actions link and check runner availability. The preview is created only after success. |
| Build failed | Open the build logs from the operation result. No preview is created from that failed build. |
| Dispatch response lost | Inspect the saved operation and Actions before starting another attempt. The coordinator records dispatch intent and does not blindly resend it. |
| Protected main changed while queued | Submit a new request. Use the displayed full source SHA to retain the same candidate if its branch has moved. |
| Coordinator restarted | Inspect the interrupted request and its Actions run. The coordinator does not replay a possible build dispatch automatically. |

## Install or update the capability

A fresh installation seeds `.github/workflows/build-preview.yaml` and the
protected `ci/build-preview.sh`, `ci/release.py` and `ci/versioning.py` tooling.
The existing source runner, registry and artefact credentials are reused. No
new service, inference model or workstation dependency is required.

For an existing lab, merge the accepted delivery-source workflow/tooling PR,
then merge and activate the lab API/UI change when delivery and comparison work
is idle. Existing source repositories are not overwritten by the installer.

The workflow is always dispatched from protected `main`, fetching the candidate
by its resolved SHA. Candidate tests receive neither registry credentials nor
the Docker socket. Tests use uv with hash-pinned dependencies and the combined
system/lab/corporate CA trust. The application image retains the existing CA
build-secret mechanism. Protected publication tooling records both the source
commit and the workflow commit; the API verifies them against the actual Actions
run before deployment.

The same Linux runner workflow and multi-platform image build support Windows
and Mac lab hosts. A native Mac rehearsal remains part of fresh-install
acceptance; it is not established by workstation unit tests.
