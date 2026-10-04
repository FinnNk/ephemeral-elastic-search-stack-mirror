# ESCI source gate integration

Verified on the Windows lab on 4 October 2026. The accepted demo policy now runs
in source CI, and the catalogue change is on source main.

## Result

| Check | Observed result |
| --- | --- |
| Source policy | PR #23 merged; accepted verifier and policy hashes verified |
| Trusted CI pins | Both variables updated and read back successfully |
| Catalogue patch | PR #19 rebased; its three-file patch remained unchanged |
| Release builds | Accepted-main build 94/1 and candidate build 95/1 passed |
| API comparison | 1,000 fresh queries against separate frozen previews |
| Coverage | 8,053/9,915 = **81.22%** on each variant |
| Results | No changed query results; result-preservation gate passed |
| Scoped CI | Relevance run 96/2 passed on the accepted policy base |
| Source acceptance | PR #19 merged; source main equals the evaluated candidate |
| Historical report | Original 29.71% coverage report remains unchanged |

The first relevance attempt failed because the new commit had no published
report. After capture and signing, the same current-base event passed. The old
pre-policy event was not rerun.

## Frozen identities

| Item | Identity |
| --- | --- |
| Accepted policy base | `b44d5748b6cdad314da1ec0c00c71fafb35e820c` |
| Evaluated candidate / source main | `12404ff259984040e7a74d0015410b9a872e2363` |
| Verifier SHA-256 | `c905493730fab35a3d0140b3cfbd984495d2681327b8638b292ffdf6877d98bc` |
| Policy SHA-256 | `96b5156d93e9d0a68e0f0f3b3f915d5b5567c5c502c08a6610810c9f6d907bfd` |
| Observation SHA-256 | `75aa12deaa2badb9a832ae454f9e273310b0add50a856fb27015d83d19fd095a` |
| Report SHA-256 | `9936f54265da8ab365f329f41cd5b3b5ea8210959584db2cc4124ca5d5cee509` |

CI logs confirm the exact base, candidate, policy and recorded demo authorisation.
Nexus report and signature bytes match the local frozen evidence. The
[validation receipt](esci-demo-source-integration.json) retains image identities,
environment fingerprints, build receipts and the original report hash.

## Limits and next step

Coverage includes **5,107 unqualified model predictions**. Published labels and
model predictions remain distinguishable. This authorisation demonstrates the
lab pipeline; it does not qualify model accuracy or establish an Irrelevant-to-Exact
error rate. No new inference, GPU work or independent actual-gap labels were added.

Apple silicon and Azure deployment were not checked. GitHub backup batches remain
separate; Gitea acceptance does not merge them.

Continue the [developer walkthrough](../../plans/developer-walkthrough.md) when
requested. The later [qualified-defaults plan](../../plans/esci-qualified-defaults.md)
requires resumed investigation and independent confirmation; the role-check
execution hold remains in effect.
