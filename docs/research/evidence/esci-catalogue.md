# ESCI catalogue verification

Observed on 2 October 2026 in the Windows Docker Desktop/k3d lab. [Retained results](esci-catalogue.json) include input hashes, source commits, image digests, index recipe, observations and Gatling report references.

## Results

| Check | Observation | Limit |
| --- | --- | --- |
| Full import | 1,215,854 products; 1,000 test queries; 18,981 published labels | Source checksums verified; fixture tests prove deterministic output. A second full import verified and reused the existing bytes rather than regenerating them |
| Metadata and prices | 1,018,263 metadata matches; 297,716 source prices; 918,138 generated prices | Source numeric prices are relabelled GBP; generated prices and stock/popularity assumptions are identified |
| Independent publication | Full and demo manifest hashes reproduced; repeat publication succeeded | Existing objects are checked before upload. Floci required an 8 GiB limit for the large catalogue objects |
| Initial index | 1,215,854 documents indexed in 272.609 seconds | One local index build, excluding source download/import; no percentile claim |
| Shared index | One canonical recipe index serves both source builds | The temporary import index was removed; retained historical synthetic indexes were not relabelled or replaced |
| Normal environment creation | Control workflow reached `ready` in 12.582 seconds; shared index reused | One warm observation using search-spike build 25; disposal verified separately |
| API comparison | 1,000 queries captured; no ordered top-10 changes between delivery-source builds 77 and 82 | Equal configuration and catalogue; this source change updates documentation, UI copy and index declarations |
| Capture and scoring | 52.032 seconds in the retained run | Fresh searches; one local run, not a latency percentile or performance capacity result |
| Judgement APIs | Both profiles returned stored labels, left gaps unjudged after model abstention and rejected altered product records | Bootstrap abstaining model; does not establish model quality |
| Snapshot restore | 45.39 seconds; full document count, frozen settings/mapping and ordered sample verified | Existing local SeaweedFS repository; excludes API deployment and warm-up |
| Gatling probes | Both sides: 30/30 arrivals, no request failures; native reports retained | Fifteen-second wiring probes, not normal/peak/stress capacity acceptance |

## Gate limitation

Both variants returned 9,915 top-10 results, of which 2,946 had published labels: **29.7126% coverage**. Scores match between builds, but delivery-source PR #19 remains blocked by the existing **80% minimum** in its trusted relevance gate. The supplied report is for the exact PR head and successful build receipt. The policy was not weakened and missing pairs were not labelled irrelevant.

The next batch must distinguish the evidence needed for result preservation from relevance decisions, and assess pooled judgement resolution. [Coverage plan](../../plans/esci-coverage-gates.md) records the scope and approval boundary.

## Verification scope

Lab, importer, evaluator and judgement tests cover changed contracts. C4 views were regenerated and the changed context view inspected. Images were published for amd64 and arm64; runtime checks used amd64 only. Azure, Apple silicon, sustained load, stress and SLO capacity checks were not run for this catalogue. The existing ESCI model qualification suite could not run in the host Python environment because MLflow is not installed there; judgement-service and pooled-resolution tests ran separately.
