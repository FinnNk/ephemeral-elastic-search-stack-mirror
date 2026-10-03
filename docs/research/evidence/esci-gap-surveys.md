# ESCI residual surveys — 3–4 October 2026

The surveys identify a useful selective recalibrator, but do not yet qualify
additional labels or establish a route to 80% coverage. Actual gate coverage
remains **29.71%**.

## Actual result pool

| Measure | Result |
| --- | ---: |
| Frozen queries | 1,000 |
| Unique returned pairs in either variant | 9,915 |
| Qualified published pairs | 2,946 |
| Missing pairs | 6,969 |
| Further qualified labels needed for 80% | 4,986 |
| Additional exact source matches | 0 |
| Eligible isolated-inference pairs | 6,920 |
| Excluded specialist pairs | 49 |

The CPU audit scanned 1,818,825 English source rows using metadata columns only,
including conservative query normalisation and exact product identity. It did
not open source label values or reserved research predictions. The two source
copies are byte-identical. Label reuse therefore cannot improve this capture.

These are retained API observations from 2 October, not a new capture for the
current source heads. Both variants returned the same pool. Of 1,000 queries,
253 have no judged returns; 541 of 995 first results are unjudged. The largest
missing groups are Uncategorised (1,602), Clothing/Shoes/Jewelry (1,376), and
Home/Kitchen (754).

## Development screens

All screens use the already exposed cohort: 6,525 published-label pairs across
400 normalised queries. Confirmation and research final references remain
unopened. Reported accuracy means agreement with those published labels.

| Approach | Observed result | Decision |
| --- | --- | --- |
| Exact ≥0.90 | 2,545 accepted; 94.93% accuracy; 24 I → E errors | Too risky |
| Exact ≥0.95 | 1,046 accepted; 97.90% accuracy; two I → E errors | Conservative comparator |
| Exact ≥0.95 with numeric-model veto | 1,043 accepted; 97.99% accuracy; one I → E error | Useful error-control signal, limited support |
| Margin, entropy, brand and broad category filters | Little added value or substantial loss of correct labels | Do not expand |
| Simple probability and lexical recalibrator | 93 extra labels, 92 correct on 1,306 checking pairs | Prioritise larger independent qualification |
| Nonlinear numeric recalibrator | 130 extra labels, 127 correct on the same checking partition | Secondary candidate |
| Category-role and MiniLM extension | Best simple candidate adds 96 labels, 95 correct | Three extra labels do not justify the added features |
| Same-query published support, character similarity ≥0.90 | 56 extra checking labels, 85.71% accuracy | Insufficient precision |
| Same-query support, MiniLM similarity ≥0.80 | 472 extra checking labels, 86.02% accuracy; five new I → E errors | More coverage, insufficient precision |

The recalibrator fits 4,031 pairs across 248 queries. Separate query groups
select thresholds, and 79 checking query groups supply the reported comparison.
Its 93 additional labels are all Exact. The whole-query bootstrap accuracy
interval is 97.20–100%, but the support and harmful-error evidence are too small
for qualification. Selecting it from this survey requires fresh confirmation.

Support retrieval fixes 30% of each query's products as published supports and
predicts only other products. Target references never enter the support set.
Its checking partition and denominators differ from the recalibrator screen;
the two percentages are not a matched comparison. Even identical normalised
titles did not guarantee the same published label.

MiniLM input generation took 69.39 seconds on four CPU threads for 8,335 unique
texts. No inputs were truncated. The role/embedding extension and support
retrieval remain exploratory; no dependency or model was added to serving.

## Projection on actual gaps

The same frozen recalibrator and thresholds were applied to saved model scores,
without opening gap reference labels or calling an inference service.

| Stage | Additional labels | Coverage if independently qualified |
| --- | ---: | ---: |
| Published source | 2,946 | 29.71% actual |
| Exact ≥0.95 | 934 | 39.13% hypothetical |
| Recalibrator on remaining pairs | 910 | 48.31% hypothetical combined |

That combined projection is 4,790 of 9,915 pairs, leaving **3,142 labels** to
reach 80%. It is not a quality claim about unlabelled products. The reconstructed
fitted model exactly reproduces the frozen development-check probabilities;
its weights, thresholds and source bytes are retained with hashes.

The numeric-model veto changes none of the 934 accepted actual-gap predictions.
The more permissive 0.90 pass supplies 2,099 labels and reaches 50.88%
hypothetically, but its development quality fails the requirements. Lowering a
threshold cannot turn those predictions into qualified labels.

## Other model pilots

| Pilot | Observed result | Decision |
| --- | --- | --- |
| NLI, 256 pairs | 193 seconds of CPU inference; projected 82 minutes for the full cohort | Stop at the fixed survey budget |
| Fixed NLI hypothesis decoder | 32 correct of 256; almost all labels Irrelevant, including many Exact products | No useful immediate label signal |
| Qwen instruction prompts | Eight scores in 93 seconds; projected 149 minutes for the planned survey | CPU configuration exceeds the 15-minute cap |

The NLI model predicts contradiction, entailment and neutrality. The three
retail hypotheses and diagnostic decoder are experimental; their scores are
not calibrated ESCI probabilities. Zero I → E errors are uninformative when no
Exact labels are emitted. This screen does not rule out training a different
NLI specialist.

Only three matched instruction-model pairs completed, so the Qwen pilot cannot
support a prompt-quality comparison or an I → E estimate. Its answer-token
contract worked; one rich input was truncated. The original tokenizer failure
and partial retry are preserved. Both pilots used four CPU threads and released
their model processes. Neither used the GPU or opened confirmation references.
Other lab and research work was running concurrently. These rates describe
the observed CPU configurations under that load, not isolated hardware limits.

Models: [NLI MiniLM](https://huggingface.co/cross-encoder/nli-MiniLM2-L6-H768),
revision `b95119ce93d3e065de6214e38cd4a97b0f2f2c6d`, and
[Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct),
revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`. Their cards describe
Apache-2.0 licensing; the NLI card lists SNLI and MultiNLI training.

## Pending work and limits

The research session owns the GPU category study: broad category, actual leaf,
full hierarchy and hierarchy with explicit role/compatibility instructions.
Their prepared contracts and tested runners do not establish accuracy or lift.
Its watcher waits for a complete saved classifier boundary; the current runner
has no partial prediction checkpoint. The owner estimates about 13 hours to
that boundary at the observed rate. A shorter matched survey is being prepared;
GPU concurrency remains an assessment request, with no second GPU job launched.

No published-label result establishes accuracy on unlabelled retrieved products.
Independently blinded gap references are still required by the current quality
plan. Upstream pretraining exposure is unknown. There is no candidate activation,
gate-policy relaxation or human exception in this batch.

The ignored evidence is under `.lab/esci-gap-surveys/`: residual audit,
selective survey and follow-up, specialist survey and projection, input
embeddings, and both support surveys. Aggregate file hashes will be retained
in the [receipt](esci-gap-surveys.json). Pair records, queries and weights stay out of Git.

Thirty-four focused software tests, Ruff and whitespace checks passed. Local
links in the new plan, evidence and experiment guide were checked. These checks
cover software and documentation integrity; the measurements above describe
the separate model evidence and its limits.

Next: [qualify complementary stages](../../plans/esci-residual-cascade.md#next-batch-qualify-complementary-stages).
