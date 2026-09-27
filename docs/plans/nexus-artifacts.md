# Batch 7f: Nexus artifacts

## Intent

Provide persistent private artifact storage for the reference delivery workflow. Keep the current Gitea registry available for historical environments.

| Work | Acceptance criterion |
| --- | --- |
| Install pinned Nexus Community Edition and PostgreSQL | Both run on the lab Docker network, with persistent volumes and loopback UI access. Database is PostgreSQL; image manifests include amd64 and arm64. |
| Create hosted image and raw release repositories | Anonymous access is disabled; releases cannot be overwritten. |
| Separate identities | Personal administrator, automation administrator, CI publisher and deployment reader have distinct credentials stored outside Git. Reader cannot publish; publisher cannot administer or delete. |
| Connect build and deployment networks | Runner can publish; Kubernetes can pull a private image by digest. |
| Prove persistence and failure behaviour | Artifact bytes survive a service restart; attempted overwrite and reader write fail. |
| Record the next batch | Roadmap status, evidence and portable CI plan accompany the PR. |

## Constraints and decisions

- Nexus and PostgreSQL run as host Docker services on the lab network, as the snapshot store does. This leaves the capped Kubernetes nodes available for search and evaluation. Production topology remains a separate decision.
- Local HTTP is restricted to loopback and the private lab network. GHES/Azure deployments require HTTPS and managed secrets.
- Start with Nexus's Docker hosted format for image compatibility and raw hosted format for immutable release bundles. Native OCI registry enhancements are not required for this slice.
- Use Community Edition; Git PRs provide promotion. Do not depend on paid staging, user tokens or cloud blob-store features.
- Resource allocation is a measured lab trial, not Sonatype production sizing. Community usage limits and retention are documented.

## Sources

- [Nexus container](https://github.com/sonatype/docker-nexus3)
- [PostgreSQL installation](https://help.sonatype.com/en/install-nexus-repository-with-a-postgresql-database.html)
- [Feature matrix](https://help.sonatype.com/en/nexus-repository-feature-matrix.html)
- [Reference CI/CD contract](reference-ci-cd.md)
- `research/platform-spike/common.py`, `runner.yaml` and `k3d.yaml`: existing local infrastructure.
