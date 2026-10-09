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

The next Mac run imported the delivery CLI and deployed a ready integration
search pod, but API verification timed out. The host verification path executes
requests through `platform/search-probe`; that pod was absent from the fresh
installer and the supplied pod inventory. The repair creates an installer-owned
probe from the already-built native control image, waits for readiness and
preserves a matching probe on resume. It refuses an unexpected existing probe.
Verification now reports changing Argo/serving states and retains the last
reason in a timeout. Native API verification remains the next acceptance check.

The maintained resume guide now uses `$HOME/certs/Corporate Root CA.pem` as an
explicitly illustrative path instead of a personal home directory and employer
certificate name. The next step remains native baseline acceptance.

The initial smaller SigNoz proposal used seven days of traces/logs and 30 days
of metrics, with scoped collection. Measure idle storage growth and one Gatling
run before committing to the proposed 10 GiB ClickHouse data volume; leave room
for database merges and bursts. Low interactive usage does not stop periodic
metrics and infrastructure logs from accumulating.

The authorised demo profile is now prepared for review. It uses the pinned chart
on existing CPU nodes, 12 GiB PVC requests and approximately 4 GiB steady-state
memory headroom; migration/startup needs additional room. It reuses the retained
native control image and CA bundle for the checksum-verified histogram binary
download. Collector queues and memory are bounded; the gateway samples 20% of
traces while application metrics and selected structured logs remain complete.
The first organisation and seven-day traces/logs plus 30-day metric retention
are explicit UI setup steps. Standard installation settings are preserved.

Verification: 56 affected fixtures passed. The pinned Helm chart rendered 32
resources; the final render preserved the native init image digest and correct
registry secret name, with no dedicated-worker selectors. Both generated agent
configurations passed validation in disposable, network-disabled containers
using the pinned Collector Contrib image. No native Mac runtime claim follows
from these checks.

Next: install on the Mac after acceptance, complete organisation/retention setup,
then measure idle ClickHouse storage growth and a bounded Gatling run. Compare
written bytes and peak memory with the trial budgets, check accepted telemetry,
and review whether limits or collection scope need adjustment. The Windows lab
has not been redeployed, and Mac measurements have not yet been taken.

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

### SigNoz init command repair

The Mac CPU installation completed verification. Optional SigNoz startup reached
ClickHouse's native init image, but its init container failed with an argument
list too long error. The generated shell argument contained a base64 CA bundle.
Use the public/corporate CA file already installed by `fresh_images` in that
same digest-pinned native image. Preserve download checksum verification,
resource settings and existing volumes.

Next: review this repair, pull it on the Mac and rerun the demo installer.
Confirm ClickHouse, migrations, collector and UI readiness before organisation
setup and the previously planned ingestion/resource measurements.

### Demo migration retry ordering

The Mac checkout contains the CA repair, but its pod still has the old inline
command. The pinned chart uses a pre-upgrade migration hook; that migration
waits for the unavailable ClickHouse before Helm applies the corrected settings.
The demo values now use a normal migration Job, and Helm waits for Jobs as well
as backend readiness. Before upgrading, recreate only the release's labelled
migration Job and retain its available logs. Database volumes are preserved.

Next: accept this installer repair, pull it and rerun the demo command. Verify
the pod receives the short CA-file command, migrations complete and telemetry
arrives. Then exercise the authorised full cleanup and fresh installation loop;
manual cluster patches are not part of the acceptance procedure.

Verification: seven local tests passed, including absent/foreign migration
resources, retained logs and conversion of the old hook service account. The
pinned Helm chart rendered both fresh installation and upgrade with a normal
Job and all migration phases preserved. No live cluster was changed; Mac
readiness remains outstanding.

The first native retry exposed a mismatch in the ownership check: the pinned
chart sets the component label to `signoz-telemetrystore-migrator`. Correct the
expected label and report actual labels if a resource is rejected. Verify both
Job and service-account labels against the pinned chart render before the next
Mac retry. Foreign resources remain protected.

Verification: the ownership check accepted actual Job and service-account
objects from all four pinned chart renders (install/upgrade, normal/old-hook).
Seven local tests passed, including foreign-resource rejection. No live
cluster changes were made. Next: merge, pull and rerun the demo installer.

### ClickHouse memory and liveness on the Mac

The supplied pod diagnostics confirm the UDF init completed with exit code 0.
ClickHouse reached ready-for-connections, then background merges exceeded its
1.5 GiB internal server limit. Kubernetes events show one-second liveness
timeouts and explicit restarts; exit code 137 is not sufficient evidence of
a kernel OOM kill. Increase the demo container memory limit from 2 to 4 GiB
and its internal limit from 1.5 to 3 GiB. Request 1 GiB and 0.5 CPU, preserve
the 2 CPU limit and 1 GiB per-query limit. Give health checks five seconds,
with approximately two minutes of sustained failure before a liveness restart.

Next: review and retry through the installer. Confirm ready pods and successful
migrations, then complete organisation setup and measure ingestion, idle growth
and bounded demo load. The new 6 GiB steady/8 GiB startup headroom figures are
trial budgets, not measured requirements. Keep the authorised clean-install
rehearsal as the final acceptance step.

Verification: seven local configuration/retry tests passed. The pinned upgrade
render contains the 4 GiB container limit, 1 GiB request, 3 GiB internal ceiling
and both active health probes with the reviewed timings. No live cluster was
changed; this does not establish native readiness or a sufficient permanent
resource budget.
