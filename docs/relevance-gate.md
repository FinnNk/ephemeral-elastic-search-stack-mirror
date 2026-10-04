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

## Temporary ESCI demo policy

The lab retains the **80% coverage requirement** and its relevance/result-preservation rules. A human-authorised quality exception allows `demo` reports for one exact ESCI catalogue, query suite, model and acceptance policy. Other exploratory or unqualified model sources remain invalid.

Demo verdicts include the recorded authorisation and unqualified label count. A passing demo gate demonstrates the delivery workflow; it does not qualify the model’s accuracy. [Judgement resolution](judgement-resolution.md#temporary-esci-demo-labels) explains the thresholds and strict-mode restoration.

The source gate and policy must first be merged to its trusted target. Then update the protected `LAB_VARIANT_GATE_CODE_SHA256` and `LAB_VARIANT_POLICY_SHA256` variables and publish fresh evidence for each exact source commit. Changing candidate code or the lab runtime cannot bypass this installation step.

## Check the installed gate

On a source PR, confirm **Reference release CI** and **Offline relevance gate** both report on the current head. A README-only change should record `evaluation_not_required` with its changed paths. Any other change needs the signed evidence described in the [operator runbook](evaluation-runbook.md).

If a check is missing, inspect the Actions run and branch protection before merging. Do not treat a successful build as a relevance result.

## First installation

Fresh `setup_delivery.py` installations seed the gate and configure protection. To activate it on an older installation, first merge the reviewed gate workflow/scripts into `delivery-source` main. The setup command verifies those trusted files before changing protection.

Use PowerShell from the reference repository root with the existing retained state:

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
python lab/setup_relevance_gate.py
```

Protection requires both checks, review and an up-to-date branch; direct pushes and administrator merge overrides are disabled. Existing additional checks are retained. Update old source branches from main and rerun their checks if they still contain the previous combined workflow.

For GitHub Enterprise, require the corresponding build and `pull_request_target` relevance checks through branch protection or a ruleset. Keep the trusted target protected and the same-repository contributor restriction. Validate the check names on that installation rather than copying Gitea's status-context strings.

See the [local verification](research/evidence/documentation-relevance-gate.md) and [variant evaluation guide](variant-evaluation.md) for the report and policy contract.
