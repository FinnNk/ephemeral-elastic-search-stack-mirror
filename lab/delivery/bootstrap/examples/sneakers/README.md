# Add the sneakers rewrite

Copy these snippets into a new branch to demonstrate a query-understanding
change. The rewrite keeps `trainers` → `running shoes` and adds
`sneakers` → `running shoes`. The examples are not loaded by the application.

| Snippet | Where to paste it |
| --- | --- |
| [understand.py](understand.py) | Replace only `local_understand()` in `app/app.py` |
| [test_method.py](test_method.py) | Add the method inside `SearchContract` in `app/test_app.py`, alongside its existing methods |
| [queries.jsonl](queries.jsonl) | Create `evaluation/queries/sneakers.jsonl` with these contents |
| [selection.json](selection.json) | Replace `gate/selection.json` for this demo |

The selection example uses `ranker-a` and `ranking-change`, matching the lab
walkthrough. If your branch already selects other variants or query sets,
add the `sneakers` entry to its existing `additional_query_sets` instead of
replacing that configuration.

From the repository root, run:

```sh
docker build -t search-api-dev ./app
```

A successful build means the application tests passed. Commit the four edited
files, push the branch and open a PR. The automatic comparison reports the
standard suite, the separate `sneakers` set and combined metrics. These extra
queries are report-only; the standard suite remains required.

The mixed-case query checks case handling. The two control queries should be
unchanged. Inspect result differences, relevance and judgement coverage in the
report; the example does not promise a relevance improvement or a passing gate.

Once this rewrite is merged, copying it again makes no new change. Choose a
new rewrite for the next demo rather than reverting an earlier one.
