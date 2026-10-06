# Final production release

## Intent

Compare the candidate API with the active production API before switching the production URL. Demonstrate blue–green deployment with one shared, frozen catalogue and a recent-query fixture.

## Constraints

- Keep integration and staging promotions and the production normal/peak Gatling gate.
- Two API deployments and named services share the production namespace; the stable service selects one slot.
- Candidate preparation and activation are separate reviewed desired-state PRs.
- Require identical concrete index, catalogue, mapping and request context. Check the Elasticsearch write block before and after evaluation and immediately before activation.
- Retain queries, observations, resolved labels, resolution outcomes and the final report by hash. No previous-data adapters.
- Use existing judgement inference reuse and pure scoring; leave the broader evaluator refactor deferred.
- Recent queries are a deterministic ESCI fixture, not observed production traffic.
- Expose preparation, evaluation, reviewed merge and rollback through authenticated UI operations.

## Acceptance criteria

| Check | Expected result |
| --- | --- |
| Prepare candidate | Active release remains selected; both slots are independently reachable |
| Final comparison | Baseline calls the stable active service; candidate calls its slot service |
| Labels | Resolve union gaps once, freeze labels, score both sides together; show abstentions and coverage |
| Activation | Existing full gates and fresh final evidence bind exact slots; human approves exact PR |
| Stale evidence | Changed slot, catalogue or active release blocks activation |
| Switch and rollback | Service selector changes; previous deployment remains available |
| UI | Named operations, progress, friendly reports and review links; no developer kubectl |
| Documentation | Release guide and SDLC show prepare, final check, review, switch and retained rollback |

## Implementation order

1. Add the slot state, deterministic rendering and reviewed preparation.
2. Add service-targeted capture, recent-query resolution and activation validation.
3. Add UI controls and friendly reports; update delivery documentation and SDLC.
4. Run focused contract tests and a lab preparation/comparison rehearsal where resources permit. Record limits and open a review PR.

## More information

- [Delivery](../delivery.md): existing promotion gates and approvals.
- `lab/delivery_runtime.py`, `lab/delivery_promote.py`: desired-state rendering and verification.
- `lab/additional_judgements.py`, `evaluation/query_sets.py`: resolution and frozen scoring.
- [Walkthrough feedback](walkthrough-feedback.md): deferred evaluator boundary.

## Next batch

After acceptance, follow the [production release walkthrough plan](production-release-walkthrough.md). Keep the active release unchanged until its activation PR is approved.

## Validation

The implementation is installed in the lab for review. [Retained evidence](../research/evidence/production-blue-green.json) records the isolated Argo rehearsal.

| Check | Observed result |
| --- | --- |
| Focused Python tests | 56 passed; includes stale evidence, write blocks, route readiness, preparation boundaries and current/candidate details before preparation |
| Browser tests | Named UI operations, reader restrictions, friendly reports, release details, approved-PR selection, empty states and mobile layout passed |
| Diagram | 9 showcase checks and 8 light/dark browser cases passed; full timeline inspected |
| Isolated rehearsal | Four real queries, same image in two slots; capture, shared labels, scoring and blue→green route switch passed |
| Rehearsal coverage | 36/40 results labelled per side; one request inferred four pairs; nDCG matched as expected for identical APIs |
| Production | Existing active release unchanged |

The rehearsal tests topology, not a new release's relevance or production capacity. It did not run the 42-minute Gatling gate or approve a production activation. A different verified staging release is required for the next walkthrough.
