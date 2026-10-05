# Team builder: clearer wishes validation

Date: 2026-10-06. Extends `2026-10-05-team-builder-design.md` (step 1, « Demandes »). Front only.

## Problem

Step 1 lists, per player, what they wrote in « avec » and « à éviter », with the registered players the matcher suggests as chips. Nothing says the chips are guesses the organiser must confirm: a suggestion and a confirmation look alike (a plain pill that is « pressed » or not), the rule « only confirmed requests count » is one small muted line, nothing says how many requests remain, and moving on with unconfirmed suggestions says nothing.

## Goals

- A suggestion reads as a question and a confirmation as a check, on the chip and on the line.
- Clear matches stand apart from those that need a decision, and can be confirmed in one click.
- The organiser sees how far along the review is, and is told before moving on with suggestions left unconfirmed.
- The reason for a match is shown, so the organiser knows how far to trust it.

## Non-goals

- No change to the matcher (`names.js`) or to what a confirmed link does to the generator and the score.
- No auto-confirmation: a link exists only when the organiser confirms it (one at a time, or through the bulk button).
- No server change.

## Design

### States of a request line

A line is one part of a player's text (`matchNames` returns one entry per part) for one kind. Its state, from `matchNames`' own fields and the confirmed links:

| State | When | Chips | Status |
|---|---|---|---|
| `confirmed` | a candidate of the line is a confirmed link | solid green, `✓` | « Confirmé » |
| `clear` | not confirmed, `best` is set (exactly one candidate that is not a typo: a full name, a last name or a first name only one player has) | solid accent, `?` | « Correspondance sûre » |
| `choose` | not confirmed, several candidates (`confidence: 'ambiguous'`) | dashed, `?` | « À choisir » |
| `check` | not confirmed, `near` (one typo away, never proposed) | dashed, `?` | « À vérifier » |
| `none` | no candidate | none | « Aucune correspondance » |

Colour is never the only signal: solid versus dashed outline, the icon (`?` circle, `✓` circle, `–`) and the status text each carry it. The existing « Added by hand » group keeps its confirmed chips and does not count as a line.

### The reason

Under each line, a muted caption from the match's `confidence`: `exact` « Nom complet · un seul joueur », `last` « Nom de famille · un seul joueur », `first` « Prénom · un seul joueur », `ambiguous` « {n} joueurs possibles, à choisir », `near` « Orthographe proche, vérifiez que c'est bien lui ou elle », `none` the existing « Aucun joueur correspondant ». A `first` or `last` match with one candidate that is already confirmed keeps its caption.

### Counter and bulk action (top of step 1)

A line with `aria-live="polite"` (not `role="status"`: the page's save indicator is the only one and a test queries it; a bulk confirmation is still announced): « 6 demandes · 1 confirmée · 4 à examiner · 1 sans correspondance » (counts of lines: `confirmed`; `clear` + `choose` + `check`; `none`). Beside it, while at least one line is `clear`, a button « Confirmer {n} correspondances sûres » (`n` the number of `clear` lines): one click confirms every `clear` line, as one change of the draft (one save, one undo through the chips). It does not show at 0. It never touches `choose`, `check` or `none`.

### Warning before moving on

While step 1 is shown and at least one line is to examine, a note above the Next button: « {n} demandes ne sont pas confirmées et seront ignorées. » (in a polite live region that stays in the page). It does not block the step change.

### Where the logic lives

- `$lib/builder/requests.js` (new, pure): `requestRows(players)` (the rows `BuilderRequests` builds today, with `matchNames`); `lineState(match, links, player, kind)` (the five states); `reasonKey(match)`; `summarise(rows, links)` → `{ total, confirmed, review, none, clear }`; `clearLinks(rows, links)` → the `{player, kind, target}` links the bulk button adds (only `clear` lines, `target` is `match.best`).
- `BuilderRequests.svelte` uses them, renders the bar, the chips, the status and the caption, and dispatches `confirmClear` with the links; `toggle` is unchanged. A small `RequestIcon.svelte` draws the `?` / `✓` / `–` circles (inline SVG, `aria-hidden`, like the card's icons).
- `+page.svelte` handles `confirmClear` by adding the links not already present in one `commit`, and shows the warning from `summarise(requestRows(players), draft.links)`.

### i18n

New `builder.requests.*` keys in both dictionaries (parity-tested): `summary` (the counter, with plurals), `confirmClear` (plural), `state.confirmed|clear|choose|check|none`, `why.exact|last|first|ambiguous|near`, `warning` (plural). Reused: `builder.requests.noMatch` (the `none` caption), `.confirm` (the chips' accessible name, unchanged: `aria-pressed` carries the state).

## Tests

- `requests.test.js`: the five states from fixtures (a unique full name, a unique first name, a shared first name, a typo, noise), `confirmed` winning over the others, `summarise` counts, `clearLinks` (only `clear` lines, none already confirmed, never `choose`/`check`).
- `BuilderRequests.test.js`: the status text per state, the caption per confidence, the counter, the bulk button label and event (and absent at 0 clear), the confirmed chip and its pressed state, one French test.
- Page test: the bulk click confirms every clear line in one save and the counter follows; the warning shows with lines to examine and goes when none is left.

## Open items

None.
