# Role-check preparation

The cached-model role experiment has an isolated runner and development
analysis, verified on the Windows host on 4 October 2026. **No real-model calls
have been made.** This batch prepares the next bounded survey; it adds no
judgements and leaves the 80% gate unchanged.

## Observed checks

| Check | Result | What it establishes |
| --- | --- | --- |
| Synthetic CPU tests | 71 passed in 22.52 seconds | State rendering, complete prompt budgets, singleton backend contract, probabilities, fixed routing, matched analysis and missing-support behaviour |
| Ruff | Lint passed; all four Python files formatted | Source checks, not relevance quality |
| Input compilation | 128 development pairs / 108 query groups and 32 numerical pairs / 29 groups | Every rendered state is byte-identical to the original C/D hierarchy projection |
| Source review | No substantive blockers | Direct Decider 1.6.0 API, temperature selection, tokenisation, routing, analysis and guidance match the frozen proposal |

Tests use synthetic records and an injected fake backend. The source review
read the installed API and prompt builder; it did not execute that backend.
Compilation reads input text only. The first manifest attempt used an incorrect
statistical-helper path and failed before writing an output; its source is
retained separately. The corrected attempt completed without changing the
runner or packet.

## Prepared contracts

The model receives query, product title and actual full category path. There is
no old-schema fallback, label input, extra score mapping or model loader. The
owner must inject the separately verified local backend.

| Route | Fixed behaviour |
| --- | --- |
| Earlier cascade decisions | Returned unchanged by the routing function; the 128-pair analysis contains only earlier abstentions |
| Existing 80 Exact claims | Keep Exact only when the role answer supports it at ≥0.90; otherwise abstain or take a supported non-Exact route |
| Other 48 residual pairs | Add S/C/I only when both relevant answers reach ≥0.90; a role answer saying “meets” still abstains |
| Unsupported answer | Abstain |
| Every new decision | Experimental and ineligible for gates |

The analysis reports the 80/48 strata separately, distinguishing corrections
from new coverage. It retains full class errors, gold support, query groups,
paired whole-query intervals and unsupported selection states. An inability to
emit Exact in one route is not evidence of a rare-error bound.

## Commitments and limits

The [compact validation record](esci-role-check-preparation.validation.json)
contains the proposal, input and source hashes. The ignored preparation manifest
is `.lab/esci-role-check/preparation-01/manifest.json`, SHA-256
`feed77ee49176bff909a55831e0b37ffbacece5f39564c788840383a29df1cd6`.
The manifest binds the installed Decider source inspected; the validation record
also binds the compiled state hashes. These are CPU preparation records, **not**
a grant or execution receipt.

Remaining checks belong to the [next execution batch](../../plans/esci-role-check-execution.md):

- Isolated owner worker, complete checkpoint/tokenizer hashes and actual-runtime
  CPU preflight and token audit.
- New scope approval, exclusive GPU ownership, numerical repeats and the
  fixed 15-minute prediction / 20-minute cleanup deadlines.
- Complete saved predictions, verified cleanup and actual model-quality results.
- Independent published and actual-gap human confirmation before qualification.
  Actual-gap human references remain absent.

The completed category survey's grant cannot authorise this different model and
question contract. Broader research remains halted. Qualified coverage remains
2,946/9,915 (29.71%); no model activation, gate relaxation or human override has
been issued.

See the [experiment README](../../../lab/experiments/esci-role-check/README.md)
for the CPU commands and the [survey proposal](../../plans/esci-exact-veto-survey.md)
for the fixed selection rules.
