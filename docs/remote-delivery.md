# Run lab delivery commands

Create a preview, compare builds or propose a deployment from your workstation
or the **Lab delivery** Actions workflow. The coordinator keeps the operation
running if you close your terminal. A promotion still needs a reviewed
`delivery-state` PR before Argo CD deploys it.

The lab's coordinator and source workflows are installed. Administrators handle
their setup; check [current status](plans/roadmap.md) for remaining validation.
Routine developer operations need no kubeconfig or cluster access.

Open the printed progress URL in a browser to see its current stage, outcome
and result links. It refreshes automatically while work is active. Report
links show tables and separate judgement coverage. **View JSON data** retains
the original machine-readable record; scripts still receive JSON by default.

## Sign in from a workstation

Use Python 3.13 from your `delivery-source` checkout. Complete the
[certificate and DNS setup](preview-access.md) first.

```powershell
$env:LAB_CA_BUNDLE = 'D:\codex\Ephemeral Elasticsearch\.lab\https-ingress\root.pem'
python ci/lab_delivery.py login
```

On Linux and macOS, use `export LAB_CA_BUNDLE=/path/to/root.pem` instead.
Open the address printed by the command and enter its code. Sign in with your
lab account. Your token is saved under `~/.relevance-lab`; it is refreshed during
long operations. Reader accounts can inspect results but cannot submit commands.

## Choose an operation

Use the successful release run's numeric ID from `/actions/runs/<id>`.
In the examples, replace `BUILD_RUN`, `BASELINE_RUN` and `PR_NUMBER` with those
values. `PR_NUMBER` for deployment is from `delivery-state`, not `delivery-source`.
The commands below work in PowerShell, Bash and Zsh.

| Task | Command |
| --- | --- |
| Preview | `python ci/lab_delivery.py preview --run BUILD_RUN` |
| Compare | `python ci/lab_delivery.py compare --baseline-run BASELINE_RUN --candidate-run BUILD_RUN` |
| Propose staging | `python ci/lab_delivery.py propose-promotion --target staging --run BUILD_RUN --intent ranking-change` |
| Merge an approved deployment | `python ci/lab_delivery.py merge-reviewed --pr PR_NUMBER` |
| Complete a reviewed relevance decision | `python ci/lab_delivery.py merge-exception --pr DECISION_PR_NUMBER` |
| Recheck staging | `python ci/lab_delivery.py verify --target staging` |
| Propose rollback | `python ci/lab_delivery.py propose-rollback --target staging --fingerprint PREVIOUS_FINGERPRINT --intent ranking-change` |

Choose current builds for your change. `PREVIOUS_FINGERPRINT` comes from the
verified deployment retained in `delivery-state/history/<target>/`. Comparisons require the source's `gate/evaluation.json` and named files
under `configurations/`. Baseline settings come from the baseline revision;
candidate settings and additional queries come from the candidate revision.

Commands print a progress URL, then follow the operation for up to an hour.
`--no-wait` returns after submission. Retry a submission with the same `--key`
to obtain its existing operation; changing its inputs requires a new key.
A restarted coordinator marks an active operation as interrupted. Inspect its
record and the desired-state PR before resubmitting a possible promotion.
For a failed comparison, inspect the error and restore the unavailable service
before submitting a new comparison with a new key. Reusing the old key returns
the recorded failure; it does not restart the operation.

## Run from Actions

Open `delivery-source` → **Actions** → **Lab delivery** → **Run workflow**.
Select **main**, an operation and its build IDs. Promotions also need a target
and intent. The workflow submits the operation and prints its progress URL.
Its success means **submitted**, not evaluated or deployed. Follow the operation
to its report or promotion PR. Submission releases the lab's single runner so
other builds can proceed during a long evaluation.

The workflow also offers `merge-reviewed`, `merge-exception`, `verify`, `propose-rollback` and
`gate-check`. Supply the relevant PR, target, source commit or previous fingerprint;
unused build fields can stay blank. Production proposals and rollbacks run the
full Gatling profile. `merge-reviewed` requires an existing, exact-head approval
from a permitted separate reviewer. It cannot create that approval.
See the [promotion procedure](delivery.md#promote-a-merged-release).

## Automatic source comparisons

Opening a source PR or pushing a commit queues a comparison for its exact head
and baseline. The coordinator waits for successful release receipts, creates
both previews, captures each selected query set freshly and publishes signed
evidence. A PR comment contains storefront, expiry, progress and report links.

The required `relevance-lab/merge-gate` status remains pending while this runs.
The submission workflow finishing is insufficient to merge. If either commit
moves during the comparison, its evidence is retained but cannot pass the current
PR. README-only changes receive a recorded exemption; application checks still run.

A report retains the original build receipt, selection, extra query/label bytes,
specification and observations by hash. Standard and required extra suites pass
independently. Report-only sets and combined scores cannot satisfy a failing gate.

A human administrator can request a bounded exception using **Accept relevance
regression** beside the source PR report. Follow the [Git decision procedure](variant-evaluation.md#accept-a-bounded-regression).
The `merge-exception` operation checks the exact human approval, merges the
decision PR, publishes its receipt and rechecks the frozen evidence. It does
not repeat the searches or approve deployment.

For a workstation alternative, sign in with `python ci/lab_delivery.py login`,
then run:

```sh
python ci/lab_delivery.py request-exception --pr SOURCE_PR_NUMBER --source-sha SOURCE_SHA --variant VARIANT --reason "Explain the measured loss and why it is acceptable."
```

Replace the source PR number, 40-character commit and variant with those shown
in the report. The printed result links to the decision PR. Actions cannot
request a human exception; it can complete a decision already approved by its
named human reviewer. `gate-check` remains available to recheck signed evidence.

## Operator setup

After the reviewed source templates are on main and the accepted control image
is installed, run these from the lab repository root:

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
python lab/setup_delivery_actions.py
python lab/setup_relevance_gate.py
```

Configure the control OIDC proxy with its accepted installer so it verifies
bearer tokens as well as browser sessions. Actions uses a separate OIDC client
restricted to delivery operations. Azure Key Vault supplies its secret and the
coordinator's signing/publishing credentials through External Secrets. Signing
keys stay out of source Actions. The API verifies token signatures, issuer,
audience and groups independently of the proxy.

The workflow syntax uses functionality shared by Gitea and GitHub Actions.
For GitHub Enterprise, configure its self-hosted runner, service addresses,
credentials and required status contexts. The coordinator's repository adapter
currently calls Gitea; replace that adapter for GitHub rather than assuming the
two providers' APIs are identical.

## If Actions reports no runner online

Ask the lab operator to check `platform/deployment/delivery-runner`. Kubernetes
allows five minutes for the runner daemon to start, then restarts a container
that is still stuck. Readiness checks verify that the daemon is running;
Gitea's runner status verifies its connection to the server.

Queued workflows start when the runner reconnects. No new commit is needed.
If a release then fails to reach the registry, follow the
[Nexus route repair](nexus.md#repair-access-after-a-docker-restart).
