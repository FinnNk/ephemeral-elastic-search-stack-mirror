# Offline evaluation before merge

An offline evaluation sends the same saved queries to two or more search variants and scores their results against a saved set of relevance labels. A gate uses that report to check whether selected variants meet the lab's policy before their source pull request is merged.

The separate **Offline relevance gate** runs code from the protected target branch. It passes changes limited to `README.md` and `gate/README.md` with an explicit documentation exemption. Other files, mixed changes and edits to the gate itself require evaluation. The candidate cannot change its own exemption rule. Application tests and release builds still run for documentation changes.

For a behaviour change, `selection.json` names the variants to check. Each selected item names a `variant` and an `intent`: `ranking-change` allows intentional changes to results; `preserve-results` checks a release intended to keep results the same. The selection has kind `variant-gate-selection`, `schema_version: 1` and a non-empty `selected` list. It does not contain its own Git commit SHA. Removing this file cannot bypass the gate.

CI builds the exact PR commit. After evaluation evidence is published, rerun the relevance check to retrieve `variant-gates/<source SHA>/report.json`, `attestation.json` and any `approvals.json` from Nexus. The attestation is a signed record binding the report to that commit and its build receipt. `ci/variant_gate.py` checks the report, signatures, policy, judgement coverage, metric changes and changes to returned results. Missing, invalid or stale evidence fails the gate.

CI also matches the selected variant's captured image digest to the attested build receipt. A digest identifies the exact image contents. A later CI rerun can build another image digest without changing which image was evaluated.

The lab operator uses `lab/variant_gate_issue.py` in the reference repository to attest the frozen report, then `ci/variant_gate_store.py publish-evidence` to publish it to Nexus. After publication, rerun CI on the same commit. A bounded negative result may need an administrator's signed exception with a reason; `publish-approval` adds that record. The exception keeps the measured scores and the decision reason visible separately. A result blocked by policy cannot be approved this way.

The lab uses synthetic products, queries and judgements. Its fixture reports demonstrate how the checks work; their scores do not establish real search quality. Read the [variant evaluation guide](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/src/branch/main/docs/variant-evaluation.md) for the full workflow and policy.
