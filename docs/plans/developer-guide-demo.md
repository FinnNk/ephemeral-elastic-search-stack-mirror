# Developer guide and disconnected demo

Status: implemented locally; review PRs open. Source merge evidence remains a lab evaluation task.

## Intent and constraints

- Help a new contributor clone securely, find a deployed browser page and understand the review process.
- Demonstrate API and frontend development without a running lab using a separate mock entry point.
- Keep normal deployments Elasticsearch-backed; mock results must be visibly labelled and must not enter merge evidence.
- Use the existing standard-library HTTP server and Archify diagrams rather than adding a framework or another service.
- Keep certificate instructions specific to Windows, Linux and macOS; distinguish tested commands from portability guidance.

## Acceptance

| Requirement | Local result |
| --- | --- |
| Explicit certificate acquisition, Git configuration and browser trust | Workstation guide added; Windows HTTPS Git verified; Linux/macOS guidance not executed |
| Lab URL and readiness instructions | README gives port-forward command, address and expected kubectl output |
| API/frontend demo without lab dependencies | Python demo and Docker image; HTTP search passed with Docker networking disabled |
| Same API validation, variant selection and response shaping | Existing eight application tests and one demo HTTP contract test passed |
| Startup reports the address and data source | Observed in container logs |
| Contributors guide and diagrams in delivery/evaluation guides | Added using existing reviewed Archify PNG exports |
| Source build and exact-commit gate | Commit `59a21763217205650a740fa517400a6fbfcf6417`: build run 52/job 56 passed; relevance run 53/job 57 failed without frozen evidence. Lab evaluation is still required before merge. |

## Next step

Review the reference documentation and source implementation. Before merging the source change, capture the candidate and baseline through the lab APIs, evaluate the declared `preserve-results` selection, publish exact-commit evidence and rerun the trusted relevance job. A missing or low-coverage report remains a failed gate; the disconnected mock is not a substitute. After acceptance, continue the developer walkthrough one step at a time using the lab environment.

## References

- [Workstation access](../workstation-access.md)
- [Delivery](../delivery.md) and [variant evaluation](../variant-evaluation.md)
- [Source implementation PR #13](http://127.0.0.1:31800/elastic-agent/delivery-source/pulls/13)
- `lab/search-app/demo.py`, `lab/search-app/app.py` and `lab/search-app/test_demo.py`
