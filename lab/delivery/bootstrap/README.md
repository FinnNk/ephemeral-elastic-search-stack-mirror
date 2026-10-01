# Search API

A small ecommerce Search API for experimenting with query understanding and product ranking. It searches an Elasticsearch index of synthetic UK retail products and includes a simple browser page for trying queries.

This repository is part of the [ephemeral search lab](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack). It gives engineers and data scientists a place to make a change, build it, and compare its search results with a baseline before deciding whether to deploy it. The catalogue uses GBP prices; the data and evaluation examples are for the lab.

## Start here

- Read [`app/app.py`](app/app.py) to see how a search request becomes an Elasticsearch query. `understand()` handles query understanding; `query_body()` builds the query and sets the result order.
- Read [`app/variants.py`](app/variants.py) to see how named ranking settings are selected. A field boost controls how much a match in a field such as the title or brand contributes to the score.
- Read [`app/test_app.py`](app/test_app.py) for examples of expected requests and responses.

## Run the tests

You need Git and a running Docker installation. The local lab certificate must be trusted to clone over HTTPS. From a terminal, run:

```sh
git clone https://gitea.localhost:34443/elastic-agent/delivery-source.git
cd delivery-source
docker build -t search-api-dev ./app
```

The image build installs the Python dependencies and runs the application tests. A successful build means those tests passed. They use mocked Elasticsearch responses, so you do not need a running search environment for this check.

To run tests directly with Python 3.13, install the dependencies in a virtual environment, then run these commands from the repository root:

```sh
python -m pip install -r app/requirements.lock
python -m unittest discover -s app -p 'test_*.py' -v
```

## Try a search

Open the browser page for a deployed lab environment and try a query such as `running shoes`. The page calls `GET /search?q=running%20shoes`; the response includes the matching product IDs, product details and total match count.

Running the image by itself is not enough to search. A lab deployment supplies an existing product index, its read credentials and the Elasticsearch certificate. The [lab guide](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/src/branch/main/lab/README.md) explains how to create and access an environment.

## Make and evaluate a change

1. Create a branch, change the API or ranking settings, and run the tests.
2. Push the branch and open a pull request. **Reference release CI**, visible in Gitea's **Actions** tab, tests and builds that exact commit. It stores the image and release files in Nexus, the lab's artefact repository. The separate **Offline relevance gate** checks the evaluation evidence; changes limited to this README and `gate/README.md` receive a recorded documentation exemption.
3. Deploy the built version to a lab environment and compare it with a baseline using the same frozen products and queries. Frozen inputs are saved versions that stay the same throughout the comparison.
4. Review the changed results, relevance scores and judgement coverage. Judgements are labels indicating how relevant a product is to a query; coverage tells you how many returned products have those labels. A passing build alone does not show that ranking improved.

The lab also supports named ranking variants: alternative settings evaluated against the same inputs. One variant is always the default for requests without a selector. The evaluation chooses its baseline separately. See the [offline gate guide](gate/README.md) for the checks that can be required before a pull request is merged.

## Repository layout

| Path | Contents |
| --- | --- |
| `app/` | Search API, browser page, tests and Docker image definition |
| `chart/` | Kubernetes deployment template |
| `contracts/` | Supported Elasticsearch index definitions and index-building code |
| `ci/` | Build, release and evaluation gate scripts |
| `.github/workflows/` | Actions workflow used by the lab's Gitea runner |
| `gate/` | Selected variants and the policy used to check their evaluation |

## Further reading

- [Reference CI/CD](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/src/branch/main/docs/delivery.md): build, deployment, promotion and rollback.
- [Offline variant evaluation](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/src/branch/main/docs/variant-evaluation.md): compare ranking choices and interpret their evidence.
- [Lab architecture](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/src/branch/main/docs/prototype-design.md): how the services and frozen data fit together.
