# Activate and rehearse relevance decisions

## Intent

Install the accepted decision flow and complete one human-reviewed bounded exception through the browser and Actions. Keep the existing production deployment unchanged during this rehearsal.

## Prerequisites and constraints

- Merge the preceding activation batch and the relevance-decision lab batch in order, then merge its matching `delivery-source` PR.
- Install an image built from accepted lab main. Update protected gate-code and delivery-client pins only after checking the source files match the accepted templates.
- Preserve existing frozen reports and Git review history. Old receipts remain historical artifacts; the current gate requires a merged Git decision reference.
- Use a fresh demonstration source PR and its own comparison. Do not reuse another source commit's report or fabricate a human approval.
- The human reviewer supplies the reason and approves the exact decision PR head. An agent may create code and fixtures; it cannot supply that decision.
- Do not merge a production proposal during this rehearsal.

## Steps and acceptance criteria

1. Verify accepted lab/source revisions and run the control deployment installer, `setup_delivery_actions.py` and `setup_relevance_gate.py` from the lab repository with its state directory configured.
2. Confirm normal source comparisons still pass and the required statuses are attached to the exact source head.
3. Produce a bounded `decision_required` comparison. If no real change produces one, use an explicitly identified disposable demonstration fixture; do not describe its scores as measured catalogue quality.
4. Open **Accept relevance regression**, check the variant and evidence, and create its decision PR. Confirm Actions identities cannot request the decision.
5. Have the named human reviewer approve the PR. Run **Lab delivery → merge-exception**. Check the merged decision file, review ID, immutable receipt and updated source gate.
6. Verify missing approval and changed source/report/policy cannot pass. Confirm a retry cannot merge or issue a different receipt for the same variant.
7. Retain an evidence record with revisions, hashes, observed results and limitations. Update the roadmap and resume the [workstation rehearsal](remote-delivery-user-check.md).

## Installed runtime

The accepted lab and source revisions are installed. The control smoke check
passed, all four containers use the accepted image, and the deployment and
state volume identities are unchanged. See the [activation evidence](../research/evidence/relevance-decision-activation.md).

The next step is the user's workstation walkthrough. A real bounded-regression
decision still needs the human's reason and review; no exception was created
during installation.

## References

- [Implementation plan](relevance-decision-records.md)
- [Decision procedure](../variant-evaluation.md#accept-a-bounded-regression)
- [Remote commands](../remote-delivery.md)
- `lab/control-runtime/install.py`, `lab/setup_delivery_actions.py`, `lab/setup_relevance_gate.py`
- `lab/relevance_decisions.py`, `lab/test_relevance_decisions.py`
