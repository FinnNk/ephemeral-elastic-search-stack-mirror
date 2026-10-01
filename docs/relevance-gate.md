# When a source change needs relevance evaluation

Every Search API pull request runs application tests and builds a release. Its separate **Offline relevance gate** decides whether it also needs a frozen evaluation report.

| Change | Relevance check |
| --- | --- |
| Only `README.md`, `gate/README.md`, or both | Passes with `evaluation_not_required`; the log records the files and reason |
| Any other file, including API code, dependencies, index definitions, deployment settings, CI code or gate policy | Requires fresh evidence for the exact source commit |
| Documentation mixed with another change | Requires fresh evidence |
| Empty, incomplete or malformed change information | Cannot receive the documentation exemption |

The allowlist names two exact paths. It does not exempt whole directories or infer safety from a `.md` extension. A change from a regular document to a symbolic link or executable also requires evaluation. Git compares the PR head with its common ancestor with the target branch and disables rename detection so a removed code file cannot disappear behind a renamed document.

## Where the decision runs

The relevance workflow uses `pull_request_target`, supported by Gitea and GitHub Actions. The workflow and classifier come from the target commit. The job fetches the candidate commit to inspect its diff and selected-variant JSON; it never checks out or runs candidate code. The trusted files and candidate inputs are mounted read-only for the gate process.

The target's `ci/relevance_scope.py` owns the allowlist. A candidate editing that classifier or the workflow cannot grant itself an exemption: the target version still runs, and those edits require evaluation. Behaviour changes use the existing signed report, build receipt, policy and exception checks. Removing `gate/selection.json` cannot bypass evaluation.

The ordinary `pull_request` workflow still runs the candidate's tests and image build on the trusted-contributor lab runner. The relevance workflow holds the evaluation signing keys separately. Neither an exemption nor a passing evaluation approves a deployment.

## Activate in an existing lab

1. Merge the reviewed source PR containing `.github/workflows/relevance.yaml`, the updated release workflow and the gate scripts into `delivery-source` main. This first installation needs an explicit review because the new target workflow is not yet on main.
2. From the merged reference implementation's repository root in PowerShell, run:

   ```powershell
   $env:LAB_STATE_DIR = (Resolve-Path .lab).Path
   python lab/setup_relevance_gate.py
   ```

   The command checks that source main contains the accepted gate files before changing protection. It requires both Actions checks, an approval and an up-to-date branch; direct pushes and administrator merge overrides are disabled. Existing additional check requirements are retained. A fresh `setup_delivery.py` installation applies this protection after seeding the source.
3. Update existing source PR branches from main and rerun their checks. Older PR branches may still contain the previous combined build-and-gate workflow. Confirm both the build and relevance checks appear on the current PR commit before merging.

For GitHub Enterprise, require the corresponding build and `pull_request_target` relevance checks through branch protection or a ruleset. Keep the trusted target protected and the same-repository contributor restriction. Validate the check names on that installation rather than copying Gitea's status-context strings.

See the [local verification](research/evidence/documentation-relevance-gate.md) and [variant evaluation guide](variant-evaluation.md) for the report and policy contract.
