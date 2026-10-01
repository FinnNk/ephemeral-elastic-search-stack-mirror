# Documentation D4: design and navigation

## Intent

Make the design describe the current reference shape and its boundaries. Give current status one owner and keep diagrams, contracts and entry points consistent.

## Constraints

- Follow the [authorship guidance](../technical-authorship.md); retain quantitative targets, assumptions and evidence limits.
- Do not infer formal ADR acceptance from code merges, or external validation from local installation.
- Preserve editable diagram sources. Regenerate visuals only when their represented relationships change.
- Retain historical decisions and measurements through links rather than development chronology in current guides.

## Work

1. Read the design end to end. Separate implemented local topology, Azure migration boundaries and remaining proposals; restructure dense sections using short paragraphs, tables and ordered workflows.
2. Align N-way variants, required default, independent baseline, pooled labels, notebooks and release decisions with the current contracts.
3. Review diagram explanations and gallery groupings. Check counts, sources and terminology against render configuration.
4. Reconcile roadmap implementation status with accepted Gitea PRs and retain open measurement/integration gates.
5. Review the plan and ADR indexes. Make their ownership and formal acceptance limits explicit.
6. Check related anchors and render the principal reading path. Record the remaining historical-record review as D5.

## Acceptance criteria

- Readers can distinguish implemented features, research candidates and unverified deployment targets.
- Current contracts and diagram explanations agree; navigation reaches their owners.
- Quantitative targets remain visible and provisional; dated results retain their scope.
- Status changes have repository/PR evidence; ADR decisions remain with their owner.
- Complete affected sections receive a clarity/structure review, not just link checks.

## Sources

[Design](../prototype-design.md), [diagram guide](../diagrams/README.md), [roadmap](roadmap.md), [plan index](README.md), [ADR index](../adr/README.md), [review](../reviews/documentation-2026-10-01.md), current source/contract guides and diagram renderer.

Complete the batch with a PR, roadmap update and detailed D5 historical/final review plan.
