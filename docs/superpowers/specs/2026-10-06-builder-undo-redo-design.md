# Team builder: undo and redo

Date: 2026-10-06. Extends `2026-10-05-team-builder-design.md` and `2026-10-06-builder-player-compare-design.md` (whose swap relied on a second click as its undo). Front only.

## Goal

Every change an organiser makes to the draft can be undone and redone, so a misplaced drag, a re-roll or a swap costs one click.

## Design

- **Scope:** every edit of the draft, all of which go through the page's single `commit`: moves, locks, swaps, propose, re-roll, place newcomers, reset, link confirmations (one or the bulk confirm) and the team size.
- **Snapshots:** `$lib/builder/history.js` (pure, immutable) keeps `{ past, future, key }` of whole drafts. `record(history, draft, key)` remembers the draft a commit replaces and clears `future`; `undo` and `redo` return `{ draft, history }` or `null`. No copying, since a snapshot is a draft the page already holds.
- **Merging:** consecutive commits with the same `key` make one step. Only the team-size field passes one (`'perTeam'`, a commit per keystroke); any other edit, undo or redo ends the run.
- **Limit:** the latest `LIMIT = 50` steps; the oldest are dropped.
- **Lifetime:** in memory for the page visit, never saved. `load()` (the first load, « load theirs », a new roster) starts an empty history, so a snapshot of another draft or roster never comes back.
- **Saving:** undo and redo restore a snapshot through the same `show` as a commit, so they are saved by the debounced saver like any edit and show « Enregistrement… ».
- **Controls:** Undo and redo curved-arrow icon buttons (named « Annuler » and « Rétablir ») in the Teams step's toolbar (`BuilderTeams`, props `canUndo`/`canRedo`, events `undo`/`redo`), disabled when the stack is empty or the draft cannot be saved (`saveBlocked`). Cmd/Ctrl+Z undoes, Cmd/Ctrl+Shift+Z (or Ctrl+Y) redoes; the shortcut is left alone in an input, textarea, select or contenteditable, which have their own undo, and while the player sheet is open (the sheet's swap is its own undo).
- **i18n:** `builder.undo`, `.undo.hint`, `.redo`, `.redo.hint` (the hint names the shortcut).

## Tests

`history.test.js` (steps, redo cleared by a new edit, merging and its end, no merge across an undo, the limit); `page.test.js` (disabled at first, undo and redo of a proposal and a move, redo cleared, the shortcuts and the text-field and open-sheet exceptions, the team-size field as one step).

## Not done

No persistence across a reload, and no history of what the other organiser's save changed.
