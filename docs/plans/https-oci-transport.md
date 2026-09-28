# Next batch: HTTPS OCI and host transport

## Intent

Move Gitea and Nexus image push/pull to CA-verified HTTPS from the Actions runners and k3d nodes. Give host Git/API scripts a repeatable HTTPS DNS and trust path on Windows, with an equivalent procedure for native Apple silicon. Keep the local architecture and immutable image references.

## Constraints

- Do not disable TLS verification or replace digest-pinned releases with mutable tags.
- Keep Gitea and Nexus credentials in their current vault-backed or bootstrap sources. Do not commit CA private keys or runner registration material.
- Prove Docker-in-Docker and node/containerd trust separately; changing a browser URL alone cannot secure OCI traffic.
- Change repository workflow URLs only after the corresponding runner and host trust checks pass. Preserve the existing PR review process.
- Measure the effect on image pull/build time before adjusting lifecycle targets. Keep internal HTTP service hops explicit in the topology.

## Acceptance criteria

1. A runner pushes an image to each used registry over HTTPS, and a fresh Kubernetes Pod pulls a digest reference with verified trust. The lab's insecure-registry entries for migrated names are removed.
2. Nexus release publication and Gitea package publication still produce the same immutable digest and provenance contracts.
3. Host Git and Gitea API tools use a documented HTTPS name and CA on Windows; Apple silicon has an executable bootstrap route and a separate native check.
4. The reviewed search-spike fixture workflow is merged, then a merged-source run proves its default branch fetches over HTTPS. Existing delivery promotion and rollback checks remain healthy.
5. Webhook URLs and the protocol inventory identify every remaining HTTP path and why it remains.

## Starting points

- [HTTPS Git client inventory](../https-git-transport.md)
- [Local HTTPS ingress](../https-ingress.md)
- [Reference CI/CD](../delivery.md)
- [k3d registry configuration](https://k3d.io/v5.9.0/usage/registries/)
- [Gitea container registry](https://docs.gitea.com/usage/packages/container)
- [Nexus reverse proxy](https://help.sonatype.com/en/run-behind-a-reverse-proxy.html)
