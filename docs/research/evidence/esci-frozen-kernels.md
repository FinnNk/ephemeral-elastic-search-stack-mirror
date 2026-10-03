# Frozen ESCI kernels: serving qualification

On 3 October 2026, candidate `synthetic-esci-judge/4` passed numerical serving
qualification on **7,393 query-product pairs across 457 queries**. It remains
inactive until [independent label quality](../../plans/esci-label-quality.md) is
assessed and reviewed. The abstaining bootstrap model remains active.

## Scope and results

The immutable bundle fixes six FLA GPU kernel configurations as well as the
singleton input and precision protocol. Startup rejects incompatible hardware,
runtime or configuration; prediction verifies the selected kernels before
returning results. There are no compatibility readers or numerical fallbacks.

Independent references used the original research loader and frozen score
mapping. The already-exposed diagnostic inputs exclude protected research
queries. They establish serving agreement, not independent label accuracy.

| HTTP arrangement | Pairs | Summed request time | Changed labels or abstentions |
| --- | ---: | ---: | ---: |
| Batch | 7,393 | 859.0 s | 0 |
| Repeated batch | 7,393 | 852.5 s | 0 |
| Reversed order | 7,393 | 852.8 s | 0 |
| Singletons | 7,393 | 1,012.5 s | 0 |
| Repeated singletons | 7,393 | 1,013.5 s | 0 |
| Batch on a fresh Pod | 7,393 | 877.7 s | 0 |

All **44,358 full-cohort predictions** passed the unchanged 0.0001 probability
tolerance. Maximum difference from independent references was **4.44e-16**.
Probabilities and actual returned decisions were identical across all serving
runs. Both Pods ran the pinned image without restarts. Three 64-pair canary
arrangements also passed on each Pod.

Reference generation took 893.8 seconds and peaked at 8.30 GiB allocated GPU
memory. These are individual local measurements, not latency percentiles or
capacity estimates. Batch requests reduce HTTP overhead while model execution
remains one pair at a time.

## Identities and retained evidence

| Item | Identity |
| --- | --- |
| Registered model | `synthetic-esci-judge/4` |
| Protocol | `singleton-fla-frozen-v1` |
| GPU | NVIDIA GeForce RTX 4090 Laptop GPU |
| Runtime | CUDA 12.4, Torch 2.6.0, Triton 3.2.0, fla-core 0.5.2 |
| Release SHA-256 | `44235684d820fc12feee84c36e9f8b0e0bb85bccf77d0c34f489672ab9bd0719` |
| Image digest | `sha256:272d8bb0e77a9684b5a24dc795eadcdff1c7506ee6418289f4d8634b46d65c28` |

The [aggregate receipt](esci-frozen-kernels.json) records input, reference,
profile, implementation and capture hashes, actual Pod identities and paired
checks. Raw inputs, vectors, captures and logs remain in ignored
`.lab/esci-packaging/frozen-kernels-20261003`. Previous failures are preserved.
The original sklearn 1.7.2 mapping was checked on every reference vector;
its maximum difference from the packaged calculation was 3.33e-16.

**Software checks:** 21 tests passed with five upstream warnings, including
profile rejection and a report that rejects changed returned abstentions even
when probabilities agree. Ruff and the complete batch diff check passed.
The installation guide's 25 PowerShell blocks parsed successfully.

SigNoz received the candidate's `model.http` and `model.predict` spans with the
original trace parent, model version and HTTP status. This checks direct model
tracing; it is not a new end-to-end Judgement API or drift assessment.

## Limits and next action

- The initial kernel profile is specific to this NVIDIA hardware and runtime.
  Other configurations need a new immutable profile and qualification.
- Numerical agreement does not qualify label accuracy or close the coverage gap.
  The 0.90 acceptance threshold and 80% coverage gate are unchanged.
- The candidate Pods, temporary ServingRuntime and reference container were
  removed after qualification, and the GPU was explicitly returned to its
  research owner.

Follow the [label-quality plan](../../plans/esci-label-quality.md) to reserve
independent confirmation queries and obtain authoritative labels for lab gaps.
Use the [installation guide](../../esci-model-installation.md) to reproduce the
serving checks. Existing architecture diagrams remain accurate; topology is unchanged.
