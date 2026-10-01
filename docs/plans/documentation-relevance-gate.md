# Documentation relevance gate

Status: accepted and activated on source main. README PR #9 has successful build and relevance checks on its rebased commit; it is merged to source main.

## Intent and constraints

- Allow introductory documentation to merge without creating artificial relevance evidence.
- Keep application tests and release builds for every source PR.
- Exempt only regular-file changes to `README.md` and `gate/README.md`.
- Require the existing signed, exact-commit evidence for all other changes.
- Run the decision from the trusted target revision; candidate gate edits cannot exempt themselves.
- Use Actions features shared by Gitea and GitHub, without compatibility paths for the old combined workflow.

## Acceptance criteria

| Criterion | Result |
| --- | --- |
| README-only PR passes without retrieving relevance evidence | Verified in Gitea |
| Mixed, unknown, executable, symbolic-link and malformed changes cannot receive the exemption | Verified by focused tests |
| Candidate workflow and classifier edits cannot bypass the target gate | Verified in Gitea |
| Both test PRs still build successfully | Verified in Gitea |
| Required gate blocks a failed PR and permits a passing one | Verified on the protected disposable branch |
| Installer refuses unaccepted source files and retains stronger existing requirements | Verified by focused tests |
| Existing behavioural and signed-exception checks still pass | Nine existing verifier tests passed |
| Main requires both checks after reviewed installation | Installed and read back; both checks passed on README PR #9 |

## Next step: README approval and developer walkthrough

The source implementation and reference PRs are merged. Main protection is installed, and README PR #9 is rebased onto the accepted source main. Build run 47 and relevance run 48 passed on commit `e6e9852ce89a4e215d5e18d99f32d5decf58268a`; the relevance verdict records only the two allowed README paths.

README PR #9 is merged to source main as `e3d820e4a6cc4521571378be3857c23782ca41ef`. Resume the developer walkthrough one step at a time: open the Search API README, identify its first local test command and explain the expected result before running it together.

## References

- [Gate behaviour and activation](../relevance-gate.md)
- [Local verification](../research/evidence/documentation-relevance-gate.md)
- [Signed evidence contract](../variant-evaluation.md)
- `lab/delivery/workflows/relevance.yaml`, `lab/delivery/ci/relevance_scope.py` and `lab/setup_relevance_gate.py`
