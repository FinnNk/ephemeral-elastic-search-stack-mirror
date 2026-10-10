# Locked Python setup and seasonal query demonstrations

## Outcome

Use uv for host Python versions, environments and dependencies on Windows and
macOS. Preserve corporate/public CA verification through Python downloads,
packages and image builds. Provide reusable Halloween/Christmas query sets for
PR reports and exploratory notebook comparisons. This batch follows the paired
data and fixed-lease batch; existing catalogue pins remain unchanged.

## Implemented behaviour

- Python 3.12.12 host pin, a non-package pyproject and universal uv lock. The
  default environment includes existing CPU lab dependencies and Redis 6.4.0.
  Notebook tooling is a separate dependency group; model research packs remain
  isolated because their frozen NumPy/GPU requirements differ.
- Existing service Python image versions retained. All maintained Python image
  builds use the verified uv 0.11.21 multi-platform digest. Search API builds
  consume a hash-checked export of their own lock and keep BuildKit CA injection.
- Locked certifi public roots supplement uv-managed Python's OpenSSL trust before
  the installer adds corporate roots. Host instructions describe system trust
  and combined PEM bundles; Docker/k3d registry trust stays explicit.
- Fresh source seeding includes uv metadata and excludes `.venv` from Git and
  Docker contexts. Existing repositories receive companion review branches.
- Three additional sets: Halloween (8), Christmas (8), shared controls (10).
  Copy/paste selections are report-only and preserve the standard required suite.
- An immutable publisher produces an 80-query combined suite for each seasonal
  catalogue, retaining all original products and 968 labels. Defaults are not
  changed. Fresh setup publishes these extra manifests; an existing operator
  can publish them after accepting the batch. The control UI's existing manifest
  fields and notebook selector require no new deployment operation.

## Verification

Observed on Windows: uv downloaded and selected the pinned interpreters and
synchronised the two isolated environments. The installer, input-selection,
pairing and gate regression run passed 87 tests. The certificate tests verify
an unknown CA is rejected, a combined corporate/public bundle is accepted by uv
against a disposable local HTTPS index, and managed Python with no default roots
loads the locked public CA bundle. The real Redis test seeded all seven datasets
in a disposable non-root container, checked read-only lookup and fallback, and
removed the container.

The uv Search API image built and passed its 18 embedded tests. The companion
source API passed 20 tests in its actual uv environment; the standalone API
passed five tests. The control runtime image built with uv on linux/amd64.
Ten query/source-comparison/judgement-resolution regressions passed, and the real
query-freezing helper accepted all three report-only files. Actual local
preparation produced 80 queries per event, preserved source products/labels and
reused identical manifests on repeat.

The Apple silicon lock installation dry run passed. Native Mac clean installation
and access through the organisation's real proxy are not verified here. Large
GPU/model images were changed to use the same pinned uv installation but were
not rebuilt, and no model research or inference job was started. The running
lab was not redeployed and the new extra inputs have not been published to it.

## Review and activation

Accept the paired-data prerequisites first: lab #171, environment-state #1 and
the API changes in delivery-source #35 and search-spike #7. Then accept this
lab batch and its companion API batches. On either host, pull the accepted code,
configure corporate trust, and run `uv sync --locked` from each repository root.

For the existing lab, publish the extra inputs with
`uv run --locked python lab/prepare_seasonal_queries.py --publish` after preparing
the seasonal datasets. Read [seasonal query demos](../seasonal-query-demos.md)
for selecting the hashes and notebooks. Control-runtime activation follows its
normal guide. No release gate or model confidence threshold changes in this batch.

## Next detailed check

On the Mac, repeat from an empty installer-owned lab with the corporate CA.
Confirm the managed Python version, package downloads, Redis readiness, native
image builds, fresh seed uv files and published seasonal-query references.
Then compare two environments on each event catalogue using the 80-query suite
and view the resulting notebook. Separately select the source-controlled sets
in a demo PR and inspect separate/combined metrics and coverage. Record actual
abstentions or unavailable nDCG rather than expecting invented grades.

## Published review batch

- [Lab #172](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/pulls/172): uv host/container setup, corporate trust and seasonal-query publication.
- [Delivery-source #36](https://gitea.localhost:34443/elastic-agent/delivery-source/pulls/36): locked API environment and reusable query sets.
- [Search-spike #8](https://gitea.localhost:34443/elastic-agent/search-spike/pulls/8): standalone uv/Redis lock and CI CA secret.

Merge the respective prerequisite first (#171, #35 and #7), then review these
successor PRs. The lab PR is mergeable at publication. Hosted API checks are
still separate from the local verification recorded above.
