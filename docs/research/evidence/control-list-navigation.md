# Control navigation checks

Checked on 3 October 2026 against the control list navigation branch.

| Check | Observed result |
| --- | --- |
| List selection tests | Five Node tests passed: combined filters, page boundaries, empty results, stable order and unmodified source records |
| API and identity tests | Fourteen tests passed, including UTF-8 UI/script responses and reader restrictions |
| Browser fixtures | 55 environments, 100 comparisons and 1,000 report queries |
| Paging | Correct ranges and counts; filters reset pages; empty results remain usable |
| Comparison selection | List filtering and refresh retained ready baseline/candidate choices |
| Unicode | Catalogue separators, `café` query text and `ΔnDCG` labels rendered correctly |
| Reader | Search/filter controls usable; mutating actions unavailable |
| Layout | Desktop and 390-pixel viewport inspected; no horizontal overflow or page errors |
| Live OIDC | Administrator and reader callbacks, UTF-8/navigation response checks and worker service checks passed |

The control image is
`nexus.localhost:18185/lab-control@sha256:b26a095f604c22a7f117956943bd159cfeea961778143c7745479ad87d83c307`.
Its manifest includes amd64 and arm64; native Apple Silicon execution was not
checked. The existing control Deployment and volume definitions were retained.

The supplied screenshot shows encoding corruption. Before this batch, the
running file already contained correct UTF-8 separators; the screenshot alone
cannot identify which response the browser retained. Fresh source, served
responses and browser rendering now pass explicit Unicode checks. No imported
catalogue, frozen report or runtime encoding adapter was changed.

Browser tests use Playwright 1.62.1 with intercepted synthetic responses. These
checks verify navigation and presentation, not relevance quality or production
capacity. Desktop computer-use automation was unavailable; headless browser
fixtures and verified HTTPS callback clients supplied the checks.

## Repeat the checks

From the repository root with Node and the lab Python dependencies available:

```powershell
node --test lab/test_control_lists.cjs
$env:PYTHONPATH = 'lab'
python -m unittest lab.test_control_api lab.test_control_oidc
```

For the optional browser fixture, install Playwright in ignored local state:

```powershell
npm install --prefix .lab/ui-qa --no-save playwright@1.62.1
node .lab/ui-qa/node_modules/playwright/cli.js install chromium
$env:NODE_PATH = (Resolve-Path .lab/ui-qa/node_modules).Path
node lab/test_control_ui.cjs
```

On Linux/macOS, set `PYTHONPATH=lab` and `NODE_PATH` with `export`, and use
`python3`. Browser captures and its JSON receipt go to `ui-qa` under
`LAB_STATE_DIR`, or repository `.lab` when unset. Live verification requires the
installed identity service and control runtime:

```powershell
python lab/verify_control_oidc.py
```

The live verifier creates and removes disposable users. It runs no evaluation
and issues no gate decision. Screenshot framing is recorded in the
[capture notes](../../screenshots/README.md).
