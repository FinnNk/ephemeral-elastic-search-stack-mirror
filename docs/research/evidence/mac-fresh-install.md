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

## Registry correction verification

The Mac retry reported HTTP 403 while pulling Elastic images. Both official
Docker Hub releases were inspected without deploying: ECK 3.5.0 has index digest
`sha256:b6f261372d9d9af7b00aab03efea25263314d16063c4d440ac322e52c2fdf314`;
Elasticsearch 9.5.4 has index digest
`sha256:82ac14f43fe701992e601f4cc81e1c0d7dbc5a2576d8cd736006452925df4026`.
Both contain amd64 and arm64 images. The updated installer selects these
sources and reconciles them when resuming completed stages. Elasticsearch
readiness waits for the current observed generation, Ready phase and green
health so a previous healthy status alone cannot complete the check.

All 21 installer fixture checks passed, including the new source overrides,
preserved Elasticsearch version/storage, completed-stage reconciliation and
image-only patch. These do not establish registry access from the corporate Mac;
that remains the target retry. The original lab was not changed.

## Limits and next acceptance

These checks do not establish native Mac installation, corporate network access
on the target, browser login, real cleanup or whole-lab readiness. Run the
foundation installer on the disposable Mac, check native DNS/HTTPS and node
restart, and exercise cleanup there. Catalogue, CI, OIDC and delivery runtime
automation remains the next [detailed plan](../../plans/mac-fresh-install.md).
