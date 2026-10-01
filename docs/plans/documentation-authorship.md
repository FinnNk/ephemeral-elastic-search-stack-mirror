# Documentation authorship and remediation

## Intent

Make the reference implementation understandable without knowing its development history. A new contributor should be able to find the right guide, follow its procedure and interpret the outcome.

Authors and reviewers must apply [technical authorship guidance](../technical-authorship.md). The [review](../reviews/documentation-2026-10-01.md) records findings; its inventory distinguishes content review from structural review.

## Constraints

- Use plain British English. Add structure where it helps the reader; do not replace dense prose with dense tables.
- Document the implemented system. Editing a guide does not authorise service reconfiguration or destructive live checks.
- Preserve historical evidence, modelling assumptions, attribution and human amendments.
- Keep shared contracts and policy in one place. Keep source templates aligned with published READMEs.
- Separate policy changes from editorial backfills in commits. Work on branches and obtain acceptance before merge.
- Treat link checks and code tests as supporting evidence, not proof that the writing is usable.

## Batches

| Batch | Scope | Acceptance |
| --- | --- | --- |
| Review and entry points | Repository author/reviewer rules, inventory, findings, root README, variant guide and plan index | Mandatory clarity/structure review recorded; findings and limitations explicit; reader can choose the correct route. Accepted on Gitea main. |
| D1 — Current operation | Lab/control runtime, identity, secrets, HTTPS, Nexus and index recovery guides; comparison and notebook screenshots | Accepted on Gitea main. Current path, state commands, expected outputs and actual security limits are documented; screenshot sources and limits retained. |
| D2 — Evaluation and delivery | Source guides, delivery, input publication, judgement resolution, variants and Gatling | Implemented, awaiting review. Engineer and operator responsibilities explicit; artefact origins, runnable examples, outputs, verdicts and recovery explained. |
| D3 — Models and observability | Model packaging/activation and connected investigation guides | Packaging is distinct from serving; access is current; dashboards and metric limits lead to useful actions. |
| D4 — Design and navigation | Design, diagram guide, roadmap and decision index | Current contracts distinguish proposals and history; status has one owner; diagram sources, terminology and references agree. |
| D5 — Historical records and final review | Research, plans and evidence; cross-references and rendered reading paths | Historical claims retain their conditions; current-entry links identify dated examples; remaining deep checks are completed or explicitly recorded. |

Each batch updates this table and the roadmap, records verification, and creates a PR. Create the next detailed batch plan when completing the preceding one.

## Completed batch: D1 — Current operation

**Reader:** the lab operator connecting to or managing an existing installation. Fresh installation and disposable research replays need clearly identified routes.

### Work

1. Trace the active control deployment through `lab/control-runtime/install.py`, `lab/control_api.py` and `lab/control_identity.py`. Check ingress configuration and the public URL/Host contract. Record any implementation gap separately from an editorial correction.
2. Rewrite the lab guide's opening and control instructions around the Kubernetes-hosted services. Move historical host launcher recipes to a clearly scoped research route if still useful; retain relevant recovery instructions.
3. Align state-directory and kubeconfig examples in the control and secret guides. Explain where build IDs, account names and credentials come from without printing secrets.
4. Give each endpoint its purpose: browser ingress, Git/API transport, registry transport and local diagnostic forward. Link workstation trust instructions rather than duplicate OS procedures.
5. Convert identity/session and account distinctions into concise reference sections. Preserve the actual cookie, expiry, owner and administrator behaviour and enterprise limits.
6. Inspect the rendered pages, follow related links, and check complete affected sections against CLI help and configuration. Use read-only checks; do not rerun setup or rotate secrets solely to validate prose.

### Acceptance criteria

- A reader can identify prerequisites, the first action, expected output and recovery in each procedure.
- The active Kubernetes path and optional local diagnostic/research paths cannot be mistaken for each other.
- Configurable state directories are respected by command examples.
- Current HTTPS endpoints and actual session behaviour agree with code; unsupported security claims are absent.
- The review names pages checked, safe commands run, visual checks and untested platforms.
- No software behaviour, live credentials, historical measurements or architecture is changed by this documentation batch.

### Sources

- [Review findings](../reviews/documentation-2026-10-01.md) and [authorship guidance](../technical-authorship.md).
- [Lab guide](../../lab/README.md), [control runtime](../control-runtime.md), [identity](../identity-boundary.md).
- [Key Vault](../keyvault-secrets.md), [HTTPS ingress](../https-ingress.md), [HTTPS Git](../https-git-transport.md), [workstation access](../workstation-access.md), [Nexus](../nexus.md).
- `lab/control-runtime/install.py`, `lab/control_api.py`, `lab/control_identity.py`, `lab/https_ingress.py` and their actual CLI help. Resolve file names from the checkout before changing examples.
- Dated [Kubernetes control evidence](../research/evidence/kubernetes-control-services.md) and [HTTPS transport evidence](../research/evidence/https-git-transport-2026-09-28.md): historical conditions, not current setup defaults.

## D1 verification and remaining implementation gap

The installed control Pod was 4/4 Ready and its read-only smoke check passed. CLI help and current code/configuration were checked. The control UI was inspected in headless Edge, and the notebook illustration uses retained, hash-verified output without rerunning inference or evaluation. The revised pages were rendered and inspected; local links and affected anchors were checked.

A CA-verified request to the HTTPS control route returned HTTP 307 to `http://localhost:18082/`. The guides now state this limit and the current cookie behaviour. Canonical HTTPS routing and `Secure` cookies require a separate implementation fix; they were not changed in this documentation batch.

[Capture notes](../screenshots/README.md) record the two maintained screenshots. [D2: evaluation and delivery](documentation-evaluation-delivery.md) is the next detailed batch plan.

## D2 verification

Capture, scoring, retention, finite-Job, judgement, attestation and delivery CLI help were checked. A disposable 12-product/3-query pack was generated and its local manifests published successfully; no live comparison, model activation or promotion was performed. The source README templates are already corrected; delivery-source PR #13 remains open for its separate code/demo change and exact-commit evidence. The guides link a complete operator runbook and explain the capture adapter's current empty-filter limitation.

[D3: models and observability](documentation-model-observability.md) is the next detailed plan. Link and rendered-page checks are recorded in the review.
