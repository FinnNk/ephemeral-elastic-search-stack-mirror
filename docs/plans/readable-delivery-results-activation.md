# Activate readable delivery results

## Intent

After acceptance, publish and deploy the merged control runtime, then resume
the sneakers walkthrough using the links already attached to its PR.

## Constraints

- Wait for active delivery operations to finish before runtime replacement.
- Preserve operation records, frozen reports, source identities and gate policy.
- Do not trigger a fresh evaluation merely to verify presentation.
- Use a signed-in human account; keep administrator actions outside the developer walkthrough.

## Acceptance criteria

1. An existing PR check opens readable operation progress at its original URL.
2. Its report displays standard, sneakers and combined sections with coverage separate and each variant compared with the baseline.
3. Actions operation links and retained promotion check links open readable views.
4. JSON requests and **View JSON data** return the original evidence bytes.
5. Readers cannot access another owner's operation unless their existing role permits it.

The installer and publisher are under `lab/control-runtime/`. Record the merged
commit and deployed image. Finish with the [sneakers walkthrough](sneakers-demo-walkthrough.md).
