# Judgement inference reuse

The calibrated model-4 run captured 1,000 ESCI queries through both variant APIs.
Both variants returned identical ordered results. Its union contained 9,915
pairs: 2,946 published judgements and 6,969 gaps. The reservation audit excluded
49 pairs; inference covered the remaining 6,920 without errors in 1,383 seconds.

Original model acceptance added 2,099 labels. The authorised demo policy applied
to those saved scores added 5,107, giving 81.22% overall demo coverage. Neither
policy has independent actual-gap accuracy evidence. Identical variants had
identical scores within each shared judgement set. Score increases between
judgement sets are diagnostic evidence, not search-quality improvements.

## Cache replay

The new API was exercised locally with those 6,920 saved predictions as its score
provider. No GPU inference ran during this check. Full inputs, model identity,
runtime image and protocol were pinned; protected pairs remained excluded.

| Stage | Cache hits | Score-provider pairs | Seconds |
| --- | ---: | ---: | ---: |
| Populate from saved predictions | 0 | 6,920 | 9.781 |
| Repeat | 6,920 | 0 | 5.469 |
| Restart API and repeat | 6,920 | 0 | 5.875 |
| Apply demo thresholds as exploratory decisions | 6,920 | 0 | 10.687 |

The repeat retained 2,099 labels and 4,821 abstentions. The threshold change
produced 5,107 labels and 1,813 abstentions without reinference. Decisions remain
unqualified. Timings cover local API resolution, excluding search capture,
catalogue loading and report scoring; they are not production latency targets.

[Verification JSON](verification.json) retains the input pass, model/runtime
identities and unchanged frozen-report hashes. Original inputs, predictions and
isolated SQLite stores remain under `.lab/esci-packaging/offline-model4-20261005`
and `.lab/inference-reuse-20261005` on the lab host.

Software verification passed 61 judgement/frozen-scoring tests and the browser
comparison test. Cases include policy changes, restart, retryable errors,
concurrent requests, authoritative labels and explicit fresh attempts retaining
the original default. The interactive/static workflow was regenerated and
visually inspected. These checks establish cache behaviour and shared scoring,
not classifier accuracy.

The published image contains AMD64 and ARM64 manifests. Its 18 focused API/cache
tests also passed inside the AMD64 container. ARM64 execution on Apple silicon
and deployment of the new API to the shared lab remain outstanding.
