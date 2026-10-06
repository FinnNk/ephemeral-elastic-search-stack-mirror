# Lab design system

Use the shared design system for delivery and comparison pages. Open
[the component reference](https://control.localhost:34443/design-system) to see
forms, action buttons, status badges and records together.

## Source of truth

`lab/lab-design.css` owns the font stack, colour tokens, spacing, borders,
controls, panels and responsive navigation. It uses installed system fonts;
no external font service is required. `lab/lab_shell.js` supplies the shared
navigation for older pages without changing their API calls or form handlers.
The release dashboard uses the same CSS with its existing static shell.

The saved notebook view embeds these styles so that its strict, script-free
content policy remains intact. Notebook cells remain inert. The retail Search
API page keeps its storefront layout; Kubernetes tools retain their upstream UI.
Markdown guides retain the repository’s technical authorship conventions.

## Use the components

- Use a `section` or `.panel` for a coherent group, with a descriptive heading.
- Use explicit labels for inputs. Put help and validation beside the affected
  field; preserve native required, minimum and maximum constraints.
- Use primary buttons for the next action, `.secondary` for alternatives and
  `.danger` for destructive actions. Disabled controls must have a nearby reason.
- Use `.badge` with text and `good`, `live`, `warn` or `bad` for state. Colour
  alone must never carry the meaning.
- Use `.table-wrap` around wide tables. Long evidence hashes wrap; connected
  release trees scroll inside their panel on narrow screens.
- Use a visible status message beside a submitted action. Link to the durable
  operation page rather than copying raw logs or JSON into a form.

Keyboard focus is visible. Navigation includes a skip link. Keep specialised
layout rules with the page, and add shared visual rules to the CSS rather than
copying them into new pages. The component reference is illustrative and does
not perform delivery operations.
