# ESCI version 2 serving attempt — 2 October 2026

**Result: numerical qualification failed.** The optional GPU worker can start
the registered candidate, but this runtime does not reproduce the independent
reference probabilities within the fixed tolerance. The active model remains
`synthetic-esci-judge/1`; no acceptance policy or coverage gate changed.

## Observations

| Check | Observed result |
| --- | --- |
| Placement and identity | Candidate on `relevance-gpu-worker`; actual image digest matches the pinned CUDA image; response identity matches registry version 2 |
| Initial model download | Default 100 MiB multipart chunks exceeded the 1 GiB initializer limit |
| Smaller chunks | 16 MiB chunks completed once at 1 GiB, then exceeded that limit on a fresh download |
| Final download settings | Direct multipart transfer, 16 MiB chunks, 2 GiB limit; download and hash verification completed in 290 seconds, with no restart |
| Prediction URL | Two harness attempts returned 404; the guide commands used service/registry names instead of the implemented `judgement-model` route; both commands are corrected |
| Canary population | 64 existing frozen-research pairs: 26 labelled Exact, 38 abstentions |
| Cold repeat | Not run: the first numerical check failed |
| Cleanup | Candidate service and Pods removed; active version 1 pin verified; GPU returned to research |
| Research resume | Owner confirmed reuse of the retained checkpoint, new committed states and an active heartbeat |

The final request arrangements all returned the expected labels and abstentions,
but their probability deltas failed the unchanged **0.0001** tolerance:

| Arrangement | Maximum absolute probability delta | Changed labels/abstentions | Result |
| --- | ---: | ---: | --- |
| Batch | 0.011779960424738722 | 0 | Failed |
| Singletons | 0.0220298621145244 | 0 | Failed |
| Reversed | 0.011779960424738722 | 0 | Failed |

[Machine-readable result](esci-serving-canaries.json) retains the model,
reference and image identities. This result is numerical evidence, not evidence
of accuracy or coverage on current judgement gaps. Raw research examples remain
in ignored local storage. The first attempt retains aggregate comparisons;
per-row returned probabilities were not saved, which the diagnostic batch must
address.

## Identities and retained records

- Registered artefact: `ee4048a8ee758af4b4f697c63e921d4113b8bc95fa4e81728e881360405598f1`.
- Release: `93ee12f782684f5213a5b5ff0205d0d2765554f42646d5294a65029704742c45`.
- CUDA image: `b3067043e3cea2a6afbec3810c5eec9b5a18315558909f972141a2c9d281fd1d`.
- Reference: `aa0773428d0972c5b8b42b8030615e30bc7b99ba64090fc2dc6c9aebe91e0570`.
- Result file: `81251bba25d999380a8201f708b89f25b3ad55831d2d096cc05eb9b7007e2b98`.
- Ignored records: `esci-packaging/serving-window-20261002`,
  `serving-window-20261002-retry` and `serving-window-20261002-contract` beneath
  the configured lab state directory. They retain harness failures, the fresh
  download restart, final Pod identity and qualification result.

## Verification and next work

The existing eight release checks and two telemetry checks passed. Ruff and
`git diff --check` passed. Inference exposed null abstention labels being sent
as metric attributes; the source fix uses the existing `none` bucket. An offline
check in the actual serving image successfully serialised abstention and Exact
metrics through its OTLP protobuf encoder (820 bytes). The fix has not yet been
built into a new deployed image; end-to-end export remains for that revision.

Research and serving have matching declared core package versions, BF16,
disabled CUDA graphs and unmerged adapter loading. Runtime logs nevertheless
show reference-kernel fallbacks. These observations do not identify a root
cause. [Parity diagnosis](../../plans/esci-runtime-parity.md) separates input,
raw inference and score mapping before requesting another GPU window.
