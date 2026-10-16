# Production slot network policies

## Failure and correction

Production preparation operation `c4b0b0c5199af795cfed903611d84ef6` failed while
combining active build 108 with candidate build 204. The only unequal shared
resource was `NetworkPolicy/search-boundary`: the candidate declares Redis
and OpenTelemetry egress that the older release does not.

Render each release's search boundary policy under a slot-specific name and add
that slot to its existing Pod selector. Preserve each policy's ingress, egress
and other selectors. Keep genuinely shared resources identical and include the
kind/name when a conflict occurs. Active routing and immutable release bundles
are unchanged.

Render the complete combined manifest before writing desired-state files, so a
rendering error cannot leave partially updated slot definitions. The failed
attempt had already left two generated JSON files in the coordinator checkout.
Their contents and origin were verified, preserved in a named Git stash, and
the idle checkout was returned to clean main. No deployment or evidence changed.

## Verification

- All 22 production release and production-load tests pass in locked uv.
  New cases cover different per-slot access, selectors and rule preservation,
  unchanged routing, unrelated shared conflicts and files remaining untouched
  when rendering fails.
- The proposed renderer successfully combined the actual retained build 108
  and build 204 bundles without writing desired state or deploying them. Blue's
  policy keeps DNS and Elasticsearch access; green additionally allows Redis
  and telemetry. The stable service still selects blue.
- Reviewed the delivery guide against the renderer. Deployment and network
  enforcement of the new policies have not yet been tested in the live cluster.

## Next step

Review and merge this fix, then activate the control runtime when idle. Start a
new Production preparation attempt. Review the resulting GitOps proposal before
deploying green; active Production remains blue until the later release switch.
