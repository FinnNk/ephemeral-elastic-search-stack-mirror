# Search API

A small ecommerce Search API for experimenting with query understanding and product ranking. It searches an Elasticsearch index of synthetic UK retail products and includes a simple browser page for trying queries.

This repository is part of the [ephemeral search lab](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack). It gives engineers and data scientists a place to make a change, build it, and compare its search results with a baseline before deciding whether to deploy it. The catalogue uses GBP prices; the data and evaluation examples are for the lab.

## Start here

- Read [`app/app.py`](app/app.py) to see how a search request becomes an Elasticsearch query. `understand()` handles query understanding; `query_body()` builds the query and sets the result order.
- Read [`app/variants.py`](app/variants.py) to see how named ranking settings are selected. A field boost controls how much a match in a field such as the title or brand contributes to the score.
- Read [`app/test_app.py`](app/test_app.py) for examples of expected requests and responses.

## Run the tests

You need Git and a running Docker installation. Before cloning over HTTPS, set up lab DNS and certificate trust using the [Windows, Linux and macOS workstation instructions](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/src/branch/main/docs/workstation-access.md). The recommended Windows setup creates a user-owned CA bundle once, so the clone below needs no extra certificate arguments. Browser trust is a separate step. Lab DNS also covers preview URLs without hosts-file edits. From a terminal, run:

```sh
git clone https://gitea.localhost:34443/elastic-agent/delivery-source.git
cd delivery-source
docker build -t search-api-dev ./app
```

The image build installs the Python dependencies and runs the application tests. A successful build means those tests passed. They use mocked Elasticsearch responses and local HTTP fixtures, so you do not need a running search environment for this check.

To run tests directly with Python 3.13, install the dependencies in a virtual environment, then run these commands from the repository root:

```sh
python -m pip install -r app/requirements.lock
python -m unittest discover -s app -p 'test_*.py' -v
```

## Run without the lab

For a disconnected demo, run this from the repository root with Python 3.13. On Linux and macOS, use `python3` in place of `python` if that is your Python 3.13 command:

```sh
python app/demo.py
```

Open the printed address, normally `http://127.0.0.1:8080/`, and try `running shoes`. The same browser page and API use eight synthetic products in memory. No Python packages, certificates, credentials, Elasticsearch or Kubernetes are needed. Stop with Ctrl+C; use `--port 8081` if port 8080 is occupied.

Alternatively, after building the image above:

```sh
docker run --rm -p 127.0.0.1:8080:8080 search-api-dev python demo.py --host 0.0.0.0
```

Image building and dependency installation need connectivity the first time; an existing image or the Python demo runs disconnected. The page and JSON responses identify mock data. The mock matches query tokens and field boosts, but does not reproduce Elasticsearch analysers or scoring. Use the lab for relevance comparisons and merge evidence. The normal image command remains the Elasticsearch-backed API.

## Try a search in the lab

For the walkthrough, use the deployed integration environment at
**https://lab-delivery-integration.preview.relevance.test:34443/**. After the
one-off workstation DNS and browser certificate setup, it opens directly. Each
preview has its own URL: `https://<namespace>.preview.relevance.test:34443/`.
Choose **Open search page** on a ready lab environment card.

For diagnosis or a workstation without preview DNS, use a port forward. Run this
with kubectl and the lab kubeconfig, replacing `<lab-kubeconfig>` with the absolute
path to the lab's `.lab/kubeconfig.yaml`:

```sh
kubectl --kubeconfig "<lab-kubeconfig>" -n lab-delivery-integration port-forward service/search 18088:8080
```

Keep the terminal open and visit **http://127.0.0.1:18088/** after kubectl prints
`Forwarding from 127.0.0.1:18088 -> 8080`. For a preview, substitute its namespace.
Stop with Ctrl+C when finished.

Try `running shoes`. The page calls `GET /search?q=running%20shoes`; the response includes matching product IDs, product details and total match count. The deployment supplies a frozen index, read credentials and the Elasticsearch certificate.

## Contributors guide

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

## Filter results

Open **Filter results** in the browser to select exact category, colour or material
values and price bounds in pence. Values within a field use OR; fields use AND.
The API accepts a JSON `filters` query parameter and echoes it in the response.
Unknown fields or invalid bounds return HTTP 400. Captures and load workloads
retain the same filters for every variant. See the
[filter contract](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/src/branch/main/docs/search-request.md).
