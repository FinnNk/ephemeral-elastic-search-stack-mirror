# Gatling runner

The Java simulation uses Gatling 3.15.1 and Maven plugin 4.21.12 from the [official Java example](https://github.com/gatling/gatling-maven-plugin-demo-java/blob/main/pom.xml). The container image is pinned by digest in [`run_gatling.py`](../run_gatling.py). No host Java installation is required.

From the repository root, generate and compile the frozen wholly synthetic workload, then run a baseline/candidate pair:

```powershell
python lab/traffic.py generate
python lab/traffic.py compile --profile probe
python lab/run_gatling.py probe baseline
python lab/run_gatling.py probe candidate
python lab/compare_gatling.py probe
```

`run_gatling.py` uses the two local loopback API forwards (`18080` and `18081`) and a CPU/memory-capped Docker container. `run_gatling_job.py` runs the same simulation as a finite Kubernetes Job against the in-cluster service and copies its output from a temporary PVC before removing the Job, ConfigMaps and PVC. It creates each uniquely named workload ConfigMap directly: client-side apply would duplicate a long CSV in an annotation and reject the sustained-peak schedule. The control API performance mode uses the Job runner for selected ready environments.

The compiled schedule and each phase's feeder are under ignored `.lab/workloads/`. Gatling records actual arrivals and makes a native HTML report. The adapter requires every planned event and matching phase count; warm-up and ramp metrics are excluded from measured budgets. Native reports are archived in Floci by hash. The [traffic modelling note](../../docs/research/synthetic-traffic.md) records the assumptions and phase profiles.

For `retail-gb-1m-v1`, compile a profile with `python lab/traffic.py compile --profile sustained-peak --release retail-gb-1m-v1`. In the control UI, select two ready environments on that release and choose **Gatling performance**. The `smoke` profile measures five minutes at 10 requests/s; `normal-full`, `sustained-peak` and `stress-full` use the separate 30-minute frozen trace. The UI runs the two finite Jobs sequentially and retains both native reports and a paired verdict. The CLI target aliases above refer to the original 10,000-product environments; the [scale evidence](../../docs/research/evidence/million-scale.md) identifies the million-product environments and measured outcomes.
