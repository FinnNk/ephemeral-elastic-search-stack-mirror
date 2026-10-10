# Restore paired demo data and choose an expiry

Use the control UI's **Create an environment** form to select a named catalogue,
or enter **Restore data as of date**. A date selects the most recent simulated
release on or before that day. The resolved release name and content identities
are retained; subsequent changes to the selection do not alter an existing environment.

## Available demo releases

| Name | Simulated effective date | Products | Queries | Rewrite rules |
| --- | --- | ---: | ---: | ---: |
| `esci-gb-demo-2026-01` | 1 January 2026 | 8,000 | 50 | 6 |
| `esci-gb-demo-2026-02` | 1 February 2026 | 9,000 | 50 | 7 |
| `esci-gb-demo-2026-03` | 1 March 2026 | 8,500 | 50 | 7 |
| `esci-gb-demo-halloween-2026` | 1 October 2026 | 1,250 | 54 | 10 |
| `esci-gb-demo-christmas-2026` | 1 December 2026 | 1,250 | 54 | 10 |

February adds products. March removes some earlier products and adds others.
Product records and retained judgements are unchanged subsets of the original
demo release. The original full and demo catalogues remain available.

These dates describe a lab simulation. The published [ESCI product schema](https://github.com/amazon-science/esci-data/blob/main/README.md)
does not supply product introduction dates. Do not interpret these releases as
historical snapshots of Amazon's catalogue or as new independent relevance labels.

## Demonstrate a seasonal change

The event pair shares 1,000 ordinary products and replaces 250 event products:
Halloween costumes/decorations versus Christmas products. Event products are
unchanged records selected from the full ESCI catalogue by explicit title terms
and a deterministic product-ID ordering. B-prefixed IDs avoid the demo subset's
heavy concentration of ISBN books; they do not guarantee an event category.
Products whose titles match both events are excluded. The season and effective
date are simulated; title matches do not prove historical availability.

Create an environment with each named event release, or use **31 October 2026**
and **24 December 2026** in the date selector. Search for **seasonal decorations**
in both. Each pinned Redis dataset rewrites that query to its own event's
**halloween decorations** or **christmas decorations**. **Party decorations**
also changes with the event. Only Halloween has **spooky decorations**;
only Christmas has **festive decorations**.

The pair adds four identical exploratory queries to the 50-query base suite.
These curated queries have no invented relevance labels. Reports may therefore
show judgement gaps or unavailable nDCG until the resolver supplies eligible
judgements. Retained published labels keep their original values and provenance.
Use searches or separate notebook reports to explore the data difference;
release gates still require matching catalogues on both sides.

For larger sets and copy/paste gate selections, follow [seasonal query demos](seasonal-query-demos.md).

## Redis and Elasticsearch identity

Each release pairs its pinned catalogue, query suite and judgement set with an
immutable Redis rewrite dataset. The environment fingerprint includes the Redis
dataset hash and its content-addressed key. Restore checks the catalogue identity
and the seeded Redis manifest before admitting the environment.

One Redis server is shared across environments, alongside the shared Elasticsearch
cluster. Each API reads its own pinned hash. Elasticsearch indices are shared by
recipe and materialised on demand; selecting another catalogue does not create
another Elasticsearch server. Redis requests 32 MiB and limits memory to 96 MiB.
It has no PVC and reloads its small committed seed on restart.

API clients have read-only Redis permissions. A search looks up its case-folded
query once, with 100 ms connection and socket timeouts and no dependency retries.
A missing rule, unavailable Redis or a catalogue mismatch falls back to
`local_understand()` in the source API. Diagnostics use a `redis:` decision prefix
for successful external rewrites. Existing API builds without this feature retain
their previous behaviour.

Try `trainers`, `sneakers`, `earbuds` or `couch`. February adds `gym shoes`;
March adds `hoodie` and removes the external `tee` rule. A local fallback rule can
still apply after an external rule is removed.

Both sides of a release comparison must continue to use the same frozen catalogue
and judgement set. Different dated catalogues are useful for separate demonstrations;
their relevance metric differences should not be presented as search quality changes.

## Set a fixed expiry

On a ready ephemeral environment card, choose **Expiry (your local time)** and
select **Set expiry**. A fixed deadline survives searches and comparisons. The
ordinary **Extend lease** button returns an ephemeral environment to the rolling
72-hour lease. Refreshing a page never extends a lease.

A human lab administrator can also set a delivery preview's expiry. This is a
coordinator operation with a progress link and an exact preview identity check.
Integration, staging and production have no expiry editor. Expired environments
cannot be revived; create another environment instead. A stale expiry form must
be refreshed before retrying.

## Install or activate

Fresh installations include paired data preparation and shared Redis in the
catalogue stage. For an existing lab, after accepting the code and chart changes,
run these operator commands from the repository root on either Windows or macOS:

```sh
uv run --locked python lab/prepare_data_versions.py --publish
uv run --locked python lab/install_redis.py
```

Expect three monthly preparation messages, a seasonal-pair preparation message
and a final shared Redis readiness message. The first seasonal preparation scans
the retained full catalogue once; repeats verify and reuse the small outputs.
The commands use the lab's configured blob store and kubeconfig. They retain
immutable objects and do not rewrite an existing release's data.

Update the control runtime using [the runtime installation guide](control-runtime.md).
Merge the environment-state chart change before creating new ephemeral environments.
Merge the delivery-source extension and let its normal CI build publish the new API.
Existing deployments are not automatically rebound to another dataset.

## Verification

Focused tests cover stale lease edits, protected targets, date selection, unchanged
subset labels and rejection of mismatched catalogue/Redis identities. The optional
real Redis test creates its own disposable Docker container and removes it:

```sh
LAB_VERIFY_REDIS=1 PYTHONPATH=lab uv run --locked python -m unittest lab.test_redis_runtime
```

On PowerShell, set those environment variables with `$env:LAB_VERIFY_REDIS='1'`
and `$env:PYTHONPATH='lab'` before running the same Python command. This test checks
the actual seed command, read-only permissions, successful lookup and offline fallback.
It does not deploy or stop the lab's Redis server.
