# Headlamp plugin testbed

The lab includes optional controllers for developing the Headlamp KServe plugin.
Use `kserve-test` for plugin fixtures. The search lab continues to use KServe's
Standard deployment mode.

| Component | Installed version | Use |
| --- | --- | --- |
| Headlamp | 0.45.0 | Existing cluster UI; latest release checked on 5 October 2026 |
| KServe LLM controller | 0.21.0 | LLM service and configuration resources; 13 upstream presets |
| Gateway API / Inference Extension | 1.5.1 / 1.5.0 | Routing contracts for LLM services |
| Envoy Gateway / AI Gateway | 1.8.1 / 1.1.0 | Internal Gateway and InferencePool routing integration |
| LeaderWorkerSet | 0.8.0 | LLM worker groups |
| Knative Serving / Kourier | 1.21.1 / 1.21.0 | Revisions, traffic controls and scale to zero |
| KEDA | 2.20.2 | Event-driven autoscaling resources |
| kube-prometheus-stack | 83.4.0 | Prometheus queries for plugin metrics |

Controllers run on `k3d-headlamp-testbed-0`, an additional CPU worker with an
8 GiB memory limit. Its label is `lab.relevance/testbed=true`. Set that node
selector and explicit resource limits on test workloads. The GPU worker retains
its reservation taint; these installs do not load another model onto it.

## Install or check

Run from the **ephemeral-elastic-search-stack checkout**, with Python, PyYAML,
Docker, kubectl and the lab's bundled Helm and k3d tools available. The maintained
checkout on this workstation is separate from `D:\labs\delivery-source`.

PowerShell:

```powershell
$env:LAB_STATE_DIR = 'D:\codex\Ephemeral Elasticsearch\.lab'
uv run --locked python lab/install_headlamp_testbed.py --verify-only
```

The command checks controller rollouts, the 13 LLM presets, internal Kourier
access and the Standard default. To install on an existing lab, omit
`--verify-only`. The installer adds the worker when absent and records the
existing model definitions before installation. It also configures Nexus image
pulls on every Docker-backed cluster node, including the new worker. It fails
if the model definitions change. Installation restarts the KServe controller; existing predictor pods
keep serving.

Linux and macOS use `export LAB_STATE_DIR=/absolute/path/to/lab-state` instead
of the PowerShell assignment. The commands were checked on Windows; native
Linux and macOS installation has not been rehearsed.

The installer uses checksum-pinned manifests and the published rc1 LLM chart
packages with stable 0.21.0 image overrides. It disables shared-resource creation
and chart-managed Inference Extension CRDs. LLM presets come from KServe's
0.21.0 source because those chart packages omit them.

## Use the services

- **Knative:** opt individual test services into `Knative` deployment mode.
  Kourier is internal and does not bind Traefik's host ports. Its internal
  gateway is `kourier-internal.kourier-system.svc.cluster.local`.
- **Prometheus:** use namespace `monitoring`, service
  `kube-prometheus-stack-prometheus`, port `9090` when configuring the Headlamp
  Prometheus plugin. This installation does not install that plugin.
- **Scraping:** add a PodMonitor or ServiceMonitor for the test predictor's
  metrics endpoint. Prometheus discovers monitors across namespaces. Installing
  Prometheus alone does not make an uninstrumented predictor expose metrics.
- **LLM routing:** Envoy serves Gateway `kserve/kserve-ingress-gateway`, class
  `envoy`. Its proxy uses ClusterIP and runs on the testbed CPU worker. KServe's
  LLM controller can attach routes to this Gateway. A routed simulator fixture
  still needs its HTTPRoute, InferencePool and scheduler; gateway readiness does
  not prove inference through that chain. Traefik serves the existing lab URLs.

## Check or reinstall the LLM gateway

Run from the stack checkout with `LAB_STATE_DIR` set as above:

```powershell
uv run --locked python lab/install_headlamp_gateway.py --verify-only
```

Omit `--verify-only` to install. The separate installer requires the testbed
worker, checks chart and upstream values checksums, and applies only Envoy's own
CRDs from its chart. The existing Gateway API and Inference Extension schemas
are preserved. It checks the gateway class, proxy readiness and ClusterIP
service. It also verifies that the existing KServe definitions, ingress
configuration and Traefik deployment remain unchanged.

Envoy needs a read-only ClusterRole for InferencePools: the chart's addon values
enable watching that resource but do not grant access. The maintained RBAC
manifest grants only `get`, `list` and `watch` for those pools.

Configuration is in `lab/headlamp-gateway/`; installation receipts and the
pre-install snapshot are in `$LAB_STATE_DIR/headlamp-gateway`.

To remove the gateway, remove any test routes using it first. With Helm and
kubectl on your PATH, run:

```powershell
kubectl --kubeconfig "$env:LAB_STATE_DIR/kubeconfig.yaml" delete -f lab/headlamp-gateway/gateway.yaml
kubectl --kubeconfig "$env:LAB_STATE_DIR/kubeconfig.yaml" delete -f lab/headlamp-gateway/inferencepool-rbac.yaml
helm --kubeconfig "$env:LAB_STATE_DIR/kubeconfig.yaml" uninstall aieg aieg-crd -n envoy-ai-gateway-system
helm --kubeconfig "$env:LAB_STATE_DIR/kubeconfig.yaml" uninstall eg -n envoy-gateway-system
```

These commands leave Envoy's CRDs and namespaces in place. Do not remove shared
Gateway API or inference schemas. On Linux/macOS use `$LAB_STATE_DIR` in place of
`$env:LAB_STATE_DIR`; those platforms have not been rehearsed.


Prometheus retains 24 hours of data, limits its TSDB to 1 GB and uses disposable
storage capped at 2 GiB. Its memory limit is 2 GiB. Grafana, Alertmanager and
node-exporter are disabled. SigNoz remains the lab's observability dashboard.

## Verification

On 5 October 2026, all installed controllers became Ready. A disposable Knative
service returned `testbed-ok` through Kourier, and Prometheus returned 21 series
for an `up` query. The smoke namespace was removed afterwards.

All six existing InferenceService definitions, six ServingRuntime definitions
and two ClusterStorageContainer definitions were unchanged. Both lab judgement
models remained Ready. The two already-failing plugin fixtures remained failing.
No LLM inference or new model-quality claim was tested.

Local manifests, settings, pre-install snapshots and smoke results are retained
in `$LAB_STATE_DIR/headlamp-testbed`.

The gateway installation on 5 October 2026 passed controller/proxy readiness,
GatewayClass acceptance and Gateway programming checks. An internal HTTP probe
received the expected 404 before any matching route was installed. The probe was
removed; routed LLM inference remains a separate plugin-test step.
