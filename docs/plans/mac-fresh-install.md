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

## Next detailed plan: complete the application setup

1. Review and merge the foundation batch, then run it on the disposable Mac.
   Record image-pull, node restart, HTTPS and native resolver results. Retain the
   original Windows lab for recovery. Test cleanup on that disposable target.
2. Extend installer ownership records to external Nexus/PostgreSQL and snapshot
   stores before automating their creation and deletion. Add fresh ESO/Key Vault
   setup and named OIDC sign-in without transferring old credentials or keys.
3. Add deterministic catalogue import and publication, with the full English
   ESCI release by default and a configurable small demo release. Reuse existing
   immutable data contracts and include only the CPU abstaining judge. Do not
   install or transfer historical gap-filling models or GPU jobs.
4. Seed source/state repositories once, configure scoped runners, await a
   successful native baseline build, publish the control/evaluator/notebook
   images and activate the control PVC once. Existing baseline-run and state
   prerequisites must be supplied or derived explicitly, not guessed from old
   Windows run numbers.
5. Reconcile delivery Actions, demonstrate one comparison/notebook and reviewed
   promotion in the UI. Add restart and selective cleanup acceptance for this
   complete topology before describing the installer as a full lab setup.

Acceptance is required before main merges. No original-lab deletion, deployment,
inference or load test is part of this implementation batch.
