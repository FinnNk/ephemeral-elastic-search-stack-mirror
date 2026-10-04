# Run lab delivery commands

Create a preview, compare builds or propose a deployment from your workstation
or the **Lab delivery** Actions workflow. The coordinator keeps the operation
running if you close your terminal. A promotion still needs a reviewed
`delivery-state` PR before Argo CD deploys it.

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
The commands below work in PowerShell, Bash and Zsh.

| Task | Command |
| --- | --- |
| Preview build 108 | `python ci/lab_delivery.py preview --run 108` |
| Compare builds 103 and 108 | `python ci/lab_delivery.py compare --baseline-run 103 --candidate-run 108` |
| Evaluate and propose staging | `python ci/lab_delivery.py propose-promotion --target staging --run 108 --intent ranking-change` |

The build IDs are examples from the walkthrough. Choose current builds for your
change. Comparisons require the source's `gate/evaluation.json` and named files
under `configurations/`. Baseline settings come from the baseline revision;
candidate settings and additional queries come from the candidate revision.

Commands print a progress URL, then follow the operation for up to an hour.
`--no-wait` returns after submission. Retry a submission with the same `--key`
to obtain its existing operation; changing its inputs requires a new key.
A restarted coordinator marks an active operation as interrupted. Inspect its
record and the desired-state PR before resubmitting a possible promotion.

## Run from Actions

Open `delivery-source` → **Actions** → **Lab delivery** → **Run workflow**.
Select **main**, an operation and its build IDs. Promotions also need a target
and intent. The workflow submits the operation and prints its progress URL.
Its success means **submitted**, not evaluated or deployed. Follow the operation
to its report or promotion PR. Submission releases the lab's single runner so
other builds can proceed during a long evaluation.

Production proposals run the full Gatling profile. Preview and comparison
commands do not approve releases. Merge an approved deployment through the
existing [promotion procedure](delivery.md).

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

An administrator can issue a signed bounded exception using the
[decision procedure](variant-evaluation.md). After publishing that decision,
run `python ci/lab_delivery.py gate-check --pr <number> --source-sha <40-character-SHA>`.
This checks the existing signed evidence and decision; it does not claim a new
evaluation or repeat the searches.

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
