# Fresh Mac installation

## Outcome

Create a new CPU lab with fresh local identities and certificates. Support the
corporate network encountered during the Mac walkthrough, show useful manual
progress, resume interrupted setup and inspect/reset only a disposable fresh
installation. Keep the original Windows lab untouched.

## Completed foundation batch

- Ordered cluster, platform, storage and browser-access stages; dedicated
  kubeconfig export creates its parent directory first.
- Corporate CA trust for Python downloads and mounted k3d node trust, official
  Docker Hub Gitea with the unchanged release digest, and GitHub API manifest
  retrieval with TLS verification enabled.
- Installer ownership records, exclusive invocation lock, saved completed
  stages, download hashes, streamed output, quiet-wait messages and timings.
- Read-only cleanup inventory and explicit deletion of recorded node resources
  and their named/anonymous volumes; generated host state is archived by default.
- Fresh-install and restoration guides have distinct entry points. DNS setup
  follows installation of the DNS service. Ingress defers absent backends.

This batch installs an empty platform foundation. It does not claim a complete
search lab, native Mac execution, whole-lab restoration or real cleanup testing.

## Complete CPU application batch

The user authorised completion, merging and verification of the GitHub mirror.
The installer now continues from the accepted foundation through owned Nexus and
snapshot services, private CI repositories/runners, OIDC, catalogue restoration,
native image builds, the CPU judgement stack, fresh baseline builds, control and
delivery activation, and readiness verification.

Corporate trust reaches host downloads, runners, image package installs and
Java/Maven. Registry choices survive HTTPS setup. Resume retains source commits,
image receipts and model registration artefacts; no Windows run IDs, model hashes
or credentials are assumed. An explicit cleanup option validates external store
identities before deleting the owned disposable installation.

The original Windows lab remains untouched. Automated fixtures establish recovery,
ownership and data identity behaviour, not a completed native Mac deployment.

## Next detailed plan: native acceptance

The Mac has completed catalogue import and materialised the 1,215,854-product
full index and 10,000-product demo index. The images stage then reported operator
port 14577 occupied immediately after the catalogue stage closed its forward.
The next repair aligns Unix socket-probe reuse with kubectl's listener behaviour
and preserves rejection of active listeners. The exact Mac listener state was
not captured; a surviving forward remains an alternative explanation.

The port-forward repair was accepted and the Mac reached ARM64 image builds.
Docker then reported `unknown flag: --platform` while Buildx was invoked with an
isolated `DOCKER_CONFIG`. The next batch preserves user plugin search paths in
that isolated configuration and resolves the selected local Docker context,
without copying registry credentials or context certificates. A Buildx version
check precedes login/build. 43 affected fixtures passed; a read-only Windows
check found Buildx and reached the same Linux Docker daemon with a disposable
isolated config. Mac execution remains the next acceptance check.

The Mac subsequently completed native image builds and the CPU judgement stack.
The baseline source checkout succeeded, but its registry login resolved
`gitea.localhost:31800` to loopback and was refused. The fresh services stage had
omitted the original platform installer's CoreDNS rewrite. The repair installs
that rule on new setups and reconciles it before baseline builds on resume,
preserving other DNS entries. A changed route permits one retry of the failed
push build for the exact source commit; a repeated failure stops. The installed
Gitea API schema confirms the run-ID rerun endpoint and attempt field. All 47
affected fixtures passed. Native Mac registry login and the remaining stages
still require acceptance; the original Windows cluster was not changed.

Native Mac registry recovery subsequently passed: search build 2 succeeded on
attempt 2 and delivery build 1 was already successful. Delivery bootstrap then
failed while importing the shared `evaluation` package. The installer now passes
the repository root to child scripts through `PYTHONPATH`, preserving existing
paths and certificate settings. Verification includes launching the actual
delivery CLI with `--help` in a child process, which imports its bootstrap
dependencies without calling the cluster. The 49 affected fixtures passed.
Resume baseline, then verify control, delivery and browser flows on the Mac.

The ESCI-S upstream bucket returned HTTP 403 on both the Mac and Windows.
The retained-source batch packages the three original files in `FinnNk/esci-s`
release assets and prefetches them before the unchanged importer runs. Original
source hashes and frozen catalogue identity are preserved. Native acceptance
must verify access to the public GitHub release assets on the corporate network.
The release is published and all seven asset hashes match; public manifest and
query/label downloads passed on Windows. The affected fixture suite passed 37
tests. See [verification](../research/evidence/esci-retained-sources.md).

1. Pull the mirror, install `lab/fresh-requirements.txt` with the existing host CA
   bundle and resume with the original corporate PEM and setup options.
2. Record the first failing stage, if any; inspect its saved logs and Actions
   results. Preserve completed stages and repair the specific cause before retrying.
3. Confirm local DNS/HTTPS and named OIDC sign-in. Create one small comparison,
   open the notebook and follow a reviewed promotion through the UI/Actions.
4. Restart the disposable cluster and rerun final verification. Inspect cleanup
   inventory; exercise a complete owned reset only on that disposable target.

No original-lab deletion, deployment, inference or load test is part of this batch.
