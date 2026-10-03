# ESCI inference contract — 3 October 2026

**The singleton release is not numerically qualified.** MLflow version 3 is
registered but inactive; the lab uses `synthetic-esci-judge/1`. The probability
tolerance remains 0.0001, acceptance threshold 0.90 and coverage gate 80%.

## Release and independent references

The release uses the original Decider 4B weights, unmerged v3 LoRA adapter and
learned four-score mapping. It declares `singleton-fla-v1`: each pair runs alone
internally, including when the HTTP caller sends a batch. Context budgeting,
padding, BF16, SDPA, FLA, convolution and precision settings are explicit.

| Identity | Value |
| --- | --- |
| MLflow model | `synthetic-esci-judge/3` |
| Release SHA-256 | `f002bc1e73fc2649e370702781514a3c3f1b4276d4038c147f0f4fea430a3a16` |
| Registered artefact SHA-256 | `16a1701aa616ac2b00ccd5532cfad3a938da52ab6d7e2043c8f1437eaa8c4691` |
| Tested image digest | `sha256:ad5333062cb58f3f61929ccc2a70f0f46a7e18ccdf4d9ac6c3419e0a227dd816` |
| Frozen input SHA-256 | `cd8a63848afd46dadbbf9a38e6232b38dee942ca74d0bfa05a444cb5f2611cf2` |
| Independent reference SHA-256 | `454270aaca5f3ad8038f32d1dbece24b4cb1b2cb0f0c948dbda07f65665a3680` |

References were generated with the original research loader and original fitted
sklearn mapping, not the serving wrapper. All 7,393 exposed pairs across 457
queries passed the normalised reservation and rendered-input audits. No protected
final-assessment or specialist query was inferred. Original sklearn 1.7.2
reproduces the mapping calculated under the reference image's sklearn 1.9.1 to
within 3.33e-16 across every pair.

## Runtime checks

The image pins FLA/Triton and verifies the selected FLA functions. Missing
compiler support now fails startup instead of silently selecting the PyTorch
fallback. The optional worker exposed the real CUDA driver but lacked the
unversioned linker library needed by Triton's host helper. A checksum-pinned
NVIDIA SDK stub fixes linking; its directory is excluded from
`LD_LIBRARY_PATH`, and the runtime still loads the injected real driver.

A live Pod verified successful driver initialisation and FLA selection. A
negative test with an unavailable compiler failed as required. The actual image
digest was checked in both candidate Pods. The earlier failed startup and all
partial diagnostic outputs are retained.

A supplied trace parent reached `model.http` and its `model.predict` child in
SigNoz. Version 3's prediction counters include both labelled and abstaining
outcomes; no query or product text appeared in the inspected span attributes.
This proves the direct candidate HTTP/export path, not a new full judgement-API
rehearsal with version 3.

## Measured results

| Comparison | Pairs | Above tolerance | Changed labels/abstentions | Maximum difference |
| --- | ---: | ---: | ---: | ---: |
| Independent singleton reference → first KServe pass | 7,393 | 4,641 (62.78%) | 24 | 0.0230935 |
| First KServe pass → interrupted identical repeat | 4,608 | 0 | 0 | 0 |
| First KServe pass → fresh Pod | 7,393 | 0 | 0 | 0 |

The first-pass change rate is 0.325%; its 95% whole-query bootstrap interval is
0.201%–0.460%. Ten pairs changed from abstention to Exact, and fourteen changed
from Exact to abstention. They span 23 queries. Differences above tolerance have
a 95% query-bootstrap interval of 61.56%–64.03%. These intervals describe exposed
diagnostic inputs, not independent label quality or production traffic.

The 64 canaries returned identical outputs across batch, singleton and reversed
HTTP requests, but all arrangements failed reference agreement: maximum
probability difference 0.0118047. None of those 64 decisions crossed the threshold.

After the full first-pass failure, the remaining full warm-repeat arrangements
were replaced by cold-start and kernel-selection controls. The retained repeat
covers all 457 queries, but it is not a completed 7,393-pair repeat. A zero-change
repeat establishes stability on those observations only.

