# Role-check runtime preflight

The isolated owner worker passed its CPU preflight on 4 October 2026. The
128-pair survey is ready for a new scope approval and exclusive GPU window.
**No Decider2B predictions have been measured.** Qualified coverage remains
2,946/9,915 (29.71%); the 80% gate is unchanged.

## Verified preparation

| Check | Result | Scope |
| --- | --- | --- |
| Owner software checks | 137 synthetic tests passed; Ruff and formatting passed | Final registered worker, launcher and reused controls |
| Independent numerical review | 20 focused synthetic tests passed during the fix | Reject incomplete or contradictory evidence before loading the model |
| Independent launcher review | 10 mock tests passed on the final launcher | Reject an exited guardian before CPU or GPU container start |
| Independent timing review | 7 synthetic tests passed on the final worker | Count elapsed startup once; retain the absolute cutoff |
| Actual tokenizer audit | 128 development and 32 numerical inputs fit | Maximum 127 context tokens, 238 role-prompt tokens and 230 non-Exact prompt tokens |
| Actual cleanup rehearsal | Guardian stopped the CPU container at its cutoff | Both preflight containers were removed and both guardian identities exited |
| Previous window | All 12 job cleanups and the old owner exit verified | The expired A–D window is not reused; explicit handback is still required |

The numerical tests cover an earlier fix snapshot; the final owner's 137-test
suite covers its registered sources. The independent launcher and timing checks
bind the final source hashes. The [validation record](esci-role-runtime-preflight.validation.json)
keeps these test versions and receipts separate.

The audit used the pinned tokenizer and formatter in the actual isolated image.
Transformers imported Torch as a dependency; CUDA remained uninitialised.
Model weights were not mounted, and no model engine or predictions were loaded.
The independent receipt review rechecked source hashes, preserved files,
container absence and guardian PID/creation identities.

## Registered execution controls

| Control | Required behaviour |
| --- | --- |
| Numerical evidence | Exact forward/reverse receipt bindings; recompute all 32 pairs and both questions from saved probabilities; difference ≤0.00001 and zero answer/route flips |
| Launch | Check a live, unchanged guardian and absence of a completed guard result immediately before start; reject expired start/cutoff deadlines |
| Timing | Project after eight calls and every subsequent 32; use measured singleton cost ×1.25, a future-startup budget of at least 90 seconds per job and 30 seconds of host overhead per remaining job |
| Absolute bounds | At most 384 singleton calls; prediction cutoff acquisition +15 minutes, cleanup deadline +20 minutes, startup included |
| Ownership | New scope approval, explicit old handback, exact process identities, exclusive leases and a source-bound grant; broader research stays held |

The timing margins are planning assumptions. A projection that fits is not a
runtime measurement or permission to extend the deadline. Failed attempts and
their cleanup records remain preserved.

Registration SHA-256 is
`8dd23af0a8356a2ef335bd707e272f0dbe1f6a27ff2ed113e8d6f2da9dcc4c46`,
under the owner's ignored `directional-execution-05/packet/registration.json`.
The validation record binds the exact image, sources and CPU receipts.

## Next run and limits

Follow the [execution plan](../../plans/esci-role-check-execution.md) after the
new approval and handback are recorded. Use the same cached checkpoint, fixed
128-pair cohort, singleton questions and 0.90 routing policy from the
[survey proposal](../../plans/esci-exact-veto-survey.md).

- Keep the 80 existing Exact claims separate from the 48 other residuals.
- Complete numerical repeats before development scoring; retain failed runs.
- Report corrections separately from new labels and keep every new label
  experimental.
- Open no new reference cohort. Independent actual-gap human references remain
  absent; this exposed development survey cannot qualify labels for gates.

The new grant has not been acquired. No model was activated, gate exception
issued or unrelated research restarted.
