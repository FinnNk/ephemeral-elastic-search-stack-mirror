# Automatic preview URLs

## Intent

Open any search environment at a stable HTTPS URL without a port forward or
per-environment workstation changes. Serve the existing platform names through
the same local DNS service, removing the need for hosts-file entries.

## Design and constraints

- CoreDNS in `lab-ingress` serves the fixed `.localhost` names and
  `*.preview.relevance.test`, mapping them to IPv4 loopback.
- Workstation domain-specific resolver settings direct only lab queries to it.
  Windows uses NRPT rules; macOS uses resolver files. Other DNS remains separate.
- A small routing reconciler discovers `search` services in namespaces labelled
  `lab=search-spike`, creates namespace-owned Ingress and NetworkPolicy resources,
  and removes its routes when services disappear. Namespace deletion removes them.
  It lists namespaces globally; per-search-namespace RoleBindings grant routing
  and service access. It cannot create routes in unrelated namespaces.
- Traefik's default TLS certificate includes the wildcard. The existing CA stays
  in place; the private key remains in `lab-ingress` for preview routing.
- Search releases, indexes and comparison fingerprints do not change. Routing is
  platform infrastructure, separate from frozen search definitions.
- Preview search pages are unauthenticated, like the existing port-forward pages;
  DNS and HTTPS listen only on the lab host. This is not LAN exposure.

## Acceptance criteria

1. Fixed and previously unseen preview names resolve over UDP and TCP DNS.
2. Two disposable previews route to different services through verified TLS.
3. Removing a service removes its route; namespace deletion leaves no route.
4. The reconciler ignores unlabelled namespaces and refuses to adopt foreign
   resources. Repeated reconciliation is stable and resumes after restart.
5. A ready environment card offers **Open search page**. Failed/deleted cards do not.
6. Instructions cover setup, expected results, stopping DNS, resolver removal and
   platform limitations. No hosts edits or public DNS dependency are required.

## Verification and references

Record local results in [preview URL evidence](../research/evidence/automatic-preview-urls.md).
Administrator-only Windows configuration and native macOS/Linux checks must be
reported separately from direct DNS and ingress checks.

- [Workstation access](../workstation-access.md)
- [HTTPS ingress](../https-ingress.md)
- [Environment workflow](../../lab/README.md)
- [CoreDNS template plugin](https://coredns.io/plugins/template/)
- [Windows domain-specific DNS rules](https://learn.microsoft.com/en-us/powershell/module/dnsclient/add-dnsclientnrptrule)

Next implementation batch: [canonical HTTPS control sessions](reference-https-control-session.md).

## Local status

Implemented and deployed for review. Direct UDP/TCP DNS, two isolated HTTPS
fixture routes, service/namespace cleanup, scoped RBAC and the real integration
Search API health check passed. The updated multi-platform control image passed
its installed smoke check. Source README PR #17 passed its build and relevance
checks. The user installed Windows resolver rules successfully; subsequent native DNS,
HTTPS verification and Git access passed. macOS/Linux workstation integration
has not been executed.
