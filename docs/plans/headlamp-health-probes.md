# Headlamp availability repair

## Observed failure

On 6 October 2026, Headlamp intermittently showed `no available server` at its
public HTTPS URL. Kubernetes recorded repeated one-second readiness timeouts
and liveness restarts. The previous container exited cleanly after receiving a
shutdown signal; there was no reported out-of-memory termination.

At inspection, Headlamp used 13 millicores and 11 MiB, while its shared worker
reported 95% memory usage. The public URL had already recovered and returned
HTTP 200 in about 60 ms. Worker pressure is consistent with transient delays,
but these observations do not prove the cause of every timeout.

## Repair

The pinned chart supports probe settings. Both timeouts are now five seconds,
with initial delays of five seconds for readiness and fifteen for liveness.
Readiness retains three consecutive failures; liveness allows six before
restarting the process. Neither probe is disabled.

The runtime correction used Helm with retained values and the installed plugin
annotations. The first upgrade encountered ownership of a manually patched
plugin annotation; retrying with its current value succeeded at Helm revision
14. OIDC, image version, plugins, resource limits and ingress remain unchanged.
The source values preserve the correction on later reconciliation.

## Verification and next action

The replacement Pod became ready on the server worker with zero restarts.
Twelve public HTTPS requests over roughly a minute returned HTTP 200 in 10–17 ms.
The deployed probes, plugin hashes and ready service endpoint were checked after
rollout. This is a short recovery check, not evidence
of long-term availability or a new OIDC login test.

The source batch is merged. Next: watch for fresh probe failures during the
next lab evaluation. If the issue recurs, measure worker pressure and Pod
response times before changing resources or scheduling.
