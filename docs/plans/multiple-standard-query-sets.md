# Multiple standard query sets

## Scope and names

Support **Standard query sets** (one or more, all required) and **Additional
query sets** (zero or more, each Required or Report only). This batch builds on
PR #191 and uses the same independent outcomes and informational combined view.

## Implementation

The trusted lab policy owns a non-empty array of query/judgement manifest pairs
for each catalogue's standard manifest. Its first entry retains the published
standard suite. Further entries have reserved `primary-` names and must use
compatible, hash-verified catalogue/query/judgement manifests.

Source PR comparisons and promotion checks capture all configured standard sets
and source additions. Standard sets retain published label snapshots; source
additions retain missing-label resolution. Recalculation verifies and reuses
original retained labels, including the original bytes of published snapshots.

Source selections cannot shadow standard names, remove a configured standard
set or downgrade its required flag. Missing or altered groups fail validation.
Every required set is assessed independently. Reports and PR prose distinguish
the two groups. No combined score can mask a failed standard set.

Existing catalogues still have one standard set each. The implementation allows
larger groups; this batch does not invent new mandatory query data or change the
current volume of live evaluation requests.

## Review and activation

Merge PR #191 first, then this follow-up. Publish and activate the resulting
control runtime once. Rerun build 184's Integration proposal checks to include
its declared `sneakers` set, then review the new report and exact desired-state
PR head. Existing proposal #25 must not be deployed using omitted-set evidence.

To configure a larger standard group, publish compatible immutable manifests
and review a change to `primary_query_sets` in the protected lab policy. Do not
change a source selection to try to replace the standard group.

## Validation

109 affected Python tests passed in the locked uv environment on Windows.
The headless Chrome report fixture passed with multiple standard and additional
sets, separate outcomes and mobile layout. These are isolated fixtures, not live
promotion evidence. Tests cover empty/duplicate
mandatory groups, protected names, compatible manifest loading, mandatory
failures with no source additions, multiple standard sets during promotion,
unchanged snapshot reuse and browser group labels. No live workload, inference,
proposal merge or deployment is performed before acceptance.
