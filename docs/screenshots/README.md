# Documentation screenshots

Use these images to recognise controls and saved output. The text guides contain the instructions; screenshots do not prove a comparison passed.

## Captures — 1 October 2026

| Asset | Source and framing |
| --- | --- |
| `comparison-controls.png` | Actual installed control UI at `http://localhost:18082/`, signed in as the agent. Headless Edge 154.0.4258.48, 1440×1000 viewport, device scale 1; capture of the `#compare` form. Selected `comparison-explorer.ipynb` locally without submitting. Baseline/candidate selectors were empty because no ready environments were available. No result, approval or environment was created. |
| `exploratory-notebook-output.png` | HTML export of retained executed notebook `e5fa0ae6f022b20c284fd6e20684a391a53d570e66d4e0d36cc04aed7257cfb8`. nbconvert 7.16.6, `lab` template, input cells hidden. Edge viewport 1100×370, device scale 1, top of page. No cells were rerun or outputs changed. |

Control image at capture: `nexus.localhost:18185/lab-control@sha256:baa5ead3bbae39647ee3a9decd950bb4f14422b7293748e6cc6531b9549782aa`.

The notebook was downloaded read-only from `runs/notebooks/<hash>/executed.ipynb` and its SHA-256 verified before export. Its source run and limits are in [notebook evidence](../research/evidence/exploratory-notebook.md). Three synthetic variants had very low judged coverage. The screenshot illustrates saved exploratory analysis, not a gate pass.

## Recapture and maintenance

1. Connect to the running control UI using the [port-forward procedure](../control-runtime.md#connect-and-check). Sign in with a shareable lab identity; keep credentials and account panels outside the capture.
2. At the same viewport, capture the comparison form after notebook options load. Select the packaged example without running a comparison. Preserve the actual labels and available state.
3. Download the retained notebook using its recorded Blob reference, verify its content hash and export with Jupyter nbconvert's `lab` template and `exclude_input=True`. Open the export at the stated viewport and capture the top of the page.
4. Inspect both images in the rendered lab guide at normal document width. Check legibility, controls, captions and source identity before committing.

No redaction or image editing was applied. The capture excludes login fields, credentials, browser chrome and comparison history. IDs, environment availability and notebook outputs may differ in another installation. Recapture or remove an image when its labels or workflow no longer match; preserve historical execution evidence separately.
