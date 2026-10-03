# Control list navigation

## Intent

Find environments, comparisons and report queries without scanning a long
page. Keep the control interface small and preserve its existing permissions.

## Constraints

- Search and page retained metadata; do not run searches or evaluations to
  populate the lists.
- Preserve the full ready-environment choice when filtering the visible cards.
- Keep administrator and reader permissions unchanged.
- Read and write source files as UTF-8. Verify served bytes and rendered text;
  do not add runtime encoding adapters or rewrite imported catalogue data.

## Acceptance criteria

| Behaviour | Evidence |
| --- | --- |
| Environments | Active default, text search, status/catalogue filters, deterministic order and paging |
| Comparisons | Environment names, text search, mode/status/verdict filters and paging |
| Reports | Query text/ID search and paging; existing relevance/result order retained |
| Refresh | Keep current filters, page size and ready-environment selections |
| Unicode | Catalogue separators, accented query text and metric labels render correctly |
| Permissions | Reader cannot create, compare, renew or delete |
| Layout | Desktop and narrow screens remain usable without horizontal overflow |

The implementation uses the existing authorised summary responses. Filtering
and paging happen in the browser; a future deployment with a substantially
larger metadata history can add database-backed paging as a separate change.

## Verification and next batch

See [navigation evidence](../research/evidence/control-list-navigation.md),
`lab/control_lists.js`, `lab/test_control_lists.cjs` and
`lab/test_control_ui.cjs`. The next identity batch remains
[authenticated gate decisions](oidc-recorded-decisions.md).
