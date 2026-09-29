# Local judgement gap resolution evidence — 29 September 2026

## Scope

The local k3d cluster ran cert-manager `v1.17.0`, KServe `v0.19.0` in Standard mode and the official MLflow chart `0.1.0` with an MLflow `3.16.1` image. MLflow used its own PostgreSQL database and a separate S3 prefix in the existing SeaweedFS service. Floci Blob supplied the synthetic 10k catalogue, query suite and original labels. ESO supplied credentials from Floci Key Vault. The x86 image was published to Nexus with a tag derived from source bytes. Apple silicon was not tested: Docker Desktop here could not execute the arm64 build stage (`exec format error`).

## Observed checks

| Check | Observation |
| --- | --- |
| Registry and model | Registered `synthetic-esci-judge` version `1`; KServe initialiser verified artefact SHA-256 `364d0b0961e682ba1440ff570a6288631486c1362e2b68f328aafcf270e5d894` before the predictor became ready. |
| Judgement API | Live smoke returned a stored `E` label, returned `unjudged` for an absent pair after KServe abstained, and rejected a forged product record with HTTP 400. |
| Reconciliation | `python lab/setup_judgement_stack.py` completed on the existing cluster, followed by `--verify-only`. The optional `--million` profile also reached readiness. These runs tested idempotence; they did not recreate the whole cluster from zero. |
| Retained 10k comparison | A 50-query observation set required 500 distinct top-ten pairs. Stored labels covered 444; the model abstained on 56; inference failures were zero. Both sides had 444/500 judged coverage (`0.888`). |
| Offline report | Baseline and candidate both yielded `nDCG@10=0.911474`, `Judged@10=0.888`, `RR@10:rel=2=1.0` against one frozen judgement hash `4f828c0c574aabb71d26e9417e3b48cc47a32587d6a2303a1776d21f08951e23`. |
| Immutable replay | Two evaluations of the same observation, source, specification and model produced report SHA-256 `b0f9b20d140081ec2871a69b8313d274409f121acf9b7535746c8bdc85e799e6`. The second reused the exact frozen bytes. |
| Million-product import | The first implementation stored every product record in SQLite and occupied 3.5 GB. Storing only SHA-256 identities reduced the fresh 1M cache to 243 MB; the source bytes remain in the pinned Blob object. The compact service passed stored-label, abstention and forged-record checks. One fresh Pod reached readiness in 43 seconds; a restart with retained cache reached readiness in 3 seconds. |
| Million-product evaluation | A retained 1,000-query observation set required 10,000 distinct top-ten pairs. Stored labels covered 21; KServe abstained on 9,979; failures were zero. Both sides had 21/10,000 judged coverage (`0.0021`). The report SHA-256 was `9712ffe22c42da466bcd57cbb5fa3e20b6232a41699b2fd3b86ebd9249e78d24` on two runs; one replay took 16.46 seconds end to end. |
| Failure path | An expired port-forward produced inference errors; the wrapper now marks reports with failed gap resolution `complete=false`. Unit coverage verifies this. |

These figures establish correct wiring and source separation. The all-abstaining model did not improve coverage or relevance. The million-release score is not suitable for a relevance decision: 99.79% of the returned pairs remain unjudged, far below the existing 80% coverage gate. Both retained examples have equal B/C result lists; an integration test introduces a candidate-only pair, creates a separate snapshot, and confirms both sides use it.

## Resource snapshot

One `kubectl top pods --containers -n lab-models` sample after the 10k run reported MLflow `1622Mi`, PostgreSQL `51Mi`, KServe predictor `134Mi` and judgement API `15Mi`. The compact 1M import used about `101Mi` after reaching readiness; another sample during import showed `71Mi` and one CPU core. The running Pods had zero restarts. One Pod creation-to-ready sample reported 25 seconds for MLflow, 18 seconds for PostgreSQL, 5 seconds for the predictor and 3 seconds for the 10k API. These are warm local observations, not cold-cluster start-up targets or distribution measurements. MLflow alone is a material persistent memory cost; sharing it across ephemeral environments is part of the topology.

## Remaining validation

Run a clean-cluster bootstrap and active-recall API comparison with this path. Publish and run an arm64/multi-platform image on Apple silicon. Validate AKS identity and object storage before treating the Azure placement as implemented. Test a non-abstaining model and its review process before using inferred labels as relevance evidence.
