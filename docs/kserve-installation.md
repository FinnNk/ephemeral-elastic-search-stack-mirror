# Install or upgrade KServe

The lab uses **KServe 0.21.0** in Standard mode. The controller manages the
InferenceService; its custom storage initializer downloads a pinned model
version from MLflow.

From the lab repository, with `LAB_STATE_DIR` set to the retained `.lab`
directory, run in PowerShell:

```powershell
uv run --locked python lab/setup_kserve.py
```

On Linux or macOS, use `python3`. Requires the running lab, kubectl, Helm and
lab Python dependencies. Expect confirmation that KServe is installed and model
and runtime definitions are preserved. This command upgrades the controller and
CRDs without redeploying MLflow or resetting the selected judgement model.
The initial judgement-stack installer uses the same KServe pins.

Check readiness:

```powershell
kubectl get pods -n kserve
kubectl get inferenceservices -A
```

Expect the controller Pod to be ready and the judgement InferenceService to show
`READY=True`. If rollout fails, inspect the controller events and logs before
changing model pins. Definitions and previous Helm values are retained in
`.lab/kserve-upgrade` for diagnosis. Helm retains the previous release revision;
check CRD compatibility before attempting a downgrade.

## Release packaging

The official 0.21 release's charts carry `rc1` labels. The lab retains those
original files with checksum verification and explicitly selects stable 0.21
images. See the [upstream issue](https://github.com/kserve/kserve/issues/6314)
and [vendored chart provenance](../lab/vendor/kserve-0.21.0/README.md).
[PR #6343](https://github.com/kserve/kserve/pull/6343) addresses the publication
scripts but does not republish the charts.

## Local verification

On 3 October 2026, the controller reached `2/2 Running` with zero restarts.
Existing model, ServingRuntime and custom storage-loader definitions retained
both their identities and specifications. A fresh disposable InferenceService
loaded model version 1 through MLflow and returned `abstain`; it was removed
then. The judgement API returned its stored Exact label, left the missing pair
unjudged and rejected forged product content. Repeated installation passed.
These checks establish local operation, not judgement quality or Apple silicon
compatibility. Aggregate results are in `.lab/kserve-upgrade/verification.json`.

## Traefik ingress

The installer sets `ingressClassName=traefik` and
`disableIstioVirtualHost=true`. This matches the lab ingress controller and
stops the warning about missing Istio VirtualService CRDs. Eight fresh
reconciliations after applying the settings emitted no such warning, the model
remained ready and the judgement API checks passed.

The advertised `example.com` model URL remains a placeholder; the judgement
API uses its internal Kubernetes Service address. These settings do not create
public model DNS names or change model selection.

The installer's preservation check caught a concurrent change to a separate
`iris` demo model during this run. The active `synthetic-esci-judge` definition
was independently checked and unchanged. A concurrent model edit can trip this
check even when controller installation succeeds; inspect the retained before
snapshot and current definitions before retrying.
