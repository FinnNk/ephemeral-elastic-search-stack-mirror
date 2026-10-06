# View a saved comparison notebook in the browser

Completed comparisons should offer **View notebook** alongside the existing
download, including notebooks retained before this change.

## Implemented batch

- Add the link to completed comparison cards and the inline run feedback.
- Read the retained `.ipynb` through the same ownership checks and hash
  verification as the download. No notebook execution or inference is started.
- Show saved Markdown, text outputs and PNG/JPEG figures. Collapse code cells
  initially, with links back to the comparison and to the original download.
- Escape code, raw HTML and text. Use a restrictive page content policy that
  blocks scripts and remote assets. Explain unsupported rich outputs and retain
  the download for interactive widgets or HTML-only content.

Markdown uses pinned [Mistune 3.2.1](https://mistune.lepture.com/en/latest/api.html)
with HTML escaping enabled and its table plugin. This adds one small renderer
dependency to the coordinator; the notebook runner and retained files are
unchanged.

## Verification — 6 October 2026

All 16 focused renderer and control API tests passed. They cover saved cells
and outputs, figures, escaping, ownership, retained hashes and the viewer's
content policy. Chromium checks passed for both notebook links and existing
comparison controls, including timeout feedback and repeat-submit protection.

The user's completed comparison `346f8b4a-b541-4fc9-b50d-40cd1367c8b0` supplied the
actual notebook for visual verification. Its SHA-256 remains
`87456bd4dea5b03a4ace6e8c32a19fa2fab3b36001776a3fed3224e6081a1cd4`.
The local browser preview showed its 50-query saved output and collapsed code,
with no horizontal overflow at a 390-pixel viewport. No cells were run.
This preview used a local file, not the installed authenticated route. The API
route was tested with its loopback test server. The new viewer awaits acceptance
and coordinator activation at the time of that verification.

## Activation — 6 October 2026

PR #146 is merged and the coordinator image is installed. All four containers
are Ready, and the Gitea, Elasticsearch and Nexus service smoke checks passed.
The existing notebook browser route returned its saved output through the
installed authenticated handler. No notebook cells or comparisons were rerun.
The image digest is
`aad7bbcc416bcbf4ef1e7ae01dd6c271289bf1061cf8d664f7450ca4017348fa`.

## Next batch

The viewer activation is complete. Resume the walkthrough with the
purpose-created previews after the current release-dashboard review batch.
