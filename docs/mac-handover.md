# Continue the lab on a Mac

Choose the installation route, retain unfinished work and verify the code before
leaving Windows. Run Mac commands from the accepted repository root in Terminal.
Keep the original Windows lab until the Mac passes acceptance.

## Choose what to retain

| Goal | Procedure | Identities and history |
| --- | --- | --- |
| Rebuild the CPU lab and continue development | [Fresh installation](fresh-install.md) | New accounts, CA and initial releases. Git history and committed datasets come from code; existing reviews, operation history and live releases are not restored. |
| Preserve the existing running lab | [Mac preparation](mac-setup.md), then [service transfer](lab-transfer.md) | Requires consistent service backups, protected credentials and keys. Git mirrors alone are insufficient. Full Windows-to-Mac restoration has not been rehearsed. |

For a fresh installation, do not copy the Windows `.lab` directory into the new
checkout. Retain research inputs separately as described below. Do not copy
`.venv`, Windows executables, Docker VM disks or old kubeconfig endpoints.

The CPU installer excludes the larger research models and GPU testbed. It uses
the abstaining judge and committed additional judgements. Optional demo SigNoz
is a separate installation step. See the fresh guide for its corporate CA,
resource, DNS, browser trust and cleanup procedures.

## Check the code before cloning

On 19 October 2026 all five configured Gitea push mirrors reported GitHub App
`401 Bad credentials` failures. Direct GitHub checks found these stale heads:

| Repository | Accepted Gitea main | Observed GitHub main |
| --- | --- | --- |
| Lab | `1760df8a5aecb7913b410d9036f309b0361f4582` | `b63f3b52bcdac59b5f2c3867eb8cb405af2f7eb1` |
| Delivery source | `2d6c237441449eb4c278d938657ac293476420be` (1.2.6) | `a7cb12a20522904c4d0b51a21a5dd6f4a1c4d2a2` |

These are dated observations, not expected permanent heads. This documentation
change itself needs acceptance and publication before it can be cloned.

