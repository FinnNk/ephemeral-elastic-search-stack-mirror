# Headlamp cluster UI

## Intent and constraints

Give lab operators a browser view of workloads, events and logs. Reuse local
HTTPS, DNS and the existing CA. Keep Argo CD as the deployment owner. Use an
expiring human token with an identity separate from the Headlamp Pod; do not add
an identity provider or persistent token Secret.

## Acceptance and evidence

- Pinned upstream chart 0.45.0 and multi-architecture image digest installed in `lab-headlamp`.
- Pod ready; native DNS resolves to loopback; HTTPS validates against the existing CA.
- Anonymous namespace requests return 401; an owner token returns a namespace list.
- Headlamp Pod identity cannot list Pods across namespaces; human owner can.
- Access instructions and local deployment diagram updated.

These checks passed locally on 3 October 2026. Apple silicon remains untested.
See [installation and login](../headlamp.md), [HTTPS ingress](../https-ingress.md)
and [local deployment](../diagrams/rendered/05-local.svg).

## Next batch

Complete [independent label quality](esci-label-quality.md) before considering
model activation. Numerical serving parity is qualified; source-label quality
and judged coverage remain separate acceptance steps. Coordinate any GPU window
with the research owner and retain historical evidence.
