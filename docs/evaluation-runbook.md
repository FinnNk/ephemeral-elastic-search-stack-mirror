# Capture, score and publish variant evidence

Use this operator procedure for standalone studies, recovery and explicit evidence
publication. Routine source PR comparisons run through the coordinator and
[Actions](remote-delivery.md); engineers do not need these commands or publisher
credentials. Both paths retain exact images, frozen inputs and signed evidence.

## Prepare inputs

Prerequisites: running lab/control services, ready Argo-managed search environments, compatible published inputs, Python and the Azure/evaluation dependency files under `lab/`. Use PowerShell from the repository root. Select the retained state directory when working in another checkout.

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
$kubeconfig = Join-Path $env:LAB_STATE_DIR kubeconfig.yaml
$env:PYTHONPATH = Join-Path $env:LAB_STATE_DIR python-libs
$inputDir = Read-Host 'Absolute directory containing the selected frozen input pack'
$manifestDir = Read-Host 'Absolute directory containing its published manifests'
$variantSet = Read-Host 'Absolute path to the frozen variant-set JSON'
$runDir = Join-Path $env:LAB_STATE_DIR ('evaluation-' + (Get-Date -Format yyyyMMdd-HHmmss))
New-Item -ItemType Directory -Path $runDir | Out-Null
```

| File/value | Authoritative source |
| --- | --- |
| `products.jsonl` or `products.jsonl.gz`, `queries.jsonl`, `judgements.jsonl` | Selected producer's retained pack; [publication procedure](data-evaluation-contracts.md#generate-and-publish-an-input-pack) |
| `catalogue.json`, `query-suite.json`, `judgement-set.json` | The matching publication output, not a different release's manifests |
| Variant set | Lab operator's frozen deployment selections; fields below |
| Metric specification | `evaluation/specs/proxy-v2.json` or a reviewed replacement |
| Source commit, run and attempt | Exact successful source PR build and its Nexus receipt |

A variant-set file has `kind: search-variant-set`, `schema_version: 1`, `default_variant`, `baseline_variant` and a `variants` object. Each named entry has `environment`, `environment_fingerprint`, `configuration_sha256` and `selection` (`default` or `explicit`). Obtain the fingerprint from its retained environment definition and configuration digest from that deployed API's echoed response. The names must match the API's variant IDs, including when two releases use separate deployments. Do not fill these fields with illustrative hashes.

Capture forwards the frozen query, country, currency and filters to every variant. The API must echo the same filters; a missing or different echo makes the capture incomplete. See the [filter contract and query-suite example](search-request.md).

Prepare configurations in the environment-state definition and let Argo reconcile them before capture. Capture verifies those definitions and the API responses; it cannot deploy a variant-set file by itself.

## Capture and score

```powershell
uv run --locked python evaluation/capture.py --variant-set $variantSet --queries "$inputDir/queries.jsonl" --query-manifest "$manifestDir/query-suite.json" --catalogue-manifest "$manifestDir/catalogue.json" --output "$runDir/observations.json"
uv run --locked python evaluation/offline.py --observations "$runDir/observations.json" --judgements "$inputDir/judgements.jsonl" --specification evaluation/specs/proxy-v2.json --catalogue-manifest "$manifestDir/catalogue.json" --query-manifest "$manifestDir/query-suite.json" --judgement-manifest "$manifestDir/judgement-set.json" --output "$runDir/evaluation.json"
```

Capture makes fresh API requests with eight query workers. Each worker visits
variants sequentially; observations retain the frozen query order. The Search API
reuses verified Elasticsearch connections, while every request still executes a
new search. Load testing remains a separate Gatling workflow.

Workers share an adaptive pacer for each API. HTTP 429, transient server errors
and connection failures slow further requests; successful responses gradually
remove that spacing. Requests have at most three attempts and a 30-second
retry/pacing budget. Long `Retry-After` values can exhaust that budget. Failed
queries remain visible and invalidate a complete capture.

Retained execution records include attempts, retries, failures, spacing and
cumulative worker wait for each API. Read these beside elapsed time: the pacer
may make a functional evaluation slower to avoid overload. It does not change
Gatling load profiles or their performance verdicts. See the
[pacing measurements](research/evidence/evaluation-pacing.md).

Capture prints its observation hash/Blob reference and retains ordered results. Scoring prints completeness, query count and per-variant metrics. Inspect `evaluation.json`, coverage and changed queries; positive deltas with poor coverage are not sufficient evidence.

If responses or identities mismatch, fix the deployed definition before recapturing. For missing labels, use [pooled judgement resolution](judgement-resolution.md#capture-resolve-and-score) instead of the direct scoring command. Every variant must use the same frozen labels. Changed bytes require a new output directory; frozen reports are not overwritten.

## Run exploratory analysis

With installed notebook support:

```powershell
uv run --locked python lab/run_notebook.py --report "$runDir/evaluation.json" --notebook comparison-explorer.ipynb
```

The command prints the retained executed-notebook reference. This saved analysis is independent of the verdict. [The lab guide](../lab/README.md#download-exploratory-analysis) shows the selector and output. If the notebook fails, retain that failure separately and continue to assess the normal report.

## Supply exact-commit merge evidence

1. Copy the current PR's source SHA, successful build run and attempt from CI. Download its `builds/<sha>/<run>-<attempt>.json` from Nexus `lab-releases` using your scoped reader or the Nexus UI. Save it in `$runDir/build-receipt.json`. Confirm the captured candidate image is the image in that receipt.
2. Set the source SHA and issue the attestation. The operator tool obtains its signing key from retained vault state:

   ```powershell
   $sourceSha = Read-Host 'Exact evaluated PR head SHA'
   uv run --locked python lab/variant_gate_issue.py attest --report "$runDir/evaluation.json" --source-sha $sourceSha --build-receipt "$runDir/build-receipt.json" --output "$runDir/attestation.json"
   ```

3. Load only the scoped Nexus publisher into this process and publish the immutable evidence:

   ```powershell
   $nexus = Get-Content (Join-Path $env:LAB_STATE_DIR nexus.json) -Raw | ConvertFrom-Json
   $env:ARTIFACT_URL = 'http://127.0.0.1:18183/repository/lab-releases'
   $env:NEXUS_USER = $nexus.publisher.username
   $env:NEXUS_PASSWORD = $nexus.publisher.password
   uv run --locked python lab/delivery/ci/variant_gate_store.py publish-evidence --source-sha $sourceSha --report "$runDir/evaluation.json" --attestation "$runDir/attestation.json"
   Remove-Item Env:NEXUS_PASSWORD
   ```

   The publisher verifies the exact receipt and reads back the stored bytes. A conflict means existing frozen evidence differs; investigate instead of replacing it. Signing confirms provenance, not relevance quality.
4. Run `python ci/lab_delivery.py gate-check --pr PR_NUMBER --source-sha SOURCE_SHA`
   from `delivery-source`, or choose `gate-check` in **Advanced delivery**.
   Use the unchanged PR's number and exact commit. A new commit requires its own build and evidence. A later build attempt can have another image; the attested receipt identifies the evaluated one.

## Human exceptions

The temporary ESCI [demo policy](judgement-resolution.md#temporary-esci-demo-labels) is a separate human-authorised quality allowance. Its predictions remain unqualified, and strict selection excludes them. The protected policy permits only the recorded model and source scope; other exploratory labels cannot pass.


Only a `decision_required` result is eligible for a bounded exception. The
normal coverage requirement remains 80%. The checker and policy also
allow a low-coverage decision for `preserve-results` when all these conditions hold:

- Every captured query returns identical ordered product IDs and total counts.
- Candidate and baseline scores and coverage are exactly equal.
- The report uses published or qualified labels, or the exact authorised lab demo policy, without exploratory predictions.
- The evaluated image and signed evidence match the exact source PR build.

This checks the saved results at the capture depth, not the whole catalogue.
A human administrator must approve the disclosed coverage gap. Low-coverage
`ranking-change` reports, changed results and unqualified labels outside the authorised lab demo policy stay blocked.
The protected coordinator must use the accepted policy and code pins. Declaring
`preserve-results` does not approve the disclosed coverage gap.

Use the [Git decision procedure](variant-evaluation.md#accept-a-bounded-regression)
from the source comparison. The human administrator reviews the disclosed loss
or permitted coverage gap in a `delivery-state` decision PR. After its exact
head is approved and merged, the coordinator publishes the signed receipt and
rechecks the frozen evidence. No signing key or Nexus credential is needed on
the developer's workstation.

The verdict retains actual baseline/candidate coverage and required coverage,
with `coverage_exception: true` for the narrow case above. Hard blocks and
invalid evidence cannot be approved away. Passing the source gate does not
authorise deployment.

## Rescore as a finite Job

For installed producer/evaluator images and a local Blob Storage emulator connection string in `DATA_BLOB_CONNECTION_STRING`, retain the captured observations and specification:

```powershell
uv run --locked python evaluation/retain.py --file "$runDir/observations.json" --kind observation-set --output "$runDir/observations.ref.json"
uv run --locked python evaluation/retain.py --file evaluation/specs/proxy-v2.json --kind evaluation-specification --output "$runDir/spec.ref.json"
uv run --locked python evaluation/run_job.py --observation-reference "$runDir/observations.ref.json" --specification-reference "$runDir/spec.ref.json" --catalogue-manifest "$manifestDir/catalogue.json" --query-manifest "$manifestDir/query-suite.json" --judgement-manifest "$manifestDir/judgement-set.json"
```

Publish tool images first with `uv run --locked python lab/publish_tool_images.py` if the retained state lacks their digest file. The reference's outer `kind: observation-set` identifies a retained file; its payload must still use the current variant-observation schema. The Job prints its retained report reference and removes temporary resources. It does not contact Search APIs. The observation/specification reference files are produced here, rather than assumed to exist in an ignored historical directory.
