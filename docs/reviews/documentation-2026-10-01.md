# Documentation review — 1 October 2026

The documentation needs a clearer separation between **using the lab**, **understanding its contracts** and **reading its history**. Several current guides require the reader to reconstruct a procedure from implementation notes. Passing code checks would not detect that problem.

## Scope and method

Reviewed the repository's 116 owned Markdown pages at `2afdc6e`, including the proposed developer-guide changes in PR #57. Gitea main was `20418a3`; its older variant guide did not yet include that PR's rewrite. The separate source README and gate README are published from the bootstrap templates; their proposed changes are in source PR #13.

| Group | Pages | Review performed |
| --- | ---: | --- |
| Current guides and references | 22 | Reader-path content review of 21 pages; design reviewed for opening, structure, navigation and consistency with the current workflow |
| Batch plans | 47 | Structure, openings, navigation and separation of historical status from current status |
| Evidence | 32 | Structure, openings, limitations and historical/current distinction |
| Research | 12 | Purpose and historical/current distinction; closer review of platform, snapshot, Key Vault, synthetic traffic and million-release guides |
| Decisions | 3 | Status and navigation consistency; no architectural acceptance inferred |

The [inventory](documentation-inventory-2026-10-01.csv) names every page and its review scope. Structural review is not a line-by-line verification of historical measurements or every command. Imported Archify notices and untracked research drafts are excluded. Diagram gallery copy and the renderer's view list were also inspected; generated diagrams were not regenerated or newly visually certified.

Applied [technical authorship guidance](../technical-authorship.md): reader and purpose, direct language, useful structure, complete instructions, related-page consistency and honest evidence. Paragraph length and keyword searches helped locate dense passages; they were not quality scores.

## Findings and actions

“High” means a reader can follow the wrong operating path or cannot complete the intended task. “Medium” means navigation, interpretation or maintenance is unnecessarily difficult.

| Priority | Pages | Finding and reader impact | Action |
| --- | --- | --- | --- |
| High | [Lab guide](../../lab/README.md), [control runtime](../control-runtime.md) | The lab guide instructs users to launch host control/watch processes, while the active reference hosts those services in Kubernetes. Fixed run IDs and experimental walkthroughs obscure the normal path. | D1: lead with the deployed control service, explain how to obtain build IDs, and separate disposable research replays. |
| High | [Delivery](../delivery.md), [data contracts](../data-evaluation-contracts.md), [judgement resolution](../judgement-resolution.md) | Some examples require ignored local artefacts, fixed recipe hashes or lists of flags whose values have no complete acquisition procedure. A clean checkout cannot follow them unaided. | D2: give prerequisites, input sources, complete commands, outputs and recovery; separate engineer and operator steps. |
| High | [Identity](../identity-boundary.md) | The opening describes a loopback-only service. Kubernetes installation binds the server to `0.0.0.0`; browser ingress has since been added. The code still emits cookies without `Secure`, so replacing the old wording with a claim of fully secured HTTPS sessions would also be wrong. | D1: document the actual serving and host-validation boundaries, cookie behaviour and remaining limits against installation and ingress code. Do not silently change the security implementation during editing. |
| Medium | [Variant evaluation](../variant-evaluation.md), source gate README | Main retained the dense guide; the pending rewrite still used an incomplete capture-command fragment and unexplained input terminology. | Corrected the entry point, input origins and engineer/operator responsibilities here. Gate README corrections remain in parent PR #57 and source PR #13. D2 completes the linked operator procedures. |
| Medium | [Root README](../../README.md) | The first action was buried among milestone and evidence paragraphs. Readers could not easily choose setup, development, evaluation or operation. | Replaced with a task table, component summary, limits and contributor link. |
| Medium | [Observability foundation](../observability-foundation.md), [backend](../observability-backend.md) | Future-backend wording, older port-forward access notes and dated dashboard results sit among current instructions. Large table cells hide capacity and interpretation details. | D3: separate access and investigation steps from signal reference and dated verification. Retain unknown-on-gap and inconclusive-performance limits. |
| Medium | [Key Vault](../keyvault-secrets.md), [HTTPS Git](../https-git-transport.md), [HTTPS ingress](../https-ingress.md), [Nexus](../nexus.md) | Bootstrap, current operation and migration observations are mixed. Key Vault instructions mention `LAB_STATE_DIR` but some commands still hard-code `.lab/kubeconfig`. | D1: reconcile state paths and endpoint purposes; link migration measurements as evidence. Preserve the bootstrap-secret boundary. |
| Medium | [Model installation](../esci-model-installation.md) | Ordered packaging steps are useful, but machine-specific research paths and implicit activation commands need clearer input origins and operator actions. | D3: retain qualification and rollback limits, distinguish packaging from activation, and complete the activation procedure. |
| Medium | [Gatling](../../lab/gatling/README.md), [lab performance workflow](../../lab/README.md) | Required deployments, credentials and forwards are explained after commands. Probe output and a performance verdict are easy to confuse. | D2: put prerequisites first and explain where run IDs and the verdict come from. |
| Medium | [Design](../prototype-design.md), [diagram guide](../diagrams/README.md) | Current contracts, original proposals and implementation updates share long sections. The stated fourteen Archify views were stale: the renderer lists fifteen, alongside seven C4 views. | Corrected counts here. D4: organise current contracts and design decisions without losing constraints or historical evidence. |
| Medium | [Plan index](../plans/README.md), [roadmap](../plans/roadmap.md), [ADR index](../adr/README.md) | Multiple current-status narratives diverge. Some already implemented batches still say “ready for review”; ADR acceptance cannot be deduced from implementation alone. | Simplified the plan index here. D4 checks status against accepted PRs and leaves architectural acceptance to its decision owner. |
| Medium | Research and evidence records | Statements such as “SigNoz was not installed” or “the API is a host process” are valid for the recorded run but can be mistaken for current instructions when linked without context. | D5: label dated scope at entry points and repair navigation; preserve measurements, conditions and limitations. |

