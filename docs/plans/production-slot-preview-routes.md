# Browser routes for Production slots

## Problem and correction

After preparation PR #34 deployed build 204 in green, its published browser URL
returned 404. The service and API were healthy internally. The preview router
only created a rule for the stable Production hostname and service `search`.

Add blue and green host rules to the same owned Ingress when their respective
services exist, select the matching slot and expose port 8080. Each slot hostname
always targets its slot service; the stable hostname continues to target
`search`. Remove a slot rule if its service disappears or is no longer eligible.
Other namespaces retain their existing single-host behaviour.

The route writer gains GET access to the two explicitly named slot services
through its existing namespace-scoped role bindings. It receives no service list
or write permission. Fresh installation publishes the same reconciler and role.

## Verification

All nine preview-route and installer tests pass in locked uv. They cover
reconciliation, repeat submissions, route ownership, removal, invalid services,
blue/green aliases and the stable service remaining separate across an active
slot change. Diff checks pass. Live browser reachability remains to be checked
after activation; no workload, evidence or active route was changed in this batch.

## Next step

Review and merge. When idle, update the installed route writer's code and named
service permissions, then restart only the preview route reconciler. Verify the
green `/release` and storefront through HTTPS, and confirm the stable Production
service still selects blue. No repeat candidate preparation is required.
