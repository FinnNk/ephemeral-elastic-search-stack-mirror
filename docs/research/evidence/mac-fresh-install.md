# Fresh-install verification

## Scope and environment

Windows host, Python 3.12 and Docker CLI metadata inspection. No installer,
cleanup deletion, Helm release or Kubernetes manifest was executed against the
original lab. Destructive behaviour was exercised only through mocked Docker
commands and temporary filesystem fixtures.

## Results

- 16 fresh-install checks passed: rejection of existing state and changed node
  identities, failed-stage retention, completed-stage resume, exclusive locks,
  cleanup ownership and path boundaries, extra-node/worktree refusal, explicit
  purge, recorded-volume deletion, in-use-volume failure recovery, invalid PEM
  rejection and explicit missing-backend verification.
- Four existing preview-route checks passed using the retained Azure SDK path.
  The first attempt without that dependency could not import the suite; the
  subsequent run with the dependency passed all four checks.
- Both new CLI help commands succeeded. Git whitespace checks passed.
- Read-only download checks retrieved Argo CD 3.5.3 (59 Kubernetes documents),
  ECK 3.5.0 CRDs (12 documents) and its operator (11 documents). Download bodies
  were parsed as Kubernetes YAML; they were not applied.
- Docker Hub Gitea 28.0.0-rootless resolves to the existing pinned index digest
  `sha256:c168e7ccb767164793a67e1e874639488260795567337452b06292d1515bea12`.
  Its manifest includes `linux/amd64` and `linux/arm64` images.

## Limits and next acceptance

These checks do not establish native Mac installation, corporate network access
on the target, browser login, real cleanup or whole-lab readiness. Run the
foundation installer on the disposable Mac, check native DNS/HTTPS and node
restart, and exercise cleanup there. Catalogue, CI, OIDC and delivery runtime
automation remains the next [detailed plan](../../plans/mac-fresh-install.md).
