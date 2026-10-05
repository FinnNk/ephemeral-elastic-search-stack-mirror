# Rehearse the sneakers relevance change

## Intent

Use the copyable source examples to take a query-understanding change through
the developer workflow, one step at a time. The owner makes the changes and
reviews the results; administration stays outside the walkthrough.

## Constraints

- Preserve the existing trainers rewrite and all user edits.
- Use fresh searches, the standard required suite and report-only extra queries.
- Do not claim improved relevance from application tests or added labels.
- Use Actions and PR links for comparisons and promotions; no developer kubectl.
- Deployment remains subject to reviewed desired-state PRs and production load evidence.

## Acceptance criteria

1. The owner copies the function, test, query set and selection from `delivery-source/examples/sneakers/`.
2. Application tests pass and the PR receives current-head build/comparison evidence.
3. The report identifies the standard, sneakers and combined query sets.
4. The owner reviews relevance, result changes and judgement coverage separately.
5. Any permitted regression decision is recorded in Git before merge.
6. A merged-source build can proceed through reviewed promotion and verification.

## Further information

- [Demo snippets](../../lab/delivery/bootstrap/examples/sneakers/README.md)
- [Build and promote](../delivery.md)
- [Interpret variants and decisions](../variant-evaluation.md)
- [Judgement inference activation](judgement-inference-activation.md)
