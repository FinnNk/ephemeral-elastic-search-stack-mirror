# Contribute to the search lab

Use a branch for each review batch. Commit the change, open a Gitea PR and obtain acceptance before merging to main. Gitea is the primary remote; GitHub is the offsite Git backup.

## Documentation

Authors and reviewers must follow [Technical authorship and review](docs/technical-authorship.md). Check clarity and structure alongside technical accuracy, including affected existing guides and source templates. Use the technical-documentation skill when available.

Before submitting, identify the intended reader, check the documented commands and inspect the rendered page. In the PR, name the pages reviewed and the checks performed; state untested platforms and remaining findings. Passing link checks do not establish that the instructions are usable.

## Review batches

- Keep documentation needed to understand a code change with that change.
- Separate changes to authoring policy from unrelated prose backfills where that improves review.
- Update the [roadmap](docs/plans/roadmap.md) and the next detailed plan after a completed batch.
- Keep historical evidence and frozen artefacts distinguishable from current operating instructions.
- Never include generated credentials or private keys in a commit or PR description.
