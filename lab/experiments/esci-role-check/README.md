# Role-check experiment

Prepare a small judgement survey using the cached Decider2B checkpoint without
an additional lab ESCI adapter. The current four-way judge makes shared Exact
errors under every category prompt. This experiment asks two separate questions:

1. Does the product itself meet the requested role and explicit requirements?
2. For a non-Exact product, is its relationship Substitute, Complement,
   Irrelevant or insufficiently supported?

The experiment can reject an existing Exact claim or add a non-Exact label.
Unsupported decisions abstain. It preserves earlier cascade decisions and
marks its own output as experimental. It supplies no qualified gate labels.

## Check the preparation

From this repository checkout in PowerShell, use the existing lab analysis
environment. These tests use synthetic pairs and an injected fake backend;
they do not load model weights or use the GPU.

```powershell
$python = 'D:\codex\Ephemeral Elasticsearch\.lab\esci-packaging\.venv\Scripts\python.exe'
& $python -m pytest lab/experiments/esci-role-check -q
& $python -m ruff check lab/experiments/esci-role-check
```

Windows is the checked host. Real-model execution requires the separate
[execution plan](../../../docs/plans/esci-role-check-execution.md); these test
commands do not obtain a GPU grant or verify a serving contract.

## Source contracts

| Source | Responsibility |
| --- | --- |
| `role_check.py` | Current-schema state rendering, singleton question calls, raw probability validation and fixed routing |
| `analyse_role_check.py` | Matched 128-pair development analysis, separate 80/48 strata, existing whole-query statistics and explicit selection support |
| Test modules | Synthetic contract and analysis checks; no real-model quality evidence |

The backend is injected by a separately authorised owner worker. There is no
model loader, GPU CLI or replacement controller here. Pin the checkpoint,
runtime, effective choice temperature, compiled inputs and complete token audit
in that worker's execution registration. No old-schema fallback or extra
four-class score mapping is supplied.

## More information

- [Survey intent and selection rules](../../../docs/plans/esci-exact-veto-survey.md)
- [Next execution and cleanup](../../../docs/plans/esci-role-check-execution.md)
- [Category results](../../../docs/research/evidence/esci-category-survey-results.md)
- [Independent cascade confirmation](../../../docs/plans/esci-cascade-confirmation.md)
