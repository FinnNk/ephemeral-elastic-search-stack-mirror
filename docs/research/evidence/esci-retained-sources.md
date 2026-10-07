# Retained ESCI source verification

Verification on Windows, 7 October 2026. No deployment, catalogue rebuild or
inference was performed against the original lab.

## Published source assets

[FinnNk/esci-s, lab-sources-v1](https://github.com/FinnNk/esci-s/releases/tag/lab-sources-v1)
contains six data assets and one manifest. The packaging source is tagged at
fork commit `28713e4`; [fork PR 1](https://github.com/FinnNk/esci-s/pull/1) reviews
the packaging script, provenance, manifest and documentation.

All three local original files matched the existing source-lock sizes and
SHA-256 hashes before packaging. The packager streamed every packaged file
back to its original bytes and verified those sizes and hashes again.

| Source | Original bytes | Download bytes |
| --- | ---: | ---: |
| Products | 1,108,857,465 | 919,638,615 |
| Queries and labels | 51,286,808 | 20,931,574 |
| ESCI-S metadata | 3,620,467,456 | 3,620,467,456 |

The six data assets total 4,561,037,645 bytes, excluding the small manifest.
Products and examples use Zstandard level 10. Metadata retains its existing
compression and is divided into three 1 GiB chunks and one 399,241,984-byte chunk.
The importer and original source lock remain unchanged.

All seven uploaded asset sizes and GitHub's server-side SHA-256 digests matched
the local files. The release was published only after that verification.
An unauthenticated public manifest fetch matched the accepted manifest content.
An unauthenticated query/label asset fetch passed its transport hash and
reconstructed the original Parquet file with its original size and hash.

## Installer checks

37 isolated tests passed across `test_esci_sources`, `test_fresh_install` and
`test_fresh_application`. Retained-source tests exercise both chunk concatenation
and decompression, reuse with no further downloads, reuse of a completed chunk
after a later download fails, rejection of corrupt downloads, and rejection of
source-identity changes before any network call.

The fresh-install fixtures mock cluster operations. They do not establish a
completed Mac installation. The larger assets were verified through local
reconstruction and server-side digests, rather than downloaded a second time.
Corporate Mac access to GitHub release assets remains unverified.
