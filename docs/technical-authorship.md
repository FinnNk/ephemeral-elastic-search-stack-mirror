# Technical authorship and review

Write documentation that helps its reader understand the system or complete a task. Reviewers must check **clarity, structure and accuracy**; valid Markdown and passing software tests are not enough.

These requirements apply to people and coding agents, including agent reviewers. Use the technical-documentation skill when available. This page keeps the requirements accessible to contributors without that skill.

## Choose the reader and purpose

| Page | Start with | Keep elsewhere |
| --- | --- | --- |
| README | What the project does, who it helps and the first useful action | Detailed architecture, measurements and delivery history |
| Task guide | Outcome, prerequisites and steps | Internal implementation details that do not help the reader act |
| Operating guide | Setup, expected results, diagnosis and recovery | Chronological test logs |
| Reference | Current contracts, defaults, states and limitations | Repeated procedures owned by another guide |
| Design or plan | Intent, constraints, decisions and acceptance criteria | Unrelated implementation updates |
| Evidence record | Revision, conditions, observed results and their limits | Instructions presented as the current operating procedure |
| PR description | Problem, resulting behaviour and verification | Work diary or unsupported completion claims |

A page can serve more than one purpose when the sections are clear. Link to detail that would interrupt its main task; do not split a page merely to reduce its word count.

## Write for understanding and action

- Name Azure services by their service names. Explain Floci as the local Azure
  service emulator where setup, implementation or a limitation makes the difference relevant.
- Use plain British English, named objects and concrete verbs. Explain a necessary specialist term where the reader first needs it.
- Lead with the reader's outcome. Avoid introductions about what the diagram or document intends to explain.
- Put ordered procedures in numbered steps. Use bullets for independent points and tables for genuine choices or repeated mappings.
- Keep one main point per paragraph. Add subsections where they give readers useful entry points; do not replace dense paragraphs with equally dense table cells.
- Give commands a working directory, shell, prerequisites and complete arguments. Explain where placeholder values come from, the expected output and the next action. State supported platforms and which were actually checked.
- Use exact UI labels. Explain states and metrics alongside the decision the reader needs to make.
- Put likely failures and recovery beside the relevant step. Do not add generic warnings unrelated to the task.
- Use a diagram when relationships or workflow order are clearer visually. Explain its relevant boundaries, keep it aligned with the implementation and link to editable sources when useful.

For example, replace “CI consumes an attested immutable evidence bundle” with “After evaluation, ask the lab operator to publish the signed report for your PR commit. Rerun the relevance check; it verifies that the report used the image built from that commit.” Retain exact contract names in the reference where they are needed.

## Describe the current system

Current guides must agree with code, CLI help, configuration and observed behaviour. Distinguish active defaults, examples, proposed work and historical results.

Keep run IDs, dated measurements and migration history in plans or evidence records. Link to them from task guides. Preserve the original conditions and limitations of historical evidence; do not relabel it as a current result or erase it to make the guide shorter.

Give shared policy one owner and link to it. Keep source README templates and published copies aligned. Check affected unchanged pages for stale counts, labels, paths, states and claims.

## Use screenshots sparingly

Use an actual application screenshot when it helps the reader recognise a control or understand an output. Keep essential instructions in text and reuse a small set of useful views.

- Capture shareable demonstration data; exclude credentials, private data and irrelevant browser chrome.
- Preserve the interface and displayed results. Label synthetic fixtures, saved exports and manually selected form states.
- Add useful alt text and a short caption. Record the application revision, capture date, route, viewport, framing and any redaction with the assets.
- Inspect the image at normal document size and in the rendered guide. Recapture or remove it when the UI changes.
- A screenshot illustrates visible state; it does not establish underlying behaviour or prove a check passed.

## Review the documentation

Apply this procedure when reviewing a PR with documentation changes **or code that changes documented behaviour**:

1. **Identify the reader and task.** Read the opening and navigation. Can a new reader tell what the page is for and where to start?
2. **Check clarity and structure.** Read the complete affected sections, including unchanged surrounding text. Are terms explained, steps ordered, and choices and outcomes easy to find? Request changes for opaque prose or a missing procedure even if every sentence is technically true.
3. **Check instructions against the system.** Inspect code, CLI help or retained observations. Check shells, paths, prerequisites, placeholder sources, expected results and recovery. Run safe examples where useful; a documentation review alone does not authorise destructive live operations.
4. **Check related pages and templates.** Follow the user's reading path and the relevant cross-references. A correct new page does not excuse contradictory existing guidance.
5. **Inspect the rendered result.** Check heading hierarchy, tables, code blocks, links, anchors, Unicode and diagram readability. Generated diagrams must match their source and the stated system. Review screenshots against the actual UI when they are included.
6. **Report the result and limits.** Name the pages checked, actionable findings and verification performed. State what was not checked. Request changes when an unresolved problem prevents the intended reader from completing the task.

Automated link, spelling and formatting checks can support review. They cannot judge whether a page is clear, correctly structured or usable. Do not impose prose-length tests or claim compliance from a checklist score.

## Record changes and evidence

- Keep authoring-policy changes distinct from editorial backfills when semantic commits make the review clearer.
- Record verification for the current revision. Separate software tests, instruction checks, visual review and empirical measurements.
- Do not describe mock output as lab evaluation evidence, a passing test as improved relevance, or a local run as cloud portability proof.
- Preserve human amendments and imported attribution. Use UTF-8 when reading and writing maintained text.

See the [documentation review](reviews/documentation-2026-10-01.md) for the current findings and the [remediation plan](plans/documentation-authorship.md) for follow-up batches.