## Checks and limits

- Inventoried all owned Markdown pages and checked local file-link targets. The only apparent missing targets in bootstrap READMEs are deployment-relative source paths, valid after publication into `delivery-source`; they are not broken repository-guide links.
- Checked the identity finding against `lab/control_api.py`, `lab/control_identity.py` and `lab/control-runtime/install.py`. Checked diagram counts against `docs/diagrams/render.mjs`.
- Reviewed the changed README, variant guide and contribution requirements as a combined reading path. The variant page now describes the workflow and handoff; it does not pretend that tool filenames alone are runnable operator instructions.
- Rendered the changed entry-point, variant, policy and review pages to local HTML with Markdown tables. The browser preview failed to start because the Windows sandbox reported a setup error; visual inspection of that preview is incomplete. Changed-page local file targets and `git diff --check` passed.
- Did not replay historical experiments, activate models, change live services, or validate Linux/macOS execution. This review does not establish cloud portability, relevance quality or historical metric accuracy.

This batch establishes enforceable review instructions and fixes the entry points. It does **not** declare all existing pages compliant. The [remediation plan](../plans/documentation-authorship.md) tracks the remaining reader-facing work in reviewable batches.

## Follow-up: D1 operating guides

The next branch rewrites the lab, control, identity, secrets, HTTPS and Nexus operating guides. It supplies current paths, input origins, expected outcomes and recovery, and moves historical measurements out of the ordinary task flow. Two actual UI/saved-notebook illustrations have [capture notes](../screenshots/README.md).

The read-only control smoke check passed. A CA-validated control ingress request returned a redirect to HTTP localhost, confirming the documented routing limit. The cookie still lacks `Secure`; that implementation gap remains open. D1 does not claim to fix transport or identity in code.

The branch also resolves the earlier browser-preview limitation using headless Edge and records rendered-page inspection. D2–D5 findings remain open under the [batch plan](../plans/documentation-authorship.md).

## Follow-up: D2 evaluation and delivery

The current guides distinguish source acceptance from deployment, obtain inputs from retained manifests/receipts and supply complete capture, scoring, attestation, exception and promotion commands. The operator runbook replaces ignored historical fixtures. Judgement pooling and Gatling prerequisites/outcomes are explicit. Source templates are corrected; source PR #13 remains open for the separate demo/code change.

CLI help for seven operator tools passed. A disposable 12-product/3-query pack and local manifest publication passed. Seven revised guides were rendered in headless Edge: each had one title, loaded images and no viewport overflow; the delivery opening and diagram were visually inspected. Local links/anchors were checked, including repaired inbound anchors. These checks do not validate a new live comparison, release or human approval. Linux/macOS execution remains untested.

## Follow-up: D3 models and observability

The model guide now separates portable bundle installation from research-author inputs, registration from serving, and numerical qualification from accuracy. Complete commands preserve API replicas and live resources, update the actual 10k/1M container names, and restore previous pins/images after failure. They were checked against code/manifests, not executed on a GPU.

The telemetry guides lead with current HTTPS access and an investigation sequence. Dashboard trends, input-selection shift and coverage-verified SLO verdicts have separate limits. Fixed dashboard IDs, pending-invitation claims and host-capacity history moved out of the current procedure. Four CLI help checks passed. Three pages rendered in Edge with one title, no viewport overflow and no missing images; the backend opening was visually inspected. Related anchors and diff formatting were checked. No dashboards, accounts, models or telemetry services were changed.

A second implementation finding is now tracked: non-empty request filters can be recorded but are not applied by the capture/API path. Empty-filter synthetic suites are unaffected; unsupported inputs need an explicit rejection before capture.
