# Version a delivery release

Use a reviewed version to describe the release and compare it with its next
promotion target. Commit `VERSION` with one `MAJOR.MINOR.PATCH` value and an LF
newline. CI reads this file; manually created tags do not choose build versions.

## Choose the next version

| Change | Bump | Example |
| --- | --- | --- |
| Breaking public API change | Major | 1.2.3 Ã¢â€ â€™ 2.0.0 |
| Compatible feature or deliberate ranking behaviour change | Minor | 1.2.3 Ã¢â€ â€™ 1.3.0 |
| Compatible fix | Patch | 1.2.3 Ã¢â€ â€™ 1.2.4 |

The ranking convention is specific to this reference implementation. SemVer
describes API compatibility; a higher version does not establish better relevance.

1. Edit `VERSION` in your source PR, starting with `1.0.0` on adoption.
2. Build and review the comparison as usual. Previews receive
   `1.0.0-pr.<PR>.<run>.<attempt>`.
3. Merge the reviewed source PR. Main publication receives
   `1.0.0+build.<run>.<attempt>` and reserves the declared version.
4. Confirm the successful release and its `v1.0.0` source tag. The coordinator
   verifies the retained bundle, source tree and immutable version reservation
   before creating that tag. Automatic repository mirroring copies it to GitHub.
5. Follow the normal promotion gates, review and deployment verification.

## Identity and ordering

Nexus retains a write-once version reservation bound to the repository and the
complete Git tree. Changing any tracked file, including documentation, requires
a version bump once that version has been published. PR builds check existing
reservations without creating them. A conflicting version fails the PR build;
main publication checks again before writing its complete receipt. Empty commits and
rebuilds with the same tree can reuse the version; the tag keeps its original
commit. Build metadata distinguishes rebuilds without changing SemVer precedence.

Promotion badges compare SemVer numerically, including prerelease precedence.
They show orange for an approved older version, green for an approved newer
version, and grey for equal or unavailable ordering. Evidence and approval must
still match the exact artefact. Git ancestry is supplemental information and
the ordering fallback when either release predates version adoption. Existing
records remain unversioned; they are not assigned artificial versions.

## Recover tag publication

The coordinator checks recent successful main builds on its regular watch cycle.
Failed tag reconciliation is retried without blocking other delivery work. Check
coordinator output for `version-tag-failed` and inspect repository access and the
retained Nexus reservation. A mismatched existing tag is rejected and never moved.
Do not delete a reservation to reuse its version; publish a new reviewed version.

## Roll out the change

Merge and update the lab runtime first, then merge delivery-source. Fresh source
repositories receive the version file and CI changes from the installer template.
Existing independent labs must apply the source repository changes too; rerunning
the installer does not replace human changes in an existing repository.
