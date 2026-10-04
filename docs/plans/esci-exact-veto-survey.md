# Check Exact decisions with the cached 2B model

Status: isolated runner and analysis prepared and CPU-tested; no model calls or
new GPU grant. See the [preparation evidence](../research/evidence/esci-role-check-preparation.md)
and the next [execution batch](esci-role-check-execution.md). The
[category survey](../research/evidence/esci-category-survey-results.md) made the
same 14 errors under every contract, already present in raw model decisions.
Test whether a different, smaller question-conditioned model can reject those
Exact mistakes and identify useful non-Exact relationships.

Use the cached Decider2B checkpoint without an additional ESCI adapter. The previous ordinal membership
adapters already tested related ideas; do not repeat them. This proposal changes
the model and decision structure, without training or downloading weights.

## Scope and contracts

The prepared packet contains **128 pairs across 108 normalised query groups**:
all 80 additional Exact decisions from contract A, plus 48 pairs selected by a
fixed identity hash from the other 282 residual pairs. All are from the exposed
quick-development packet and were unresolved by the retained prefix. This
deliberately selected sample cannot estimate full-pool coverage.

| Item | Fixed requirement |
| --- | --- |
| Model | Cached `Mapika/decider-2b` revision `533964dae8be954c5b5e19fa4948e48408094c1e`; verify its immutable cache manifest. The upstream checkpoint contains a merged adapter; add no lab ESCI adapter |
| Runtime | Pinned `decider-ai==1.6.0`; new isolated direct `Decider` runner, no external four-class mapping. Plain `choice` questions use the cached temperature 1.164; bind source, formatter, tokenisation and numerical settings |
| Input | Same query and product text, full category hierarchy; no published label, prediction, identifier or other answer-derived field in model text |
| Question 1 | Does the product itself meet the requested role and every explicit requirement? Answers: meets, does not meet, insufficient evidence |
| Question 2 | For a non-Exact product, is the supported relationship Substitute, Complement, Irrelevant or insufficient evidence? |
| Ambiguity | Do not invent query intent or compatibility. Unsupported decisions abstain |
| Experimental threshold | Saved raw answer probability ≥0.90; no threshold search or fitted score mapping |
| Exact check | Retain an A additional Exact only when question 1 says meets at the fixed threshold; otherwise abstain. Preserve earlier prefix decisions |
| Non-Exact route | Only when question 1 says does not meet at the fixed threshold, allow a supported S/C/I from question 2 at the same threshold; otherwise abstain |
| Other residuals | Question 1 saying meets in the 48 A-abstained pairs still abstains. This survey checks existing Exact claims and supplies S/C/I; it introduces no new Exact route |

The full questions and input hashes are retained in ignored state at
`.lab/esci-category-increment/exact-veto-proposal-03/`. They were prepared after
the category outcomes were read; they are a new development hypothesis, not
fresh confirmation. The 0.90 threshold is an exploratory fixed choice and does
not imply equivalent calibration between the two models.

## Work and acceptance

1. **Verify and register execution.** Integrate the prepared isolated runner with
   the owner's worker and new source-bound grant: the
   current `FixedDecider` requires four options and the lab engine injects the
   ESCI adapter. Neither supports this contract unchanged. Direct Decider
   supports the proposed three- and four-option questions. Verify the model
   identity, complete input rendering and token budget; freeze `choice` rather
   than typed Boolean answers. Use one question in a singleton row per call;
   packing both questions changes conditioning.
   Freeze source/runtime hashes, prompts, option order, sample, analysis and
   stopping rules before any new prediction.
2. **Obtain a separate exclusive GPU grant.** The approved interrupted-run grant
   binds the completed four-contract 512-pair study. It cannot authorise this
   new model or another window. Retain explicit scope approval and the owner's
   source-bound lease, process identities, fixed deadline and cleanup receipts.
3. **Run bounded inference.** Allow at most 384 singleton evaluations: two
   questions × 128 development pairs, plus two questions × 32 numerical pairs
   in forward/reverse order. Numerical pairs are a fixed hash-selected subset.
4. **Check timing and numerical stability.** Set the prediction cutoff to grant
   acquisition +15 minutes, including startup, and the cleanup deadline to
   acquisition +20 minutes. After the first eight calls and each subsequent
   32 calls, stop if measured remaining time projects past the prediction cutoff.
   Reserve the last five minutes for cleanup. Require
   maximum raw probability difference ≤0.00001 and no decision flips. Preserve
   failed attempts; do not extend the grant or retry inside a replaced record.
5. **Measure useful changes.** Keep existing prefix decisions. Report each
   candidate's additional labels, class support, harmful errors and correct
   Exact decisions lost to the veto. Use paired whole-query intervals; show the
   80-pair and 48-pair strata separately. Agreement is a routing input, not truth.

Advance the Exact check only if it removes at least two of the four known
Irrelevant → Exact errors while retaining at least 53 of the 66 correct A
additions (80%). Advance the non-Exact route only if it adds at least ten S/C/I
labels **in the 48 A-abstained pairs**, with at least 95% point accuracy and no
observed Exact → Irrelevant error. Corrections among the 80 A-accepted pairs
improve accuracy but do not add coverage; report them separately.

These are **survey selection rules**, not quality qualification. Report their
uncertainty, full confusion counts and class/query support for E → I, E → S and
E → C. The S/C/I-only route cannot emit I → E by construction; check that
contract rather than claiming an empirical rare-error result. Missing support
remains unavailable. If neither signal appears, retain the failure and stop
this approach.

## Constraints and next decision

- Open no new reference cohort, fitting reservation, confirmation output or
  specialist query. No model calls until the new execution and grant are valid.
- Keep T1 and the full category study stopped. Start no second GPU job or watcher.
- Do not relabel published references, select a threshold from these outcomes,
  register an active release or alter deployed defaults.
- Retain raw probabilities, exact formatter/token audits and per-source evidence.
  A rejected Exact is an abstention unless the separate non-Exact route supports
  a label; it does not automatically become Irrelevant.

A useful signal justifies separately frozen calibration and confirmation work.
Apply the existing [cascade confirmation policy](esci-cascade-confirmation.md)
before activation, including independent actual-gap human references. Those
references are currently absent.

If bounded model surveys still cannot supply the required labels, prepare a
human-review proposal for a temporary, exact-commit gate exception. It must show
the remaining coverage gap, preserve source provenance and prioritise
Irrelevant → Exact protection. Do not issue an exception automatically.

Finish with measured evidence, the updated [roadmap](roadmap.md), a next detailed
plan and separate Gitea/GitHub review batches. Main merges require acceptance.

## More information

- [Completed category results and limitations](../research/evidence/esci-category-survey-results.md)
- [Residual cascade and exclusions](esci-residual-cascade.md)
- [Blinded actual-gap review preparation](esci-gap-review-packet.md)
- [Decider2B classification interface](https://huggingface.co/Mapika/decider-2b)
- Research owner: `.lab/esci-model-agent-repo/esci-tfm-experiment/`; execution
  controls in `operations/category_gpu_controller.py` and
  `operations/category_gap_grant.py`. Existing controls must be verified for
  the new contract before reuse; this proposal is not an executable grant.
