# Prepare blinded human reviews of ESCI gaps

Status: implemented for review. A 100-query preparation contains 754 pairs,
blank answer templates and zero reference labels. It is not a confirmed cohort.

## Intent and constraints

Make independent review of actual Search API judgement gaps practical while
category inference is prepared. Use a small command-line tool and the existing
query identity and input contracts.

- Read frozen gap inputs and their hash-bound protected-query exclusions only.
- Select whole normalised query groups before viewing reference labels or
  predictions. Exclude protected aliases and retain all pairs in selected groups.
- Give reviewers original catalogue text and request context, with opaque pair
  identities. Keep model evidence and operator mappings out of their directory.
- Create blank answers only. Preserve uncertainty, independent reviewers and
  human source provenance in the subsequent producer workflow.
- Do not create an independence reservation, bypass a research exception,
  manufacture human labels or activate a model. Add no old-data adapters.

## Acceptance

| Requirement | Result |
| --- | --- |
| Reproducible selection | Seeded whole-query order is stable under input reordering |
| Protected query aliases | Exclusions close over the existing normalised query identity |
| Reviewer blinding | Allowlisted input fields, opaque IDs and blank labels; synthetic/model auxiliary fields omitted |
| Frozen preparation | Source, audit, selection, tool and output hashes retained; existing packets cannot be overwritten |
| Current lab exercise | 100 of 944 eligible normalised query groups; 754 of 6,920 eligible pairs; six protected groups/49 pairs remain excluded |
| Honest scope | Zero labels, no confirmed reservation and no gate-eligibility change |

See [execution evidence](../research/evidence/esci-gap-review-packet.md) and
the [operator guide](../gap-review.md). Tests cover leakage, query aliases,
immutable output and invalid inputs; they do not verify a human's independence
or model accuracy.

## Next batch

Resume [category-aware cascade selection](esci-category-cascade-selection.md)
once the reviewed GPU hand-over permits it. After choosing and freezing a useful
cascade, obtain the independent human-reference reservation and sampling design
before reviewers open answers. Do not present the preparatory sample as that
approved cohort.

The [confirmation specification](esci-cascade-confirmation.md) owns required
support, uncertainty and source separation. The current missing human references
remain a separate activation requirement even if category prompts improve
experimental coverage.
