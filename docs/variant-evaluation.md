# Offline evaluation of search variants

A variant is one pinned public Search API behaviour. The variant set names exactly one **default** for requests without a selector and one **baseline** for metric deltas. These roles may name different variants. The proposed production choice is made later by a separate gate decision.

| Shape | Capture | Production path |
| --- | --- | --- |
| Replacement release | Current version and proposed version, each selected as its deployment default | Proposed version replaces the current default after promotion; no online flag or traffic split is needed. |
| Runtime choices | Two or more named configurations served by one or more pinned APIs | A selected configuration may later be activated through the production feature-flag mechanism. The offline run makes no traffic-allocation decision. |

`SEARCH_VARIANTS_JSON` contains a `default_variant` and a map of named configurations. Each configuration has four bounded `field_boosts`: `title`, `product_type`, `brand` and `description`. An omitted `X-Lab-Variant` selects the default; an explicit header selects a named configuration. The public response echoes `variant_id` and `configuration_sha256`. The digest is SHA-256 of the selected configuration's sorted, compact JSON. A changed or unknown selection fails the capture.

The frozen `search-variant-set` selects each variant's environment name, environment fingerprint, configuration digest and `default` or `explicit` request selection. A single environment may serve several variants; different API images or index schemas use separate frozen environments. `evaluation/capture.py --variant-set ...` validates the current environment definitions and sends the same synthetic query suite to every selected public API. It retains one `search-variant-observation-set` containing a named result for every query and variant. Any error, missing result or identity mismatch invalidates the capture.

`judgements/evaluate.py` forms the union of all variants' result pairs through the requested metric depth. It uses stored labels first, requests missing pairs from the pinned model and freezes one judgement set. `evaluation/offline.py` scores each variant against that same set and reports per-variant metrics, coverage, query-level values and deltas from the named baseline. A model abstention remains unknown; low judged coverage stays visible alongside scores.

The variant observation and report contracts are the only inputs to the new offline variant gate. Earlier pair-shaped artefacts remain historical evidence and are rejected by these commands. Recreate an evaluation from the synthetic generators and pinned Search API images when a new decision needs current evidence.

The [implementation plan](plans/offline-variants-and-gates.md) covers the gate and human decision record. A passing metric is evidence for a decision, not the decision itself.
