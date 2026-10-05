# Headlamp Prometheus plugin

## Intent

Install the custom Prometheus 0.9.1-kserve.1 release for the next KServe plugin
trial. Preserve the existing KServe plugin, OIDC configuration and Kubernetes
permissions. This release replaces the official plugin with the same name.

## Acceptance

- Retain the original release archive and verify its published SHA-256.
- Mount one Prometheus plugin alongside KServe using the existing ConfigMap pattern.
- Confirm Headlamp readiness, plugin discovery and exact served asset bytes.
- Check Prometheus discovery and predictor scraping; distinguish installation
  from browser-specific configuration and chart validation.
- Commit the reproducible setup and documentation for review.

## Next

Refresh Headlamp and test the next KServe plugin release when supplied. Continue
the relevance walkthrough separately. See [plugin setup](../../lab/headlamp-plugins/README.md).
