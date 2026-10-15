# Retain evaluation phase progress

## Change

Keep an ordered history of evaluation phases on the operation page. New worker
samples update the current phase's counters; a change of phase, suite or Job
starts another entry. Returning to an earlier phase later creates another entry,
so repeated suites or variants do not erase previous work. Status polling
rebuilds the display from this history, and reopening the page reconstructs it
from retained operation logs.

The current phase is marked while its evaluation update is current. Other entries
are labelled **Recorded phase**, rather than claiming their gate passed. Counters
and stale-sample notices remain as reported, including final capture counts.
The existing live Gatling panel and report decisions are unchanged.

## Verification and next action

JavaScript syntax validation passed. A DOM fixture confirmed worker updates,
phase transitions, repeated capture phases, preserved final counters and all
entries remaining after the content is rebuilt by a status refresh. Browser
rendering has not been checked. After review and merge,
activate only when the current evaluation has finished. This changes presentation;
it does not restart evaluation or alter retained evidence.
