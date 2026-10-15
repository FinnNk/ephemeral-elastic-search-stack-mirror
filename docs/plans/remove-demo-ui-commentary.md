# Remove demo-specific commentary from review screens

The user wants the tooling's interface to work equally for demonstration and
other data. Remove blanket commentary about authorised demo labels, unqualified
model accuracy, exploratory scores and the local simulation from report views,
comparison coverage text, release dashboards and generated promotion PR prose.

Retain measured coverage, label-source counts, gate outcomes, unavailable-score
reasons, statistical-method explanations and all underlying provenance and
authorisation fields. This changes presentation only; it neither changes gate
rules nor reclassifies evidence or model labels.

## Verification and next step

Run description unit fixtures and the report/dashboard browser fixtures. Assert
that the removed commentary is absent for demo-labelled reports while metrics,
coverage, missing-data explanations and normal navigation still render.

This batch follows the pending version/SHA batch #188. Merge that batch first,
then this one. After acceptance, activate the combined UI and update proposal
#25's generated prose, preserving human edits and all evidence/deployment values.
Do not merge or deploy the proposal.
