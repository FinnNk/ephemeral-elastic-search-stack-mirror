# Verify Headlamp plugin workflows

## Intent

Exercise the plugin against the newly installed Kubernetes controllers, using
small CPU fixtures in `kserve-test`. Installation and endpoints are documented
in [Headlamp plugin testbed](../headlamp-testbed.md).

## Constraints

- Keep the lab's Standard deployment default and existing search/model pins.
- Use the testbed CPU worker and explicit workload resource limits.
- Obtain separate authorisation before loading a GPU model. The authorised
  internal Envoy gateway is installed separately; its readiness alone does not
  establish inference through a route, pool and scheduler.
- Keep deliberately failing fixtures distinguishable from installation failures.
- Prometheus supports plugin metrics; SigNoz remains the lab dashboard.

## Acceptance criteria

| Workflow | Evidence required |
| --- | --- |
| LLM configuration | Plugin displays the 13 presets and distinguishes inherited from service-owned configuration |
| LLM routing | A CPU simulator route reaches its InferencePool through the internal Gateway and scheduler; the plugin shows those resources |
| Knative lifecycle | A CPU fixture shows readiness, revisions and traffic allocation correctly |
| KEDA scaling | Plugin reads and edits the ScaledObject bounds rather than an unrelated HPA |
| Metrics | Headlamp's Prometheus plugin discovers the monitoring service; a fixture exposes a scraped metric |
| Isolation | Existing judgement services remain Ready and their model/runtime definitions remain unchanged |

Record the plugin release, exact fixture manifests, observed UI behaviour and
controller state. Remove disposable fixtures after verification. Review this
batch in the plugin project; these are follow-up criteria, not checks already
performed by the lab installer.

## Further information

- Installer: `lab/install_headlamp_testbed.py`.
- Versions, source checksums and limits: `lab/headlamp-testbed/`.
- Local installation snapshots and smoke evidence: `$LAB_STATE_DIR/headlamp-testbed`.
- Original requested scope: `research/headlamp testbed/lab-installs-for-r2-r3.md`.
