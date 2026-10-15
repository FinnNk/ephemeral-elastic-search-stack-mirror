# Focused Redis rewrite query coverage

## Change

Add a focused additional query set for every Redis rewrite paired with the
walkthrough's `esci-gb-v1` catalogue. The 18 requests cover lower-case and
title-case forms of all six aliases, five distinct rewritten targets and one
unrelated pass-through query. Preserve the sneakers set and standard mandatory
sets. This set is report only because no reviewed reference labels are supplied;
capture and inferred labels do not establish independently reviewed relevance.

Publish the query file, selection and guide in delivery-source with patch version
1.2.2. The API implementation is unchanged, so this source PR declares
`preserve-results`. Later promotion plans review the cumulative release against
each destination; the current Staging baseline still predates the Redis feature.

Keep the same file, selection example and guide section in the lab bootstrap so
fresh installations can use it. The example is available for selection without
changing the initial baseline's default query-set selection. Existing seasonal
sets cover the separate seasonal catalogues.

## Verification and next step

Check the file through the ordinary query-set freezer, verify every alias in
the pinned Redis data has both case forms and its canonical target control,
and confirm unique request IDs, GB/GBP context and report-only selection.
Run the source PR's normal build and relevance checks before requesting merge.
Do not change the current deployments, retained evidence or build 194's plan.

The source update is delivery-source PR 41, version 1.2.2. Seventeen focused
tests passed on Windows, covering the new request set, seasonal data/query
contracts and promotion query-set handling. The actual source selection also
passed the ordinary freezer with both sneakers and the new 18-query set. Source
CI and the source comparison run against its exact PR head. No promotion or Mac
execution was performed as part of this batch.

After merging the source PR, use its successful merged-source build. Start at
Integration, where the API change relative to build 194 should preserve results;
review a fresh plan including this additional set. Continue through Staging using
the cumulative intent and checks against its actual baseline. The draft plan for
build 194 cannot be reused for the replacement build.
