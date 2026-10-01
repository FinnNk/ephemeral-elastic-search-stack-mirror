# Documentation relevance gate

Status: implemented and verified locally; source and reference changes await acceptance.

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
| Main requires both checks after reviewed installation | Pending acceptance and activation |

## Next batch: activation and README walkthrough

After the source implementation and reference PRs are accepted:

1. Install the accepted protection with `python lab/setup_relevance_gate.py` from the reference checkout using its existing `.lab` state directory.
2. Rebase the existing source README PR onto the updated source main, preserving its documentation changes and removing the old workflow from its branch history.
3. Confirm the current commit has successful build and trusted relevance checks; the latter must record `evaluation_not_required` and the two allowed paths.
4. Ask for acceptance of the README PR, then resume the developer walkthrough one step at a time.

Main must remain free of merge commits. No source main update or exemption activation is performed before review acceptance. The initial workflow installation requires explicit review because the previous target cannot run the new workflow.

## References

- [Gate behaviour and activation](../relevance-gate.md)
- [Local verification](../research/evidence/documentation-relevance-gate.md)
- [Signed evidence contract](../variant-evaluation.md)
- `lab/delivery/workflows/relevance.yaml`, `lab/delivery/ci/relevance_scope.py` and `lab/setup_relevance_gate.py`
