# ESCI blinded gap-review preparation

Measured on 4 October 2026 on the Windows lab host. No model was called and no
reference labels were created, inspected or imported by this preparation.

| Measure | Result |
| --- | ---: |
| Frozen unresolved pairs | 6,969 |
| Protected query groups / pairs excluded | 6 / 49 |
| Eligible normalised queries / pairs | 944 / 6,920 |
| Selected whole queries / pairs | 100 / 754 |
| Reference labels created | 0 |
| Model/GPU requests | 0 |

Selection seed: `esci-blinded-gap-packet-preparation-20261004-v1`.
The ignored output is `.lab/esci-gap-review/packet-100-02/`.
Operator manifest SHA-256:
`7d95e88a713e6897186fb968e5d9e2abeb77a20b7e0563d0331a7e282bd9251e`.
The manifest binds the exact input, exclusion audit, tool and packet files.
The initial packet is retained separately; a code review identified nested-field
leakage on malicious fixtures, which was fixed before this second preparation.
No leaked fields were present in the real source metadata.

Fifteen focused software tests passed. They check protected aliases, all-pair query
sampling, input-order stability, allowlisted reviewer fields and blank answers,
UTF-8 values, duplicate/invalid input and nested-evidence rejection and refusal to overwrite packets.
Ruff passed. Document rendering and the final revision's checks are recorded in
the [validation receipt](esci-gap-review-packet.validation.json).

The packet separates the operator's original inputs/mapping from the reviewer
directory. Original title, brand, description and bullets come from ESCI;
category hierarchy comes from ESCI-S. Synthetic stock/popularity and rating/price
fields are not review evidence. Missing catalogue text remains missing.

This preparation has no independent confirmation reservation or human answers.
The gap-input exception covers isolated inference, not a new confirmation claim.
Its 100-query size does not establish the sample support or harmful-error bounds.
No model is qualified or activated: actual coverage remains **2,946/9,915
(29.71%)**, against the unchanged 80% gate.

Next: [category study and cascade selection](../../plans/esci-category-cascade-selection.md),
then an independently audited actual-gap assessment of the frozen candidate.
