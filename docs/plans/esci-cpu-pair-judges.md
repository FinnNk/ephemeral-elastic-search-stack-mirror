# Test CPU pair models and prompt inference

Status: the small pair model is training within a fixed budget. The alternative
prompt runtime's short probe is complete; analysis and delivery follow next.
Neither candidate is qualified.

## Intent and constraints

Find a complementary judge after the [larger fitting survey](esci-fitted-specialists.md)
found no useful gain from six inexpensive classifiers. Test learned interaction
between query and product, and whether a specialised CPU runtime makes compact
instruction-model surveys practical while research owns the GPU.

- Use the reserved 1,000-query fitting pool and its existing 700/300 query split.
  Do not fit on the exposed development cohort, actual lab gaps or confirmations.
- Keep source labels, identifiers and synthetic price, stock and popularity out
  of model features. Published text can be missing; handle it explicitly.
- Pin weights, prompts, field contracts, code, libraries, seeds and partitions
  before outcomes. Retain failed, partial and successful attempts separately.
- Use explicit CPU execution and bounded threads. Coordinate any GPU work with
  its owner at a saved boundary. Preserve the research reservations and watcher.
- Keep predictions exploratory. No activation, source-policy change or human
  exception is part of this batch.

## Work and acceptance

| Trial | Frozen first screen | Required evidence |
| --- | --- | --- |
| Small pair model | A pretrained 22.7M-parameter retrieval encoder with a fresh four-class ESCI head; one epoch, AdamW at 3e-5, 128 tokens, batch 16, four CPU threads | A 64-update throughput probe; stop if the projected epoch or elapsed training exceeds 30 minutes. Save complete weights before assessment |
| Compact prompt model | Official quantised Qwen 1.5B weights in an isolated llama.cpp CPU runtime; matched exposed-development pairs and the existing three field/prompt contracts | Publisher and file hashes, explicit zero GPU layers, bounded probe, exact prompt/decoder records and cleanup of the owned process |
| Development assessment | Fixed class threshold grid, at least 30 accepted calibration pairs and 98% observed agreement before accepting a class in the screen | Full confusion, per-class support, incremental decisions after the retained two-stage comparator and whole-query uncertainty |
| Residual value | Score eligible unlabelled pairs only if the development screen adds a meaningful, credible number of labels | Separate hypothetical coverage from the unchanged qualified coverage; preserve excluded specialist pairs |

For prompt inference, first establish throughput. If a complete matched survey
would exceed its 15-minute inference budget, retain the partial probe and stop.
Grammar-constrained token scores are not equivalent to probabilities from the
earlier PyTorch contract; assess the new runtime on its own terms.

Do not respond to a failed screen by expanding the same search indefinitely.
Prioritise a promising interaction or category/prompt signal, then freeze one
complete cascade for [independent confirmation](esci-cascade-confirmation.md).
That confirmation still needs independently blinded actual-gap references.

## Where to find the work

- [Previous CPU results](../research/evidence/esci-fitted-specialists.md).
- [Experiment tools](../../lab/experiments/esci-gap-surveys/README.md) and the
  [larger fitting tools](../../lab/experiments/esci-fitted-specialists/README.md).
- Ignored fitting inputs and outcomes: `.lab/esci-fitted-specialists/`.
- Research-owned category plans and controls under
  `.lab/esci-model-agent-repo/esci-tfm-experiment/`.
