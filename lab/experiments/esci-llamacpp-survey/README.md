# llama.cpp CPU prompt survey

Run a small, reproducible ESCI prompt survey using a quantised Qwen model. This
experiment does not change the judgement service, import labels or open gates.

The measured Windows probe scored 32 pairs with three prompts in 213 seconds.
It projected 28.45 minutes for the full sample and stopped at the fixed budget.
The [aggregate evidence](../../../docs/research/evidence/esci-cpu-pair-judges-prompts.json)
contains the results and hashes. Prompt differences are exploratory; the sample
contains only one Irrelevant reference.

## Prerequisites

- Windows x64, Python 3.12 and NumPy. The commands below use the lab's existing
  packaging environment; install no global runtime.
- Run from the repository root. The lab state is `D:\codex\Ephemeral Elasticsearch\.lab`.
- The exposed development cohort at
  `.lab/esci-packaging/label-calibration-20261003`, including inputs and published
  references. Confirmation cohorts are excluded.
- Internet access for the official binary and model, approximately 1.14 GB of
  downloads, and at least 5 GB of free disk space.

The binary archive and Q4_K_M model are pinned by publisher hashes. Archive paths
are checked before extraction. The server uses CPU only, four threads, one slot
and a temporary loopback port. The script stops its own process in `finally`.
Linux and macOS were not tested by this experiment.

## Run an isolated survey

In PowerShell, from the repository root:

```powershell
$surveyPython = 'D:\codex\Ephemeral Elasticsearch\.lab\esci-packaging\.venv\Scripts\python.exe'
$surveyRuntime = 'D:\codex\Ephemeral Elasticsearch\.lab\esci-fitted-specialists\llamacpp-survey\runtime-01'
$surveyOutput = 'D:\codex\Ephemeral Elasticsearch\.lab\esci-fitted-specialists\llamacpp-survey\attempt-02'

& $surveyPython lab/experiments/esci-llamacpp-survey/llamacpp_survey.py prepare --runtime $surveyRuntime
if ($LASTEXITCODE -ne 0) { throw 'Runtime preparation failed.' }

& $surveyPython lab/experiments/esci-llamacpp-survey/llamacpp_survey.py generate --runtime $surveyRuntime --output $surveyOutput
if ($LASTEXITCODE -ne 0) { throw 'Survey generation failed.' }
```

`prepare` verifies existing downloads or downloads the pinned official files.
`generate` freezes the prompt contracts and selected inputs before inference.
It scores 32 matched pairs, then continues only if the projected 256-pair survey
fits its 15-minute inference budget. Read `generation.json` and `probe.json` for
the outcome; `cleanup.json` records the owned server's exit.

Use a new output directory for each run. Preserve interrupted downloads and
failed attempts; do not overwrite previous results. If preparation fails, inspect
its `failure-*.json` receipt and choose a fresh runtime directory for a retry.

After generation ends, assess its outputs against the same exposed development
references:

```powershell
& $surveyPython lab/experiments/esci-llamacpp-survey/llamacpp_survey.py evaluate --runtime $surveyRuntime --output $surveyOutput
if ($LASTEXITCODE -ne 0) { throw 'Development assessment failed.' }
```

This writes `diagnostic-plan.json` before opening reference labels, then writes
`report.json`. It reports matched confusion matrices and error counts. It does
not establish model qualification or performance on actual judgement gaps.

## Interpret the output

- The three prompts reuse the original definitions, role instructions and
  development sample. The rich prompt adds brand, bullets and description.
- Product fields may be null. Rich text is shortened to keep the instructions
  and query within the 512-token budget; truncation is recorded per score.
- The grammar requires one of E/S/C/I. Greedy grammar-conditioned choices are
  not calibrated probabilities and cannot supply selective acceptance thresholds.
- Quantisation, chat formatting and backend caching differ from the previous
  PyTorch pilot. Neither output parity nor isolated hardware speed is claimed.

The packaging helper, `package_evidence.py`, reproduces the committed aggregate
receipt from the retained `attempt-01` artefacts and its frozen post-probe paired
analysis amendment. It starts no model or server. It is specific to that measured
run; new runs need their own frozen diagnostic and evidence destination.

## Sources

- [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/7fe450e19305b828c199d602c23a8337aaa1f03b/tools/server/README.md)
- [Pinned Windows CPU release](https://github.com/ggml-org/llama.cpp/releases/tag/b11146)
- [Official Qwen GGUF model](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/91cad51170dc346986eccefdc2dd33a9da36ead9)
