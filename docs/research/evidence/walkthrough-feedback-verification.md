# Walkthrough feedback verification

Source PR [#27](https://gitea.localhost:34443/elastic-agent/delivery-source/pulls/27)
passed its release and relevance checks for commit
`424bc21b0fc0aff43213e510b9f3fa7430ed3289`. The accepted baseline was build 108;
the candidate was build 109. Production remained on its existing verified release.

## Fresh API comparison

| Observation | Result |
| --- | --- |
| Catalogue | Full English ESCI catalogue, 1,215,854 products; GB/GBP lab prices |
| Query suite | 1,000 frozen queries through both exact-image APIs |
| Capture | 32.047 seconds, eight workers |
| Requests | 1,000 per API; no retries, transient failures or terminal failures |
| Coverage | 8,053 of 9,915 results per variant: 81.2204% |
| Gate | Passed under the existing temporary demo policy |
| Original receipt | Its downloaded bytes were signed; the PR head and base were checked again before publication |

The capture ran the new pacing module in a finite Kubernetes Job. It did not
replace the control Deployment. This healthy run verifies wiring and retained
diagnostics, not overload recovery in Kubernetes. The
[isolated pacing trials](evaluation-pacing.md) provide the overload evidence.

Coverage includes the already authorised, **unqualified** calibrated-model
labels. A passing demo gate does not qualify model accuracy. No new exception
or threshold reduction was issued. The source change preserves the existing
trainers rewrite; this is not a new relevance improvement claim.

## Retained identities

| Item | SHA-256 or run |
| --- | --- |
| Observation Blob | `0ac2be6aead3ffcf610e6070ea7018ca0d6569b37fd98fe253ab65ba3a224b55` |
| Signed report | `b3fffb4ac4708018267f7f5d605935e5a9d9fc6ef02f45eb107ae1063f077441` |
| Pacing module | `7c83e65cea14a1cf2f2ccca893749465cb20ed3c37389889b922794c14baa7de` |
| Candidate release CI | [Run 109](https://gitea.localhost:34443/elastic-agent/delivery-source/actions/runs/109), passed |
| Protected relevance CI | [Run 110](https://gitea.localhost:34443/elastic-agent/delivery-source/actions/runs/110), passed after evidence publication |

The observations are retained at
`datasets/0ac2be6aead3ffcf610e6070ea7018ca0d6569b37fd98fe253ab65ba3a224b55/observations.json`.
Nexus retains the report and attestation under
`variant-gates/424bc21b0fc0aff43213e510b9f3fa7430ed3289/`.

## Provider corrections

The live API check exposed two issues before activation:

- Gitea identifies workflow runs by `path`, such as `release.yaml@refs/heads/main`.
  The automatic comparator now selects that workflow rather than a `name` field
  absent from this API response. It found baseline 108 and candidate 109 in the
  real provider response.
- Preparing a comparison checkout previously called repository setup with its
  default Actions setting. Checkout preparation now only initialises local Git;
  remote settings remain owned by setup. Tests check that it makes no repository
  API mutation.

16 focused source-comparison, queue and protection tests passed, and the affected
provider/comparison modules passed Ruff. Source application tests passed 17
checks, including the pasted rewrite test after moving it out of a nested function.

New OIDC delivery clients, manual Actions submission, automatic PR capture,
required extra-suite behaviour and the Gitea setting correction still need the
[accepted runtime activation](../../plans/walkthrough-activation.md).
Their isolated checks do not substitute for that live rehearsal.

## Windows checkout bytes

The lab's gate code, merge policy and remote client now declare LF checkout
endings in `.gitattributes`. These files supply exact source Actions hash pins;
Windows line-ending conversion must not alter those pins after a fresh checkout.

With the actual `core.autocrlf=true` setting, `git checkout-index` produced LF
files for all three paths. Their bytes and SHA-256 values matched source PR #27's
published files. This verifies the packaging contract; it does not establish a
live remote Actions run. Frozen datasets and earlier evidence were unchanged.
