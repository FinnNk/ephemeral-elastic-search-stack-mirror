# Documentation exemption: local verification

The source gate runs from the PR target revision. Only regular-file changes to `README.md` and `gate/README.md` qualify for an exemption. Application tests and release builds still run.

## Gitea checks

Tests used a disposable target branch at `502b7f7e8e295863fc905a4bd7a10aa86611924e`. Source main was not changed.

| Fixture | Build | Trusted relevance gate | Protected merge |
| --- | --- | --- | --- |
| [Source PR #11](http://127.0.0.1:31800/elastic-agent/delivery-source/pulls/11): README-only change | Passed (run 41, job 45) | Passed with `evaluation_not_required` (run 42, job 46) | Accepted |
| [Source PR #12](http://127.0.0.1:31800/elastic-agent/delivery-source/pulls/12): candidate replaces its classifier and workflow with a bypass | Passed (run 43, job 47) | Failed: evaluation required, frozen evidence missing (run 44, job 48) | Rejected with HTTP 405; PR remained unmerged |

The protected fixture branch required both checks and disabled administrator overrides. Both PRs had no merge conflicts. The successful merge provides a control for the rejection; Gitea's rejection message itself was generic.

The documentation verdict recorded candidate `6c0d7d2ffaeff7e5822f27763e8cca259bac005f`, the target SHA, changed paths and diff digest. The tampering verdict recorded candidate `e1b19dbab5fb2c5a35751c4f2016ea77c59bd9ee` and both changed gate paths. The candidate's replacement workflow did not run the trusted gate.

## Automated checks

Focused tests cover mixed changes, unrecognised paths, CI and policy changes, symbolic links, executable documents, code renamed to documentation, malformed diffs and a target branch that has advanced independently. Protection tests check that unaccepted source files cannot trigger protection changes and that additional checks and stronger approval requirements are retained. Existing signed-evidence tests cover behavioural verdicts and recorded exceptions.

## Activation

[Source PR #10](http://127.0.0.1:31800/elastic-agent/delivery-source/pulls/10) installs the new workflows and scripts. Its release build passed (run 40, job 44). The new target workflow will enforce main-targeted PRs after that implementation is reviewed and merged, and [main protection is installed](../../relevance-gate.md#activate-in-an-existing-lab). The initial installation has no new target-gate check because the old target does not contain it.

These checks verify the documentation decision and merge wiring. They do not replace relevance evaluation for behavioural changes or demonstrate safe execution of untrusted application PRs on the privileged lab build runner.
