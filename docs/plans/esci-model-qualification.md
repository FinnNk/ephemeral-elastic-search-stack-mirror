# Qualify the registered ESCI judge

## Intent and constraints

Qualify a pinned registered ESCI release as a selective first pass for judgement
gaps. Keep the 80% coverage gate and the model's acceptance thresholds unchanged.
Qualification does not implement the later cascade passes.

- Add an optional NVIDIA worker; leave the default CPU topology independent of it.
- Coordinate a checkpointed research pause before inference. A free GPU interval
  between automatically scheduled research stages is not a handover.
- Preserve research reservations, caches and failed attempts. Never tune on the
  ongoing experiment's frozen final assessment.
- Pin assets, wrapper, serving image, thresholds and inputs. Do not add data
  compatibility adapters or rewrite existing evaluation evidence.
- Keep the active bootstrap judge until serving and quality evidence has been reviewed.

The optional worker is ready for review. The original serving attempt and the
[larger investigation](../research/evidence/esci-probability-diagnostics.md)
identified silent kernel fallback and batch-size sensitivity. The explicit
singleton release starts with verified FLA but still fails independent numerical
agreement; [evidence](../research/evidence/esci-inference-contract.md) records the
results. Next, [freeze and qualify the kernel profile](esci-kernel-reproducibility.md).
Quality assessment has not started.

## Batches and acceptance

| Batch | Work | Acceptance |
| --- | --- | --- |
| Optional worker | Build the same k3s version with NVIDIA runtime; join a separate restricted worker; add a node-scoped device plugin and removal command | Existing nodes remain Ready; one GPU advertised; model manifests target the optional worker; no model inference during preparation |
| Serving qualification | During the agreed GPU window, deploy the candidate; check actual image/model identity and 64 independent canaries | Batch, singleton and reversed requests differ by at most 0.0001 probability, with no label/abstention changes; repeat after cold restart |
| Quality qualification | Audit query overlap; reserve separate calibration and confirmation cohorts and representative lab gaps; inspect accepted labels | Report accepted accuracy with uncertainty, coverage, per-class outcomes and Irrelevant-to-Exact errors; distinguish historical evidence from new observations |
| First-pass decision | Assess the evidence and choose activation or further work | Retain explicit model provenance and one frozen judgement set across all variants; inadequate quality or coverage remains blocked |

The first batch ends with a PR and an updated plan. The next detailed batch must
record the agreed GPU pause/resume procedure and quality cohort allocation before
running its model calls. Precision acceptance criteria must be fixed before
opening confirmation results; the historical 0.90 cutoff is not independently
qualified on the lab's gaps.

## Sources

- [Model installation](../esci-model-installation.md): registered bundle, canaries,
  numerical checks and rollback.
- [Optional worker](../gpu-worker.md): local GPU setup and removal.
- [Catalogue evidence](../research/evidence/esci-catalogue.md): current coverage gap.
- `judgements/esci/qualification.py`, `deployment.py` and `contract.py`.
- The separate “Implement on-demand ESCI judging” session owns its research
  pipeline and query reservations. Its current unfine-tuned model is different
  from this registered LoRA and learned-mapping candidate.
