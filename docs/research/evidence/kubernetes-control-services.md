# Kubernetes control services: local evidence

27 September 2026, Windows 11 host with two-node k3d, shared Elasticsearch 9.5.4. All product, query, judgement and traffic data used here is synthetic. These are single functional trials, not capacity estimates.

| Boundary | Observed result |
| --- | --- |
| Placement | Four containers ready in one `lab-control` Pod. `Recreate` replacement kept the 2 GiB PVC and the supervised browser route reconnected. Kubernetes readiness and in-Pod Gitea, Elasticsearch and Nexus smoke checks passed. |
| Migration identity | 137 environment and 31 comparison records crossed the initial cutover. Ordered environment ownership/source/dataset/fingerprint/recipe fields and comparison report references had equal host/PVC SHA-256 digests. |
| Runtime identity | The Pod used an in-cluster ServiceAccount and internal service URLs. Unrelated `default` Secret reads and writes were denied; platform Secret and Job creation remained denied. The control identity can create namespaces and temporary Jobs in `lab-indexing`. |
| Shared-index lifecycle | `lab-7i-control-smoke-3` became ready, served search (HTTP 200) and was deleted. A separately aged `lab-7i-expiry-smoke` was removed by the lease worker after 40 seconds. |
| Dedicated-index lifecycle | `lab-7i-index-smoke-2` rebuilt a separate frozen index with `title-keyword-v1`, served search (HTTP 200) and was deleted. Its temporary Job and credentials were in `lab-indexing`. |
| Result preservation | 51 queries completed with verdict `changed`; report `12bbd786284893b50eb9cb21bb1257587668ee9488c863f001d47ba644ebfdee`. |
| Relevance | 50 queries completed with verdict `measured`; report `81d8e845d6255c70a70db34ddd2716d60f3a60a72081304ffda3d70e666d540d`. |
| Performance | Paired finite Gatling probe completed with verdict `within-budget`; report `b4b02c5ae25d2b45831359e46d383531a8eb477e137684747112dddc2bdc4473`. This result checks the probe configuration, not production capacity. |
| Comparison interruption | A live Gatling Job and running comparison were interrupted by force replacement of the control Pod. The new API marked comparison `db756a5d-a767-4527-937a-b8cb54c2f724` failed with an explicit restart reason; the lease worker removed its labelled Job, Pod, ConfigMaps and PVC. A new quick comparison completed with report `96c4a3a49eb34b44d8aa4bc7a6af4d38179146677cc0b06fb10e2b098b7beb33`. |
| Provisioning interruption | Force replacement of the control Pod left `lab-7i-provision-interrupt-4` in `provisioning`. The lease worker retried after its two-minute stale window, reused the existing labelled namespace without cluster-wide patch access and reached `ready` at 13:35:03 UTC. A separate failed retry was recovered manually after this fix. Both test previews were then deleted through the authenticated API. |
| Deletion interruption | Force replacement during deletion left `lab-7i-provision-interrupt-2` in `deleting`. The lease worker completed deletion at 13:32:42 UTC; the namespace was absent. |
| Delivery from Kubernetes | An initial integration verification timed out: the older frozen target NetworkPolicy did not admit `lab-control`. The installer applied a scoped, additive ingress policy to the three retained targets; direct Search API access then returned 20 IDs and `verify integration` passed in 0.34 seconds. The retained verification report is `f54081ac73f8bf8f45904635cfff2e4031fb7faa9345ac23a1a0e37c45b63c24`. The Kubernetes coordinator also opened production promotion PR 6 with exact-input evidence; validation passed and review is required. |
| Multi-platform image | The published Nexus manifest `b9acc9d1e02ab8b654dacb93944dcb9b6e382218117f36a98371af35c260b4b1` contains `linux/amd64` and `linux/arm64`. An emulated arm64 container imported the native relevance dependencies. The amd64 cluster pulled that digest, replaced the Pod and passed the in-Pod smoke check. |
| State export | A quiescent PVC export produced a 99,430,766-byte archive with SHA-256 `973043aa84dcab69c97ed0bfde09a08f5c19d0f13a3bc83201e028986cad9e27`. Isolated import retained 142 environment and 37 comparison records, both Git checkouts and two releases. The original Pod resumed and passed smoke checks. |
| Fresh checkout | A clean clone of commit `f3c3094` imported that archive, then staged against the existing cluster twice using only the separately supplied kubeconfig and scoped Gitea/Nexus credentials. Both stages passed; the active Pod retained 147 environment and 39 comparison records and passed smoke checks. Activation against an active writer was not run. |
| Resource sample | At idle, the Pod used 7 millicores and 130 MiB; `/state` used 121.3 MiB. These are one-off `kubectl top` and `du` readings. |

The first cutover was rolled back after Windows held a SQLite backup handle open. A second rollback followed a smoke check that incorrectly required Nexus status to return a body. Both faults were fixed before activation. The first live preview then exposed two portability assumptions: Windows Git checkout line endings and an SDK account-name inference from Floci's Kubernetes DNS address. Subsequent checks found missing control ingress on Argo-managed Search APIs, a Windows absolute directory in an older frozen Gatling manifest, and a Gatling report path relative to the source tree. Each fix was followed by a passing operation. No frozen content hash was relaxed.

## Open checks

- A separate fresh-checkout **activation** against disposable control resources has not run. Archive import and repeated staging passed in a clean checkout. Automatic approval review rejected an attempted activation trial against the live cluster because it could disrupt the sole writer; no activation command was run there.
- Dependency outage and failed-deployment readiness trials remain.
- Production promotion PR 6 is validated and awaits human review under the fixture repository's protected-branch rule. Deployment verification and the reverse-evidence rollback follow its merge; the coordinator has not yet completed those two operations from Kubernetes.
- Native Apple silicon and AKS validation remain external gates. The emulated arm64 build and import are not a native Mac trial.

The [runtime guide](../../control-runtime.md) contains commands and state boundaries; [the batch plan](../../plans/kubernetes-control-services.md) retains the remaining acceptance criteria.
