# Activate prominent comparison gate status

After acceptance, use the [runtime update procedure](../control-runtime.md#update-an-existing-runtime)
when delivery operations are idle. Preserve the installed baseline and frozen evidence.

1. Publish the merged runtime and verify rollout and smoke checks.
2. Open source PR 31's latest completed comparison report while signed in.
3. Confirm its top status agrees with the operation's gate and the PR check.
4. For a passed gate, confirm there is no acceptance link. Correct any existing
   bot comment from the previous runtime using its recorded operation outcome.
5. Open an old decision link for a passed gate. Confirm it says no decision is
   needed and offers no sign-in link to an already authenticated reader.
6. Resume the walkthrough; no new comparison is needed to check presentation.

Do not manufacture a failing comparison to verify the UI: automated fixtures
cover required decisions, blocks and recorded exceptions.
