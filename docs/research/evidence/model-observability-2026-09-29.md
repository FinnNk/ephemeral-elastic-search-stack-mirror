# Model observability: local proof, 29 September 2026

This proof uses only the synthetic `retail-gb-10k-v1` source. It checks signal transport and trace continuity, not judgement quality or model accuracy.

| Check | Observation |
| --- | --- |
| Model path | A two-query frozen evaluation required ten query-product pairs. Five source labels were reused; the pinned model abstained on five gaps; no model call failed. The replay report hash was `c9a8b3df68481053fa72fd774cb03bac498e33499da437f122925658e0eb09ef`. |
| Trace | SigNoz stored trace `7917daa15c79455a36a2c28ac47c265a` with `judgement.evaluate` → `judgement.resolve` → `judgement.http` → `judgement.lookup` → `kserve.predict` → `model.http` → `model.predict`. Parent span IDs connected both HTTP boundaries. |
| Dashboard | The source-controlled dashboard was applied to ID `01a0ea97-de6a-74fb-bbc2-319512f4a8d2`. A browser check showed the panels without query-error markers. SigNoz stored 50% pooled label coverage and query-length input-shift JSD `0.311278` for this run. The model-label panel correctly had no data. |
| Search API | An instrumented disposable Search API served a 20-result synthetic request over the frozen baseline index. SigNoz stored trace `7ce4d48bea153684dd36dc2777669822`: `search.request` had the supplied parent span `33a5932739824925`, with `search.query_understanding` and `search.elasticsearch` beneath it. The disposable Deployment, Service and additional egress policy were removed after the check. |

The input-shift reference is the frozen observation-query length mix. The measured side is the length mix of pairs sent to inference. This is **selection into inference**, not drift against model training data. The all-abstaining model cannot yet yield accuracy, output-label drift or model-labelled coverage. These panels must retain an unknown state until a reviewed model emits labels and reviewed source labels support a quality estimate.

The checked source deployment chart enables OTLP/HTTP and gateway egress. Older retained Search API deployments predate those settings and dependencies, so they require a new image and chart reconciliation before producing these spans. This proof did not modify those frozen deployments. Control-to-capture traceparent propagation is also covered by the finite worker tests; capture and later offline evaluation remain separate traces joined by retained observation hashes.

Commands used for repeatable checks include `python -m unittest discover -s judgements -p 'test_*.py' -q`, `python -m unittest lab.test_evaluation_worker -q`, and `python lab/observability/probe_model_trace.py --inputs <staged synthetic source> --output <new ignored directory>`. The probe output directory is immutable on replay and remains outside Git. SigNoz trace and metric rows were checked read-only after export.
