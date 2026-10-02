# Azure service terminology

Complete for review in the documentation branch.

## Intent

Describe Azure Blob Storage and Azure Key Vault by their service names. Explain
Floci as the local Azure service emulator where the implementation matters to the
reader, without implying that it reproduces every Azure feature.

## Scope and acceptance

| Work | Acceptance |
| --- | --- |
| Repository overview and current guides | Introduce the emulator once; use Azure names for ordinary data and secret workflows |
| Local operation and cloud boundaries | Retain Floci-specific endpoints, persistence, ESO provider and identity/snapshot limitations |
| Design and C4 diagrams | Use Azure service labels; identify Floci in local deployment; regenerate affected diagrams |
| Authorship guidance | Give future authors the same service/emulator naming rule |
| Review | Check context and links, render representative pages and inspect changed C4 views; retain historical evidence and imported text |

This changes documentation and diagram labels only. Commands, service identifiers,
configuration and APIs retain their existing names and behaviour. Historical
measurements continue to identify the service actually tested.

## Further information

- [Technical authorship](../technical-authorship.md).
- [Secrets operation and emulator limits](../keyvault-secrets.md).
- [Azure boundary](../prototype-design.md#azure-boundary).
- [Diagram sources and rebuild procedure](../diagrams/README.md#rebuild).

The next detailed implementation plan remains
[canonical HTTPS control sessions](reference-https-control-session.md).
