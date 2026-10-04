# Additional query sets

Let engineers evaluate a specific change alongside the standard frozen suite.
Keep the standard suite required; extra suites report only by default.

## Contract and constraints

- Declare named query JSONL files in `gate/selection.json`, with an explicit
  `required` flag and an optional matching judgement file.
- Read files from the exact source commit. Reject unsafe paths, duplicate suite
  names, duplicate query IDs within a suite and invalid request filters.
- Freeze the original bytes and hashes. Every suite makes fresh requests to
  every variant, including queries that appear in another suite.
- Report each suite separately and combine equally weighted query cases.
  Namespace query IDs by suite; disclose repeated request counts and weighting.
- Unlabelled suites provide result similarity and unknown coverage. Required
  suites need labels and must pass individually; combined averages cannot
  bypass a failed required suite. The scoped ESCI demo allowance applies only
  to the standard suite.

## Acceptance

An example trainers suite includes the rewrite, a case variant and unchanged
controls. Tests cover input rejection, repeated queries, combined weighting,
report-only missing labels and a failing required suite. Update the variant
guide, source gate guide and workflow diagram to match the contract.

## References

- [Feedback plan](walkthrough-feedback.md)
- [Variant evaluation](../variant-evaluation.md)
- `evaluation/capture.py`, `evaluation/offline.py`, `lab/variant_gate.py`
- `lab/delivery/bootstrap/gate/`, `lab/delivery/ci/`
