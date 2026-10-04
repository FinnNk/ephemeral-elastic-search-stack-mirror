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

The relevance workflow uses `pull_request_target`, supported by Gitea and GitHub Actions. It runs the protected target's delivery client and queues an exact-commit comparison. It never checks out or runs candidate code. The coordinator reads the complete Git diff, classifies the change and waits for successful build receipts before capturing results.

The coordinator's `relevance_scope.py` owns the allowlist. Editing the source copy or workflow cannot grant an exemption: those paths require evaluation. Behaviour changes use signed reports, build receipts, policy and exception checks. Removing `gate/selection.json` cannot bypass evaluation.

The ordinary `pull_request` workflow still runs the candidate's tests and image build on the trusted-contributor lab runner. Signing keys stay in the coordinator. The workflow's OIDC credential can submit delivery requests but cannot administer other lab resources. Neither an exemption nor a passing evaluation approves deployment.

## Temporary ESCI demo policy

The lab retains the **80% coverage requirement** and its relevance/result-preservation rules. A human-authorised quality exception allows `demo` reports for one exact ESCI catalogue, query suite, model and acceptance policy. Other exploratory or unqualified model sources remain invalid.

Demo verdicts include the recorded authorisation and unqualified label count. A passing demo gate demonstrates the delivery workflow; it does not qualify the model’s accuracy. [Judgement resolution](judgement-resolution.md#temporary-esci-demo-labels) explains the thresholds and strict-mode restoration.

The source workflows and policy must first be accepted on main. Install the
matching reviewed coordinator and run its setup commands to verify the source
templates, pin `LAB_DELIVERY_CLIENT_SHA256` and require the coordinator status.
Candidate policy edits cannot replace the installed policy. Policy updates need
their own reviewed coordinator installation and fresh exact-commit evidence.

## Check the installed gate

On a source PR, confirm **Reference release CI**, **Offline relevance gate** and `relevance-lab/merge-gate` all pass on the current head. The workflow reports submission; the coordinator status reports the result. A README-only change records its changed paths and reason. Other changes receive fresh signed evidence automatically. Follow the PR comment's [comparison links](remote-delivery.md).

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
