# Lab appearance, promotion controls and Mac preparation

## Scope

Checked on Windows x64 on 6 October 2026, in the isolated
`esci-category-increment-analysis` checkout. The prepared branches follow the
accepted release-dashboard source. New design/promotion code has not been
installed or used to promote a live release.

## Results

| Check | Observed result | Limit |
| --- | --- | --- |
| Shared page design | 33 focused Python checks, existing control-list/form Chromium checks and retained-data tree fixture passed; desktop and narrow screenshots inspected | Browser fixtures are not full live OIDC acceptance |
| Promotion panel | 56 focused Python checks passed; Chromium exercised keyboard selection, approved-PR selection, reader restrictions, transport retries and narrow layout | No live load, inference or deployment action was submitted |
| Combined contracts and portability | 59 focused checks passed, including the previous delivery/API/projection checks and three transfer checks | Windows execution; no native Mac runtime |
| Control archive | Both databases retained committed rows still present in WAL; import recovered them and refused an existing destination | Disposable files, not a whole-cluster backup/restore |
| Host tool selection | macOS-style PATH fallback exercised with no bundled executable | Mocked host choice; Homebrew was not installed on Windows |
| Document pages | Local gallery and lifecycle diagram loaded shared tokens and rendered without JavaScript errors; screenshots inspected | Specialised SVG geometry and semantic colours retained |
| Guide references | 37 current guide files had no missing local file targets; relevant CLI help matched the examples | External authentication and native Mac commands not executed |

The installed model identity ConfigMap names `synthetic-esci-judge`, version 1.
Both judgement APIs use the current multi-platform relevance-judge image. The
guides now distinguish this CPU abstaining fallback from saved version-4 demo
labels and the GPU candidate.

## Image and storage inventory

Read-only inventory at 22:26 UTC found five nodes, 15 PVCs requesting 70 GiB and
three external persistent service volumes. CPU node Docker limits total 30 GiB;
Nexus and its database add 4.5 GiB. These values are configuration, not measured
disk use or a Mac capacity result.

Of 109 workload image references, 97 exact inspected indexes advertised
`linux/arm64`. Twelve were unknown in that pass, including seven older Gitea
search-spike references, optional inference fixtures and older judge images.
The intentionally missing test image remains unresolved. A later verbose
inspection identified one older `relevance-judge` image as `linux/amd64`; it is
not the current multi-platform judge API image.

Core control, current search APIs, the abstaining judge API, identity, Gitea,
Headlamp, Elasticsearch and SigNoz advertise arm64. Separate exact manifest
checks confirmed the retained K3s, Nexus and snapshot-store references. No
images or models were started to establish this metadata.

The ignored inventory and screenshots are retained under the existing host
`.lab`; they are not secret-bearing backups or portable restore bundles.

## Outstanding acceptance

Native Mac tool installation, Keychain trust, resolver routing, ARM startup,
database integrity after restoration, node/PVC placement, GPU exclusion and a
full lab restart still need target-host checks. Neither Docker manifest metadata
nor an emulated image build establishes those outcomes. No current service was
stopped to produce a cold backup in this batch.

Follow [Mac setup](../../mac-setup.md), [transfer](../../lab-transfer.md) and the
[activation/native-transfer plan](../../plans/lab-experience-and-mac.md#next-detailed-plan-activation-and-native-transfer).
