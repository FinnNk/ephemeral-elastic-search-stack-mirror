# Pass the offline relevance check

Before merging a search change, compare its lab API results with a baseline using the same saved queries and relevance labels. **Offline relevance gate** checks that report against [the merge policy](policy.json).


Strict gates exclude exploratory reports and unqualified model labels. The lab’s temporary ESCI **demo** policy allows one explicitly authorised model/source/policy combination. These model labels remain unqualified; the verdict records the human authorisation and their count. A business exception cannot admit other unqualified sources.

Application tests and builds run separately. If a PR changes only `README.md`, `gate/README.md`, or both, the relevance check passes with `evaluation_not_required`.

## Prepare your PR

1. **Choose what to evaluate.** Edit [selection.json](selection.json) to name the candidate variants and their intent. Use names from your evaluation, excluding its baseline.

   | Intent | Use it when |
   | --- | --- |
   | `ranking-change` | You intend to change the search results |
   | `preserve-results` | The release should keep the results the same, such as a dependency update |

   For example, to check that `ranker-a` preserves results:

   ```json
   {
     "kind": "variant-gate-selection",
     "schema_version": 1,
     "selected": [{"variant": "ranker-a", "intent": "preserve-results"}]
   }
   ```

2. **Push the branch and open a PR.** CI builds the exact commit; the coordinator waits for its successful receipt before comparing it with the baseline.
3. **Open the PR's comparison links.** The comment lists both storefronts, their expiry and the report. Review relevance, label coverage, changed results and RBO/Jaccard overlap.
4. **Wait for `relevance-lab/merge-gate`.** It stays pending while fresh searches run and the coordinator signs the report. The submission workflow completing is insufficient to merge.
5. **Review the outcome.** Every new commit gets a new comparison. A passing build alone cannot satisfy the gate. A recorded exception preserves the measurements and reason.

`gate/evaluation.json` names the default and baseline. Files in `configurations/`
define their ranking settings. The coordinator reads baseline settings from its
revision and candidate settings from the PR head. Both use the same frozen inputs.

## Add a query set

Add `additional_query_sets` to `selection.json` for queries specific to your
change. For example:

```json
"additional_query_sets": [
  {"name": "trainers", "path": "evaluation/queries/trainers.jsonl", "required": false}
]
```

The supplied file contains the rewrite, its case variant and two controls.
Extra sets report only by default. Their separate metrics and the combined view
are retained in the report; the standard frozen suite remains required.
An unlabelled set reports overlap and ordering, with relevance shown as unavailable.
To require an extra set, set `required` to `true` and supply a `judgements` path
to reviewed reference labels. Each required set passes independently. See the
[query-set contract](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/src/branch/main/docs/variant-evaluation.md#add-queries-for-your-change).

## Read the outcome

| Outcome | What to do |
| --- | --- |
| `evaluation_not_required` | Review the documentation; no relevance report is needed |
| `pass` | Review the report and proposed release choice |
| `decision_required` | Ask an administrator to review the bounded regression, changed results or permitted coverage gap; record a reason if accepting it |
| `approved_exception` | Review the measured results and administrator's recorded reason separately |
| `blocked` | Address the regression or insufficient label coverage; an exception cannot bypass this result |
| `invalid` | Check for missing evidence, mismatched commits/images or an incomplete report, then rerun after correcting it |

The normal policy requires 80% judged coverage. A declared low-coverage
exception is available only for `preserve-results` when every captured query
has identical ordered product IDs and total count, and both scores and coverage
match exactly. It checks results at the saved capture depth. A human
administrator must accept the disclosed gap; selecting this intent does not
approve it. Low-coverage ranking changes remain blocked. Unqualified labels outside the exact demo authorisation remain invalid.

A gate update requires review and protected policy/code pin updates after merging to its trusted target. Existing PRs also need fresh evidence for their exact commits.

For a `decision_required` result, open **Accept relevance regression** beside
the source PR report. A human lab administrator chooses the variant and records
the reason. Review and approve the resulting `delivery-state` decision PR as
its named reviewer, then run **Actions → Lab delivery → merge-exception** with
that PR number. The coordinator merges the reviewed decision and rechecks the
source gate. A direct human merge is also processed. No `kubectl` command is needed.

The decision file and PR approval remain in Git. Its signed receipt names the
report, source commit, policy, selection, variant, reviewer and decision merge
commit. An exception preserves the scores. It does not approve deployment. Source merge requires passing checks; the lab allows authors to merge their own demonstration changes. Deployment requires a separate approving reviewer.

The [variant evaluation guide](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/src/branch/main/docs/variant-evaluation.md) explains report fields and evidence publication. Synthetic fixture scores demonstrate the workflow, not real search quality.
