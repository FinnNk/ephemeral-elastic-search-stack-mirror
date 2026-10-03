# KServe 0.21 upgrade

## Intent and constraints

Upgrade the controller and CRDs to the 0.21 release. Retain Standard mode,
MLflow version pins, custom runtimes, source judgements and the active GPU
research process. Keep the release assets unchanged and checksum-pinned.

## Acceptance and results

| Required behaviour | Local result |
| --- | --- |
| Controller available | Stable 0.21 multi-platform image; Pod 2/2 ready |
| Existing model and loader preserved | UID and specification checks passed |
| Fresh model deployment | Disposable InferenceService downloaded version 1 from MLflow and returned abstain |
| Judgement API | Stored label, unjudged gap and forged-record rejection passed |
| Repeated installation | Passed without resetting the model |
| Traefik ingress | Applied after user approval; eight fresh reconciliations without the Istio warning; judgement API checks passed |
| Portable installation | Image has amd64 and arm64 manifests; Apple silicon test remains open |

[Operating instructions](../kserve-installation.md) explain the upstream chart
metadata issue. The next identity batch remains
[Gitea and control UI integration](oidc-application-integration.md).
