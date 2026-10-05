# Internal gateway for Headlamp KServe tests

## Intent

Install the routing implementation required to exercise KServe LLM resources in
Headlamp. Use the CPU simulator rather than loading a GPU model.

## Constraints

- Envoy Gateway 1.8.1 and AI Gateway 1.1.0; checksum-pinned chart packages and upstream values.
- Existing Gateway API and inference schemas remain unchanged.
- Gateway `kserve/kserve-ingress-gateway`, class `envoy`, has a ClusterIP proxy.
- Controllers and proxy use the labelled testbed worker. Proxy limits are 1 CPU
  and 512 MiB; requests are 50m CPU and 64 MiB.
- Preserve Traefik, KServe ingress settings, serving definitions and Standard default.
- Do not create the routed simulator or start a GPU job in this batch.

## Acceptance criteria

| Check | Required result |
| --- | --- |
| Controllers | Envoy and AI Gateway deployments available |
| GatewayClass | Accepted |
| Gateway | Programmed with an internal proxy service |
| Preservation | Existing model/runtime definitions, ingress and protected schemas unchanged |
| Reproduction | Separate installer and local configuration committed for review |

Upstream addon values require an explicit read-only InferencePool role for the
Envoy controller. No broader permission is added by the local RBAC manifest.

See [testbed operations](../headlamp-testbed.md), `lab/install_headlamp_gateway.py`
and `lab/headlamp-gateway/`. Next, [verify routed plugin workflows](headlamp-testbed-validation.md).

## Verification

Installed and checked on 5 October 2026. Both controllers and the proxy are
ready; the class is Accepted and the Gateway is Programmed. A disposable CPU
probe reached the internal listener and received 404 with no matching route.
It was removed. Existing protected schemas, serving definitions, ingress
configuration and Traefik spec were unchanged; both lab judgement services
remained Ready. Routed LLM inference has not been tested.

The first preservation check assumed the k3s default Traefik name; it stopped
before changes and was corrected to the lab's ingress deployment. Envoy's initial
cache failed before the required read-only InferencePool grant was applied; it
recovered after restart. The first HTTP probe assumed a Server header that Envoy
did not return. The corrected probe checks the actual listener's HTTP status.
