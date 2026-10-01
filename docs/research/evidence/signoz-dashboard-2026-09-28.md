# SigNoz account and dashboard: local verification

**Historical account/dashboard check — 27–28 September 2026.** Invitation expiry and dashboard IDs describe this run, not current account access. Use the [backend guide](../../observability-backend.md) and request a new invitation if needed.

Measured on 27–28 September 2026 in the Windows x64 k3d lab. The dashboard has live metric-query checks; no browser navigation or rolling seven-day verdict is claimed.

| Check | Observation |
| --- | --- |
| Separate owner identity | Agent password login returned HTTP 200 and access/refresh tokens. The invited `finn@lab.local` user is `pending_invite`, `isRoot=false`, with managed `signoz-admin` role. SMTP is off. The manual password-setting link is in ignored `.lab/secrets/signoz-owner-invite.url`; it is absent from Git and expires on 29 September 2026 at 22:58 UTC unless renewed. Activation and human login are pending. |
| Dashboard provisioning | SigNoz `v0.143.0` accepted the source-controlled `v6` dashboard at ID `01a0e51c-1043-79cb-94a8-9511cb0c665b`. Reapplying it returned the same ID. Its 12 panels include interpretation, normal search counts/ratios/budget trends and per-kind operation outcome trends. The generated JSON matched the builder output. |
| Search metric fixture | An in-cluster probe emitted two copies of fast HTTP 200 (80 ms), slow HTTP 200 (360 ms) and HTTP 502 (42 ms), with separate cumulative exports six seconds apart. The metric query's two-hour interval returned increases of eligible 3, success-good 2 and responsive-good 1. Formula results were 66.667% success, 33.333% responsiveness, −0.97 success budget remaining, −1.85 responsiveness budget remaining, 33.333× success burn and 13.333× responsiveness burn. These are interval calculations over one increment, not seven-day SLO evidence. |
| Operation query | SigNoz accepted both grouped operation success and deadline queries (HTTP 200). Deadline queries filter to operation kinds that currently emit the deadline-good counter. A synthetic data fixture with known deadline outcomes is still needed to verify their returned values. |
| Interpretation | The dashboard's text panel says that no data is unknown and fewer than 100 normal requests do not support a search percentage verdict. The current time picker controls plotted interval increases. It cannot measure collector loss by itself; collection coverage remains a separate gate. |

The user interface was not inspected: browser automation was unavailable in this session. The dashboard route and API were checked, but panel rendering, filter preservation and trace/log drill-through remain in the [next investigation batch](../../plans/signoz-connected-runtime.md). The local port-forward must be active for the owner invite and dashboard links.