1. Follow [mirror recovery](github-mirror.md#authentication-and-recovery).
   Verify the GitHub App key, installation access and permissions. Synchronise
   each mirror after correcting authentication. A successful GitHub login by a
   developer does not repair Gitea's App credentials.
2. Compare Gitea and GitHub `main` hashes for all five repositories in the mirror
   guide. Check any unfinished branches that will be used on the Mac as well.
   Do not assume an enabled mirror or its last-update timestamp means success.
3. Clone the lab mirror after the accepted documentation revision appears:

   ```sh
   git clone https://github.com/FinnNk/ephemeral-elastic-search-stack-mirror.git
   cd ephemeral-elastic-search-stack-mirror
   git rev-parse HEAD
   ```

   Expect the accepted revision, or a later reviewed descendant. Use your own
   GitHub authentication for the private mirror; do not embed tokens in URLs.

If mirror authentication cannot be repaired before departure, use verified Git
bundles from the authoritative local repositories. For each repository, first
confirm the intended commits and branches exist locally. From its Windows
checkout, using PowerShell, choose a new output filename:

```powershell
git status --short
git branch --all
git bundle create 'D:\transfer\lab-code.bundle' --all
git bundle verify 'D:\transfer\lab-code.bundle'
Get-FileHash 'D:\transfer\lab-code.bundle' -Algorithm SHA256
```

Create the private `D:\transfer` directory first. Commit intended work before
bundling; uncommitted and ignored files are excluded. Use a distinct bundle name
for each repository and copy the recorded checksums through a trusted channel.
On the Mac, verify its checksum before cloning:

```sh
shasum -a 256 /path/to/transfer/lab-code.bundle
git clone -b main /path/to/transfer/lab-code.bundle lab
cd lab
git remote rename origin transfer-bundle
git remote add origin https://github.com/FinnNk/ephemeral-elastic-search-stack-mirror.git
```

Use the corresponding mirror URL for another repository. The bundle remains a
recovery source; ordinary development and review still belong in the lab's
Gitea. A Git bundle does not replace service backups for a full restoration.

## Retain unfinished work

The following work is separate from the accepted installation. Retain its Git
branches and research files before leaving Windows, even for a fresh install.
Do not resume old automation or judgement workers on both hosts.

| Work | Retained location and next action |
| --- | --- |
| Realistic nDCG example, lab | Branch `codex/ndcg-ranking-example`, checkpoint `487d619`. Retain the full commit and branch in a verified mirror or Git bundle. |
| Title-match Search API | Source worktree `.lab/title-match-source`, branch `codex/title-match-ranking`, checkpoint `25d15a7`, proposed version 1.3.0. Bundle this repository separately; cloning lab Git does not include it. |
| Additional title-match judgements | Shared state `.lab/experiments/title-match-judgements/shard-1` through `shard-3`. Retain all protocol, input batches, partial label outputs, progress and provenance; these ignored files are not in Git. |
| Original experiment evidence | Inventory the related `.lab/experiments` files and source worktree before choosing the archive. Preserve original captures and published-label results alongside later labels. |

Paths above are relative to the original lab checkout's shared state, not the
nested development worktree's own `.lab`. Inspect all three shards; a paused
worker does not imply its outputs are complete. Archive research material into
private storage with a file manifest and SHA-256 checksums. Check for credentials
before copying; do not upload the whole shared state to Git. Extract research
into a separate directory on the Mac, then configure new runs explicitly rather
than mixing it into a fresh installer's ownership records.

The frozen title-match experiment originally showed nDCG@10 increasing from
0.305371 to 0.308877 on published labels, with a 95% interval for the change of
[0.001628, 0.005657]. Its published-label coverage was only 28%. The next step is
to complete the paused judgement review and re-score the unchanged protocol,
retaining both results. Do not tune labels or the query selection to force an
outcome. The target was comfortably over 80% coverage, not complete coverage.

## Current capability and remaining acceptance

Lab PRs #214, #219, #220 and #221 and source PRs #44/#45 are merged. The control
runtime was activated and smoke-tested. The additional judgement loader reads
54 sneakers labels and 252 Redis labels; retained captures have 90% coverage on
both sides. New captures can have different coverage. Source 1.2.6 passed its
comparison after activation. On 19 October the user confirmed a branch preview
deployment completed.

These observations do not establish a clean current Mac installation, exact-SHA
preview acceptance or a full service-history restore. The earlier Mac CPU
installation reached verification after repairs. Repeat acceptance from the
current code without those intermediate patches.

1. Complete the chosen installation or restore procedure. Record the Mac model,
   architecture, Docker allocation and exact code/image revisions. For a fresh
   CPU lab, plan around 200 GB free disk and 40 GiB Docker memory; a 64 GB Mac is
   a practical starting point. These are allowances, not measured Mac minima.
2. Verify Control, Gitea, Headlamp and Argo CD sign-in, native DNS and HTTPS.
   Fresh installations use their new credentials and public CA. A restored lab
   must preserve its original identities.
3. Install optional demo SigNoz using the fresh guide. Confirm metrics, traces
   and correlated logs with new traffic and a matching time range. Keep its
   returned dashboard IDs; do not copy historical Windows dashboard URLs.
4. Create a branch preview, then an exact-SHA preview, inspect their pinned
   source/image/data bindings and expire a disposable preview early.
5. Run a comparison and open its report and notebook. Follow a new merged-source
   release through a reviewed check plan and promotion; check advisory outcomes,
   release names/changelog links and carried plan selections. Standard sets must
   remain mandatory. A fresh lab's build numbers differ from Windows.
6. Resume the nDCG experiment from its retained checkpoint. Optional adaptive
   warm-up and OpenCost/Headlamp integration remain follow-ups; neither is
   required to complete this installation.

Use the [roadmap](plans/roadmap.md) for remaining refactoring and qualification
work. Preserve Windows recovery data until the relevant acceptance checks pass.
