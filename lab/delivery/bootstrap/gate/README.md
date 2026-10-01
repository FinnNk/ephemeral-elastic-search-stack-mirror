# Pass the offline relevance check

Before merging a search change, compare its lab API results with a baseline using the same saved queries and relevance labels. **Offline relevance gate** checks that report against [the merge policy](policy.json).

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

2. **Push the branch and open a PR.** In Gitea's **Actions** tab, wait for **Reference release CI** to build that exact commit. An initial relevance-check failure is expected until its report is available.
3. **Evaluate the built image in the lab.** Use frozen inputs: saved versions of the products, queries and labels that stay unchanged during the comparison. Review relevance scores, label coverage and changed results.
4. **Publish the evidence.** Give the frozen report and build receipt to the lab operator. The operator signs and publishes them to Nexus, the artefact repository. The signed record binds the report to the exact source commit and evaluated image.
5. **Rerun Offline relevance gate on the same commit.** If you change the source commit, obtain evidence for the new commit. A passing build alone does not satisfy this check.

## Read the outcome

| Outcome | What to do |
| --- | --- |
| `evaluation_not_required` | Review the documentation; no relevance report is needed |
| `pass` | Review the report and proposed release choice |
| `decision_required` | Ask an administrator to review the bounded regression or changed results and record a reason if accepting them |
| `approved_exception` | Review the measured results and administrator's recorded reason separately |
| `blocked` | Address the regression or insufficient label coverage; an exception cannot bypass this result |
| `invalid` | Check for missing evidence, mismatched commits/images or an incomplete report, then rerun after correcting it |

An exception preserves the scores and binds the decision to the report, source commit, policy and selected variant. It does not approve deployment. Merge still requires an approving PR review and the passing build check.

The [variant evaluation guide](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/src/branch/main/docs/variant-evaluation.md) explains report fields and evidence publication. Synthetic fixture scores demonstrate the workflow, not real search quality.
