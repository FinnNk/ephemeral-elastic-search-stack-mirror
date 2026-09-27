# Batch 7g: portable release CI

## Intent

Run the same build logic under Gitea Actions and, later, GitHub Enterprise Server. Publish an immutable release which downstream environments can deploy without rebuilding.

| Work | Acceptance criterion |
| --- | --- |
| Shared workflow | `.github/workflows` uses common triggers, jobs, shell steps, `github` context aliases and explicit secrets. Gitea is configured to discover it. |
| Exact checkout | Fetch and verify the event SHA. Record source repository and SHA in release metadata. |
| Test and build | Application tests pass before publishing; build amd64/arm64 images and retain digest metadata. A deliberate failing test prevents a release. |
| Frozen bundle | Package the chart, query assets and schema contract with deterministic hashes. Reject missing or malformed content. |
| Immutable publication | CI uses a scoped Nexus publisher. Release descriptor is written last; repeat publication verifies existing bytes. |
| Provider boundary | Gitea setup/status/PR API calls are separate from reusable build and release logic. Document exact GHES substitutions and untested gates. |
| Demonstration | Source PR build and accepted source build run on the local runner in a dedicated demo repository. Record timings and URLs. |

## Constraints

- Keep existing Gitea image builds and historical build-run references working.
- Do not copy provider tokens into build layers, Git URLs, artifacts or logs.
- No environment approvals, marketplace dependency chains, provider artifact upload actions or provider cache semantics are required.
- Merged source releases use the merged SHA; PR evidence cannot approve a different merged SHA.
- CI failure and malformed release tests verify consequential boundaries; avoid tests that merely repeat implementation details.

## Information

[Reference contract](reference-ci-cd.md), [Nexus foundation](nexus-artifacts.md), `lab/search-app`, `lab/pr_workflow.py`, `lab/index_recipe.py`, `research/platform-spike/chart` and [Gitea Actions differences](https://docs.gitea.com/usage/actions/comparison/).

At completion, record evidence, update the roadmap and write the detailed promotion/deployment plan before opening the batch PR.