## Cause and controlled replay

FLA/Triton automatically chooses how GPU calculations are split into blocks.
Different choices can change floating-point rounding even with identical weights,
inputs and package versions. Five fresh-process probes retained the six selected
kernel configurations on the same 256-pair prefix. The original research loader and
serving loader could reproduce the reference raw scores exactly, but later
serving processes selected different configurations and changed scores.

| Control on 256 pairs | Maximum mapped difference from reference | Difference from KServe |
| --- | ---: | ---: |
| Frozen reference configurations | 2.22e-16 | 0.0141498 |
| Change triangular-solve tile from 64 to 32 | 2.22e-16 | 0.0141498 |
| Change output tile from 128×128 to 64×64 | 0.0139493 | 0.0141498 |
| Change normalisation grouping from 8 rows / 8 warps to 32 rows / 4 warps | 0.0146186 | 0.0141958 |
| Change recomputation from 8 to 4 warps | 2.22e-16 | 0.0141498 |
| Apply the three recorded serving changes together | 0.0141498 | **0** |

The combined settings recreate every KServe vector in the control exactly.
Changing normalisation and output configurations separately demonstrates their
numerical effects; the two negative controls showed no effect on this set.
Installed package versions and the name “FLA” do not fully specify the numerical
execution: runtime tuning choices also matter.

The exact registered MLflow package reproduced KServe's mismatch. Within that
process, direct engine calls, MLflow calls, the predictor function and newly
created request threads all returned identical vectors. Input serialisation,
wrapper conversion and request threading do not explain this control's drift.

Using FLA's supported `FLA_CACHE_MODE=default` and `FLA_CONFIG_DIR` restores
reference agreement through all five paths: maximum difference 2.22e-16, zero
changed decisions. Two isolated direct processes using the fixed profile also
reproduced the reference raw vectors exactly. No kernel was monkeypatched.

These were diagnostic overrides, not a newly qualified registered release.
The profile must be included in the model's immutable identity, checked for
completeness and validated in KServe. Upstream cache modes can retune when a
configuration is missing; merely setting the environment variable is insufficient.

### Full fixed-profile diagnostic

The registered package's predictor function was then run on all **7,393 pairs
across 457 queries**, using newly created request threads, four CPU cores and a
24 GiB container limit. The fixed profile agreed with the independent references:

- Maximum probability difference: **4.44e-16**.
- Pairs above 0.0001: **0**.
- Actual changed labels or abstentions: **0**.
- Inference collection: **986.38 seconds**, excluding download, verification,
  model loading and warmup.

This larger result supports freezing the profile. It does not qualify a new
release: the overrides are not yet part of the registered model contract, and
full HTTP arrangement/repeat/cold-start checks under that contract remain.
The different collection paths and CPU limits prevent a clean performance
comparison with the earlier HTTP pass.

## Cost and limits

On a 512-pair control, singleton inference took 62.42 seconds, followed by warm
repeats of 62.98 and 63.81 seconds. Eight-pair inference took 53.17 seconds:
singletons were about 17% slower on that run. Peak allocated GPU memory fell from
9.63 GB to 8.90 GB. These are inference measurements, not Gatling load tests;
there was one eight-pair timing run, and no timing confidence interval.

Singleton execution fixes caller-dependent tensor batching, but the default
version 3 reference comparison still fails. Fixed-profile diagnostics pass; their
configuration needs to become part of a new immutable release. Registration, startup and CPU tests do not establish
numerical qualification. Label-quality assessment and activation remain blocked.

Raw inputs, scores and failed logs remain in ignored
`esci-packaging/inference-contract-20261003` storage. Aggregate results and
provenance can be published without query or product text. The
[next plan](../../plans/esci-kernel-reproducibility.md) requires a demonstrated
cause and fresh-process agreement before full qualification.

[Aggregate results and hashes](esci-inference-contract.json) contain no raw
examples or per-pair probability vectors. Candidate Pods and diagnostic GPU
containers were removed before explicit research handback at 10:57 BST. The
temporary 8.09 GiB registered-model download was removed after verification;
MLflow artefacts and the original release bundle remain available.
