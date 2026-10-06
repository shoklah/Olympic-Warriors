# Team builder: ignoring requests

Date: 2026-10-06. Extends `2026-10-06-builder-requests-clarity-design.md`. Needs a server change (one draft key).

## Goal

On the Requests step an organiser can set a written request aside, so it no longer shows on the cards of the Teams step and stops counting as « to review ».

## Design

- **Unit:** one written part of a player's `team_with` or `team_avoid` text, as `splitNames` writes it: the same unit as a line on the Requests step.
- **Storage:** `draft.ignored = [{ player, kind, text }]`, in the shared draft next to `links`, so organisers see the same cards, it survives a reload and it goes through the same saver, stale check and undo history. `validate_draft` returns six keys; `ignored` is optional (a draft saved before it validates), at most 400 entries, each a known player, a kind (`with` or `avoid`) and a non-blank text of at most 500 characters, duplicates dropped; errors `invalid_draft`, `unknown_player`, `too_many_ignored`. The server deploys before the front.
- **Requests step:** an « Ignorer » button on every line (named « Ignorer « Emma » »). An ignored line is struck through, labelled « Ignorée », captioned « Ignorée : n'apparaît sur aucune carte », has no candidate chips and offers « Ne plus ignorer ». `lineState` answers `ignored` first, `summarise` counts it apart (`ignored`), so it is in neither confirmed, to review, no match nor clear: it does not hold back « Tout est confirmé » and the bulk confirm skips it. The status card gets an « N ignorées » chip. « À examiner seulement » hides it like a confirmed line, and a line ignored while the filter is on stays in view until the filter is switched off and on (as for confirming).
- **Confirmed links:** ignoring a line removes the confirmed links of that line's candidates for that player and kind, in the same save; taking it back does not restore them.
- **Teams step:** the cards' notes read `shownText(player, kind, ignored)`: the text as written when nothing of that player and kind is ignored, else the remaining parts joined by commas, and no note when none is left.
- **Roster changes:** `reconcile` drops entries of players who left and reads a missing key as empty.

## Not done

An ignored part is matched on its wording: if the player edits their registration text, the line comes back. No « ignore the whole answer » shortcut.

## Tests

Server: `test_builder.py` (kept, deduplicated, optional, each refusal, the cap). Front: `requests.test.js` (`ignored` state, counts, the bulk confirm, `shownText`), `BuilderRequests.test.js` (the button and its event, the greyed line, the count, filter and bulk confirm, French), `page.test.js` (the cards' notes, the link dropped, undo, the saved document, an old draft and a departed player).
