# CPU judgement surveys

These experiments screen inexpensive classifiers for filling ESCI judgement
gaps. They use only the **already exposed development cohort**. They cannot
qualify a model, activate its labels or open a merge gate.

`specialist_survey.py` compares nine small classifiers using query/product word
overlap, product categories and probabilities from the existing classifier.
Query groups are divided into fitting, threshold calibration and evaluation
partitions. The calibration partition selects a confidence threshold for each
ESCI class; the evaluation partition measures the selected rules.

## Run the survey

Use Python 3.12 with the packages in `requirements-cpu.txt`. The measured
surveys used those versions on Windows. From the lab repository, set
`LAB_STATE_DIR` to the state directory containing your preserved development
artefacts. For example, in this lab's PowerShell session:

```powershell
python -m venv .lab/surveys-venv
.\.lab\surveys-venv\Scripts\Activate.ps1
$env:LAB_STATE_DIR = 'D:\codex\Ephemeral Elasticsearch\.lab'
python -m pip install -r lab/experiments/esci-gap-surveys/requirements-cpu.txt
```

On Linux and macOS, create the environment with `python3 -m venv` and activate
it with `source .lab/surveys-venv/bin/activate`. Set `LAB_STATE_DIR` to the
location of your preserved artefacts.

Choose a **new output directory**
for each run; the scripts refuse to overwrite earlier results. Then run:

```powershell
python lab/experiments/esci-gap-surveys/test_specialist_survey.py
python lab/experiments/esci-gap-surveys/specialist_survey.py `
  --state "$env:LAB_STATE_DIR" `
  --output "$env:LAB_STATE_DIR/esci-gap-surveys/specialist-survey"
```

On Linux and macOS, replace PowerShell line continuations with `\` and use
`"$LAB_STATE_DIR"` for the environment variable. The CPU survey was checked on
Windows; these shell equivalents have not been run.

The script requires the existing `esci-packaging/label-calibration-20261003`
development artefacts. It does not read a confirmation cohort or download
data. Each candidate prints its added label count, observed agreement and
combined coverage. `report.json` records input hashes, partitions, model
settings, libraries, class results and uncertainty. The output also includes
pair-level predictions for inspecting development errors.

## Interpret the results

| Output | Meaning |
| --- | --- |
| `standalone` | Labels accepted by the candidate alone |
| `residual_added` | Additional labels after the existing classifier's Exact-at-0.95 comparator |
| `cascade` | Comparator labels followed by accepted candidate labels on remaining pairs |
| Query bootstrap interval | Accuracy uncertainty after resampling whole query groups |
| Irrelevant → Exact | An Irrelevant reference product accepted as Exact; report both the error count and its denominator |

The comparator is an experimental policy, not a qualified stage. Threshold
selection requires at least 20 accepted calibration examples and 98% observed
agreement for a class. That is a quick screen; it does not replace the lab's
confirmation or harmful-error requirements.

Coverage is the proportion accepted **within this development cohort**. It is
not projected coverage of unlabelled search results. Published ESCI agreement
does not establish quality on those gaps; fresh confirmation and independently
labelled gap examples remain necessary. Categories that fail to help a small
linear classifier may still help a model with more explicit product-role
prompts.

## Category roles and embedding extension

`role_specialist_survey.py` keeps the first nine-candidate report unchanged.
It tests category leaves as evidence for accessory roles. A broad department
such as **Cell Phones & Accessories** does not by itself make a phone an
accessory.

The optional embedding input must be the coordinator's CPU-only MiniLM export:
`embeddings.npz` with row-ordered `query`, `title` and `category` arrays, plus
the adjacent `plan.json` and `receipt.json`. The script checks the input and
export hashes. It adds query/title/category cosine similarities and their
interactions with existing classifier probabilities.

```powershell
python lab/experiments/esci-gap-surveys/role_specialist_survey.py `
  --state "$env:LAB_STATE_DIR" `
  --base-report "$env:LAB_STATE_DIR/esci-gap-surveys/specialist-survey/report.json" `
  --embedding-features "$env:LAB_STATE_DIR/esci-gap-surveys/input-embeddings/embeddings.npz" `
  --output "$env:LAB_STATE_DIR/esci-gap-surveys/specialist-survey/embedding-role-extension"
```

The export is text-only and contains no reference labels. This extension still
uses the same exposed development partitions; it supplies no fresh confirmation.

## Measure coverage on saved lab gaps

`project_recalibrator_gaps.py` applies the unchanged simple recalibrator to saved
eligible gap inputs. It makes no inference API calls. It reconstructs the model
from the fitting partition, checks its evaluation probabilities against the
frozen survey and saves the fitted artefact before scoring gaps.

```powershell
python lab/experiments/esci-gap-surveys/project_recalibrator_gaps.py `
  --state "$env:LAB_STATE_DIR" `
  --survey "$env:LAB_STATE_DIR/esci-gap-surveys/specialist-survey" `
  --output "$env:LAB_STATE_DIR/esci-gap-surveys/specialist-survey/actual-gap-projection"
```

The report separates actual qualified coverage from hypothetical coverage if
the candidate stages were qualified. It leaves excluded specialist pairs and
published labels unchanged. The saved gaps have no independent reference
labels, so this measurement establishes **possible coverage, not label quality**.
It does not import or activate predictions.

## Other surveys

| Tool | Inputs and purpose |
| --- | --- |
| `residual_audit.py` | Frozen observations, qualified judgements, catalogue and source metadata; counts missing labels without reading source label values |
| `selective_survey.py` | Exposed development scores; fixed threshold, margin and input-rule screens; `--followup` adds saved-gap coverage projections |
| `support_survey.py` | Fixed same-query published supports; predicts different products using title similarity |
| `embed_inputs.py` | Label-free query/title/category text; creates row-ordered MiniLM embeddings on CPU |
| `nli_survey.py` | A bounded CPU entailment-model pilot, followed by a separate development diagnostic |
| `instruction_survey.py` | Matched broad-category, hierarchy/role and richer-product prompts for a bounded CPU instruction-model pilot |

Run each tool's `--help` for its required paths. The model producers require
Torch, Transformers and Hugging Face Hub; the observed environment used
`torch 2.6.0+cu124`, `transformers 5.17.0` and `huggingface-hub 1.33.0`. Every
producer forces CPU execution. Model weights stay in ignored local caches.
Package versions alone do not establish equivalent results on another platform.

For example, the selective screen uses the existing state directory:

```powershell
python lab/experiments/esci-gap-surveys/selective_survey.py `
  --output "$env:LAB_STATE_DIR/esci-gap-surveys/selective-new-run"
```

The NLI producer's plan fixes a 256-pair throughput pilot before considering
the full cohort. Its `diagnostic` action assesses that retained pilot, while
`evaluate` requires completed full-cohort features. The instruction producer
also retains partial attempts when its time budget is exceeded. An interrupted
or small pilot cannot qualify a model.

See the [measured results](../../../docs/research/evidence/esci-gap-surveys.md)
and [next qualification batch](../../../docs/plans/esci-residual-cascade.md).
