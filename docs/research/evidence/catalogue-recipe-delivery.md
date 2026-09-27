# Catalogue recipes and delivery: local evidence

**27 September 2026 · Windows 11 / local k3d.** These are individual lab observations, not timing distributions or capacity claims. All catalogue, query, judgement and traffic data are synthetic. Immutable references below identify retained inputs and reports; no earlier object was rewritten.

## Index creation and recovery

| Check | Frozen identity | Observation |
| --- | --- | --- |
| Shared 10k catalogue | Catalogue manifest `e65c481acbb0f9917526841fd7ee51573104fb76e190805150c000d44f646c6a`; format-2 recipe `379d0387750155b84c4d6291690aee8b5885aa4c4dfcc003a54fefad00c2e569` | Rebuilt 10,000 documents in 9.359 s into `retail-gb-10k-v1-r379d0387750155b84c4d6291`. A delivery preview served public searches from that index. |
| Dedicated mapping variant | Format-2 recipe `a3bdc04bab6372991e31ed9424a74aadbfb719ac0680abd9a1aabbd26ad76619` | Rebuilt 10,000 documents in 9.438 s from the same catalogue. The first ten ordered IDs were `gb-000000` through `gb-000009`. The temporary check index was removed. |
| Shared 1M catalogue | Format-2 recipe `93a6f2b9800804c4a044aff7aa5c87a2baa046c37d0f9c92782caebfae1eb39a` | Rebuilt 1,000,000 documents in 115.672 s into `retail-gb-1m-v1-r93a6f2b9800804c4a044aff7`. The first ten ordered IDs were `gb-0000000` through `gb-0000009`. A second ensure reused the same index without indexing. |
| Explicit historical replay | Format-1 recipe `511b1d4aa37af0313af09eb4d3a15ab6edb93a9feb87a18b17429cae7758b6e2` | After changing the current mapping source, historical rebuild used the pinned old indexer and mapping, retained the same first ten IDs and took 10.078 s. The test indices were removed. |

The new shared name derives from the recipe hash, allowing multiple schemas over one retained catalogue. Format-1 release-named shared indices remain available for explicit historical recovery. The control Pod has not yet been rolled to this branch's code.

## Delivery comparison

The candidate preview used release run 17, fingerprint `7fbd82d4632257e4da6904886498fe64ace5ccf1fd1fcfad78a587f86a1141da`, and the shared format-2 index above. The baseline was approved run 15, fingerprint `68c5783af2d35767162d881895359bb5ee747a795718ade1abdefc9856a51b55`. Both previews served public API searches. Candidate input selection pinned query manifest `144c51398442422cb638b6ef0f9df8c890e54afa6f3cad9383fbd1f93ad495fa` and judgement manifest `f30d8e10880e774d2987555450d71b3f0186c2736b534238d0a2c90d2373c69d` with the catalogue manifest above.

| Check | Retained report | Result |
| --- | --- | --- |
| Result preservation | `c1921e81ba79a0d964e1fa83716c9b09c0bd1e1e180333a63a8c4bea006a582a` | Full 50/50 queries; `unchanged`. |
| Synthetic relevance | `4eec2fd031844994d83dd969978a4833665c562d146b66caf3830023682bff2b` | Full 50/50 queries; `measured`. This is evaluation evidence, not a quality approval. |
| Gatling probe, first complete pair | `184ff945b295a8d298890b7487f731118edfabc8fbbfccdbf5170c22dd696adf` | Both APIs returned 30/30 requests without failures and met the normal-phase latency budget. One candidate arrival was 734 ms late, so the workload timing contract marked the pair `invalid` and the delivery gate rejected it. |
| Gatling probe, controlled rerun | `40c35a91c762e04113059d0f3ca41feef307401442b6e8435d1cde157ad8df69` | Both APIs completed 30/30 requests against the same pinned workload with no errors. The normal phase was within budget: p95 14 ms on each side at 2 offered requests/s. The delivery gate validated the pair. |

The first Gatling attempt exposed an ownership collision: control orphan cleanup selected the delivery Job. Delivery Jobs now use their own ownership label. A second attempt exposed a report-copy path assumption when local state sits outside the isolated worktree; the copy path now supports that layout. Both fixes are in this batch, with focused tests. The invalid complete pair remains retained for inspection. The valid delivery evidence is `633df343846dc36085cf71876ae18f184cd57eb600ee30c6f4c4aa4ccc92b89e` in `runs/633df343846dc36085cf71876ae18f184cd57eb600ee30c6f4c4aa4ccc92b89e/delivery-evidence.json`.

The [schema-contract source PR](http://127.0.0.1:31800/elastic-agent/delivery-source/pulls/4) changes the index compatibility contract and passed its PR-head Gitea Actions run 18. It remains open for review. A stable-target schema promotion and rollback require its reviewed merged-source build, so this batch does not claim those gates passed. The [next batch](../../plans/reference-runtime-consolidation.md) covers that rehearsal and control rollout.

## Verification

- `python -m unittest discover -s lab -p 'test_*.py'`: 85 tests passed.
- Changed Structurizr SVGs and Archify views were regenerated, browser-validated and visually inspected; receipts are in `docs/diagrams/receipts/`.
- `git diff --check` passed.
