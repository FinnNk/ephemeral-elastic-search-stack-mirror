# Offline variants and merge decisions

**Status:** four review batches are ready. The [managed rehearsal](../research/evidence/managed-variant-gate.md) captures three variants from an Argo-managed source build, blocks the low-coverage live report in CI and passes a separately labelled deterministic fixture. The current reference contract pins the selected variant's image to an attested immutable build receipt.

## Intent

Evaluate two or more frozen Search API variants on one synthetic query suite. Exactly one variant is the runtime default and one is the evaluation baseline; they may differ. A two-version production replacement uses the same contract without an online experiment or traffic splitter. Record a proposed variant and any human exception separately from the measured result.

## Constraints

- Capture the public Search API response for every query and variant. Query understanding, ranking and index changes are all observable at this surface.
- Freeze the variant selector, API/environment fingerprint, configuration fingerprint, catalogue, query suite, judgement set, evaluator and policy. A response that does not echo the requested variant identity is invalid.
- Resolve the union of all returned query/product pairs once. Stored labels win; abstention remains unjudged. All variant scores use that one frozen set.
- Keep the default mandatory. The baseline is selected per evaluation; the release decision may select another variant. A replacement release promotes the selected variant to the new default.
- Use one current multi-variant observation and report contract. Do not add readers or adapters for older pair-shaped artefacts. Historical retained bytes may remain as historical evidence, but are not accepted by this workflow.
- Treat evidence-integrity failures as invalid. A quality result inside a versioned exception band may be approved by an authenticated human without changing the measured verdict. A result outside the band remains blocked.
- Keep policy evaluation and approval provenance independent of Gitea-specific event shapes so the same gate can run under GitHub Enterprise.

## Batches and acceptance

| Batch | Work | Acceptance |
| --- | --- | --- |
| 1. Frozen variants | Variant manifest and explicit Search API selection; finite N-way capture; N-way scoring and pooled judgements; deterministic synthetic fixtures | Two and three variants work, including default ≠ baseline; wrong echo, changed pin, incomplete capture and missing pair fail closed; a two-version replacement needs no runtime flag service. |
| 2. Decisions and merge gate | Versioned gate policy, selected variants, per-variant verdicts and trusted human exception receipt; portable CI command and source workflow wiring | Passing, decision-required, approved-exception, blocked and invalid cases are distinct. An approval binds exact evidence, policy, selected variant, reviewer and reason; an untrusted PR-authored approval cannot pass. |
| 3. Reference proof | End-to-end synthetic run, evidence, operating guide, C4/workflow diagrams and roadmap; clean reference language | Local live API capture and gate examples match the documented contract. Old pair-shaped input is rejected instead of adapted. Each batch is committed and offered as a stacked PR; merge only after acceptance. |
| 4. Managed gate rehearsal | Run `evaluation/capture.py` against an Argo-managed variant environment; publish source-bound evidence after a delivery-source PR commit; verify the declared CI gate and retained decision | The source SHA and immutable build receipt identify the evaluated image and CI verdict. A missing bundle fails. A complete low-coverage report blocks. A separate deterministic adequate-coverage fixture exercises pass and bounded exception mechanics without claiming live model quality. |

## Where to look

- [Data and evaluation contracts](../data-evaluation-contracts.md)
- [Judgement resolution](../judgement-resolution.md)
- [Delivery gates](../../lab/delivery_gates.py)
- [Search API](../../lab/search-app/app.py)
