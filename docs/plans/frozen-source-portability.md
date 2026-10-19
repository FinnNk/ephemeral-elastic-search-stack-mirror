# Preserve frozen source bytes across checkouts

## Cause and scope

The ESCI importer records its own raw SHA-256 in each base release manifest.
Dated/seasonal producers bind those complete source manifests into their own
provenance. Original frozen releases were produced from a Windows CRLF checkout,
while Git held an LF version. A Mac LF checkout therefore changed derived
manifest hashes even when product, query and judgement content was unchanged.

The original importer hash is
`dc6f175d8cf737a8ab8f7df84a374a88824e4fb7fe524303b6092d09a3db758e`;
the previous LF checkout hash is
`40cfc8e4e08aeeb63b18ffdbd494f1a4fd31a19408a86edc82886c38c79faa4f`.
The fix stores the exact original CRLF bytes in Git and disables text conversion
for that file. Its code and frozen raw hash remain unchanged.

## Similar dependencies checked

| File or boundary | Treatment |
| --- | --- |
| Synthetic million-product generator and its profile | Preserve the existing exact bytes; retained manifests bind both raw hashes. |
| CPU abstaining judge source | Preserve the existing source bytes used by registration receipts and the host verification. |
| Search routing helper and Gatling simulation | Preserve raw bytes recorded in evaluation and load evidence. |
| Vendored Envoy values | Disable conversion; their current bytes already match upstream checksums. |
| Downloaded charts, models and source archives | Keep exact-byte verification; these are downloaded binary artefacts, not Git text conversions. |
| Existing frozen query/label packs, policy, kernel profile and diagram receipts | Existing Git attributes already preserve their intended bytes. |
| Research source receipts | Preserve historical receipts; a changed research checkout needs its own newly recorded run. No historical evidence is rehashed or relabelled. |

No committed catalogue/query/judgement pins, Redis bindings, accepted labels,
source release versions or performance budgets change.

## Interrupted fresh-install recovery

The fresh catalogue stage verifies the frozen importer bytes before import.
For the known earlier LF producer, recovery is allowed only when every retained
base data file verifies and replacing that one importer provenance field yields
the exact original full manifest hash. Other changes fail closed.

Original metadata and affected derived directories are retained under
`.lab/portability-recovery`. Derived files are regenerated using the normal
producer; they are not edited or re-pinned to make a check pass. Publication
continues to refuse changes to existing Blob objects. Repeating recovery after
success is a no-op. This is limited to the installer-owned fresh catalogue stage,
not a migration of an established lab or an import of arbitrary old outputs.

## Verification, 19 October 2026

- Real Git checkout fixtures with `core.autocrlf=false`, `true` and `input`
  preserve the same frozen producer bytes, regardless of `core.eol=lf`.
- Recovery fixtures check unchanged base data, retained old outputs, repeat
  execution and interrupted directory moves. Modified data, importer code,
  additional metadata and mixed artifact provenance are rejected.
- A disposable replay using retained source data reproduced changed pins for
  all five dated/seasonal catalogues after substituting the known LF importer
  identity. Recovery and normal regeneration restored all 15 committed input
  pins and all five original release-manifest hashes exactly. A second recovery
  made no changes. Live services and source catalogue files were not modified.
- The final focused run passed 63 tests covering recovery, importer behaviour,
  timeline/Redis bindings, fresh application setup and installer behaviour.

These are Windows checks with simulated checkout differences, not native Mac
execution or proof that a separate compression-library difference is resolved.

## Next detailed plan

1. Accept and merge the fix, then verify the GitHub mirror contains it.
2. On the Mac, pull with `git pull --ff-only` and resume the same installer
   command/options. Retain output if it rejects a difference beyond line endings.
3. Complete installation and workstation access, then open a source PR and
   promote its merged build through the ordinary reviewed UI flow.

See [fresh-install recovery](../fresh-install.md#resume-after-a-checkout-line-ending-mismatch).
