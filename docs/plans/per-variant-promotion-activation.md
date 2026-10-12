# Activate per-variant promotion controls

The accepted control code from lab PRs #179/#180 is published and installed in
the Windows lab. The release dashboard now explains the source-controlled
variant intents instead of offering an operator intent selector.

## Observed runtime

On 12 October 2026, the old runtime still served the intent dropdown after the
repository merges. There were no queued or running delivery operations. The
existing runtime installer deployed the new image while preserving the control
volume. Its digest is
`006113b49ad006b4543a7a4a5ef3beb5cd040127d63daaf45e5bbd7cc1eaf0e7`.

The HTML served for `/release-dashboard?run=184` contains the explanation and no
`promotion-intent` selector. The read-only smoke check matched the cluster,
Gitea runtime identity and Elasticsearch 9.5.4, and reached Nexus.

The remaining separate production page still submitted legacy intent fields for
release and rollback. This batch removes those fields and explains the same
source-controlled selection. It requires a further accepted runtime update.

The installed delivery-source client and seven delivery workflows matched the
previous templates. Their separate review batch copies the accepted new
templates without replacing human changes. YAML and Python syntax checks pass;
the matching stack client was covered by the 64 passing unit fixtures recorded
in [test-runtime recovery](test-runtime-recovery.md).

## Next detailed plan

1. Accept the production-page correction and delivery-source template update.
2. Publish and install the corrected control image when its queue is idle.
3. After the source update is merged, reconcile `LAB_DELIVERY_CLIENT_SHA256` to
   the accepted client bytes. Do not change that trusted digest while main still
   contains the old client; the comparison workflow reads its protected base.
4. Verify the dashboard, separate production page and Actions forms, then resume
   the build 184 walkthrough. No promotion or production route switch was
   performed during this runtime update.
