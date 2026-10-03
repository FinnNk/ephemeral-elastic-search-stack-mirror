# Fit CPU judgement specialists

This experiment tests six inexpensive ESCI classifiers on a separately reserved
published training pool. It measures whether they add useful labels after the
existing experimental cascade. Predictions stay inactive throughout the survey.

| Stage | Data and purpose |
| --- | --- |
| Fitting | 700 whole query groups from the newly reserved pool |
| Calibration | 300 separate groups choose class confidence thresholds |
| Development | The already exposed 400-query cohort screens quality and extra coverage |
| Confirmation | A separately reserved assessment is required before qualification |

Features use query text, published product text, brand, category paths and
product type. Synthetic prices, stock and popularity are excluded. The models
combine lexical relationships or category roles with fixed MiniLM embeddings.

## Run

From this repository, use the existing packaging Python environment with NumPy,
SciPy, scikit-learn and joblib. Set `LAB_STATE_DIR` to the ignored lab state.
The fitting pool must already be materialised, with its reservation and input
hashes verified. MiniLM exports contain CPU-only, row-ordered query, title and
category vectors, plus their plans and receipts.

```powershell
$surveyPython = "$env:LAB_STATE_DIR/esci-packaging/.venv/Scripts/python.exe"
& $surveyPython lab/experiments/esci-fitted-specialists/test_fit_specialists.py

& $surveyPython lab/experiments/esci-fitted-specialists/fit_specialists.py freeze `
  --state "$env:LAB_STATE_DIR" `
  --pool "$env:LAB_STATE_DIR/esci-fitted-specialists/fitting-pool-01" `
  --output "$env:LAB_STATE_DIR/esci-fitted-specialists/six-candidate-survey"

$env:OMP_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$env:BLIS_NUM_THREADS = '2'

& $surveyPython lab/experiments/esci-fitted-specialists/fit_specialists.py run `
  --state "$env:LAB_STATE_DIR" `
  --output "$env:LAB_STATE_DIR/esci-fitted-specialists/six-candidate-survey" `
  --pool-embeddings "$env:LAB_STATE_DIR/esci-fitted-specialists/fitting-pool-minilm" `
  --development-embeddings "$env:LAB_STATE_DIR/esci-gap-surveys/input-embeddings"
```

Freeze into a new output directory. The tool checks its own bytes against the
plan before fitting; use the retained `executed-source` copy to replay a
historical run after source formatting changes. Plans, predictions and fitted
artefacts remain in ignored local state. The commands above were checked on
Windows. On Linux and macOS the virtual environment executable is
`$LAB_STATE_DIR/esci-packaging/.venv/bin/python`. Replace PowerShell
continuations with `\` and set the environment variables using `export`;
these shell equivalents were not run.

## Read the results

- `report.json` records calibration thresholds, timings, warnings, class
  confusion, risk denominators and uncertainty for each candidate.
- `class-support-audit.json` adds class support and unfiltered confusion.
- Fitted `.joblib` files and development predictions retain the exact models
  used in the screen.
- `executed-source-receipt.json` identifies the source bytes used for the run.

A candidate warrants a gap projection only if it adds at least three percentage
points of development coverage, reaches 98% observed agreement with a 95%
query-bootstrap lower bound of at least 95%, and adds no Irrelevant → Exact
errors. These are survey screens. Qualification still requires fresh evidence,
adequate support and the established harmful-error bounds.

Zero observed errors cannot establish zero risk. Any bootstrap repetition with
an empty denominator makes that interval inconclusive. Pair confidence bounds
that assume independent pairs are labelled descriptive; they do not establish
the query-clustered quality requirements.

The prior recalibrator was fitted on part of the exposed development cohort,
so its reported prefix quality can be optimistic. The new classifiers fit only
the new pool. This survey leaves gate coverage and deployed judgements unchanged.
