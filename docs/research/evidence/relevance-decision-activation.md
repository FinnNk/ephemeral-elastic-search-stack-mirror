# Relevance decision activation

Checked on 5 October 2026 against the existing local cluster.

| Item | Observed value |
| --- | --- |
| Accepted lab revision | `750335ecaafebdc7bf69a5faacb5ff504d33b407` |
| Accepted source revision | `715a2a3ed6df60d8acaf85cb7a767413c97dc6a4` |
| Control image | `nexus.localhost:18185/lab-control@sha256:c964e2eff5b723aeedf6edc9f044c7286d62b7786eda3941fd37a193e0e937a9` |
| Deployment UID | `8e13c499-37b2-484b-8bee-5cff05afb246` — preserved |
| State PVC UID | `8d230ba2-7b24-4735-b69d-6674d887a5df` — preserved |

All four control containers use this image. The installed decision module,
browser form, gate verifier and delivery client match the accepted source bytes.
The Actions client, policy and verifier pins were reconciled after checking the
source templates. No queued or running delivery operation was present before
the update.

The read-only control smoke check passed: cluster identity matched, Gitea
identified `elastic-agent`, Nexus was reachable and Elasticsearch reported
9.5.4. It found 156 environment records and 43 comparison records.

Re-running the authentication installer exposed a missing-secret deletion:
the old source signing secrets had already been removed. The installer now
lists existing secret names before deleting those two keys. A second installation
completed successfully with the secrets absent.

No human relevance exception or deployment promotion was requested by these
checks. The browser and Actions decision rehearsal remains part of the
[workstation walkthrough](../../plans/remote-delivery-user-check.md).
