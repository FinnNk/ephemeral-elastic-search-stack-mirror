# KServe 0.21 release charts

These unmodified charts come from the official **v0.21.0** release. Their names
and chart metadata still say `v0.21.0-rc1`; stable chart tags were not published.
`release.json` records each original URL and SHA-256 checksum. The upstream
Apache-2.0 licence is retained in `LICENSE`.

The installer explicitly sets `kserve.version=v0.21.0` and pins the stable
controller's multi-platform image digest. It does not use a prerelease controller.
The image manifest includes amd64 and arm64; Apple silicon operation is untested.

Upstream tracks the chart metadata in [issue #6314](https://github.com/kserve/kserve/issues/6314).
[PR #6343](https://github.com/kserve/kserve/pull/6343) fixes release-script checks
but does not republish these charts. Retain the original chart metadata for
provenance; update the pinned assets only after verifying a replacement release.
