# Next batch: HTTPS clients and transport

## Intent

Move the lab's Git, webhook and OCI clients onto stable HTTPS names after the browser-facing ingress has been proven. Keep the source, build and deployment contracts compatible with GitHub Enterprise Server and AKS.

## Constraints

- Keep local CA material outside Git. Validate Windows and native Apple silicon trust separately.
- Change one client family at a time; preserve pinned images, existing PRs and deployed environments.
- Do not disable TLS verification to make a client pass.
- Measure any extra image-pull or build latency before changing lifecycle targets.

## Acceptance criteria

1. Gitea Actions runner, control runtime and Argo CD use HTTPS Git or API endpoints with verified CA trust.
2. Gitea and Nexus OCI push/pull work under TLS from the runner and Kubernetes nodes without insecure-registry settings.
3. Webhooks and public Gitea links use the intended HTTPS address; all three delivery targets still promote and roll back.
4. A clean workstation can bootstrap DNS and CA trust through documented, repeatable steps on Windows and Apple silicon.
5. A protocol inventory records any remaining HTTP paths and the reason for each.

## Starting points

- [Local HTTPS ingress](../https-ingress.md)
- [Reference CI/CD](../delivery.md)
- [Local platform guide](../../research/platform-spike/README.md)
- [Gitea reverse proxy](https://docs.gitea.com/administration/reverse-proxies/)
- [Nexus reverse proxy](https://help.sonatype.com/en/run-behind-a-reverse-proxy.html)
