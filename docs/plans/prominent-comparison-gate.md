# Prominent comparison gate status

## Intent

Show the recorded merge outcome before report measurements. A passed gate must
not invite the developer to accept a regression.

## Constraints

- Read the gate from its delivery operation; preserve frozen report bytes.
- Retain owner checks and show an error if the recorded outcome cannot be loaded.
- Do not infer a gate result from metrics or change gate policy.
- Keep pass, bounded decision, blocked and accepted exception distinct.

## Acceptance criteria

| Surface | Behaviour |
| --- | --- |
| PR comment | Names the recorded gate state; offers a decision link only for `decision_required` |
| Comparison report | Shows the gate outcome at the top, before scores and coverage |
| Passed gate | Says no relevance decision is needed, including when an old decision link is opened |
| Sign-in link | Appears only for an unauthenticated API response; permission and gate states have their own messages |
| Other outcomes | Distinguishes required decision, blocked evidence and a recorded exception |
| Evidence | Fetches the existing operation separately; leaves frozen JSON unchanged |

## Verification

18 server tests and seven subtests passed; browser checks cover the four gate
states, baseline comparisons and mobile layout. Decision-page browser checks
cover pass, accepted exception, block, required decision, non-admin access,
HTTP 403 and HTTP 401. These verify presentation, not
search quality. The existing passed comparison comment on source PR 31 was
corrected without changing its evidence.

See `lab/delivery_source_comparison.py`, `lab/delivery_results.js`,
[delivery](../delivery.md) and the
[activation plan](prominent-comparison-gate-activation.md).
