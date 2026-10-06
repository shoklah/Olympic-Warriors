# Team builder: compare two players and swap them

Date: 2026-10-06. Extends `2026-10-06-builder-player-preview-design.md` (the `PlayerSheet`) and `2026-10-05-team-builder-design.md`. Front only.

## Goal

From a player's sheet, an organiser can put a second player beside them, read both profiles on one table, see what swapping them would do to the draft, and swap them in one click. Today the sheet shows one profile and a swap takes two drags.

## Non-goals

- No server change: the roster payload already carries everything the table needs.
- No suggestions of who to swap with (a "best swap" finder is its own feature; the picker lists everyone).
- No general undo: the swap is its own undo (see Swap).
- No compare of more than two players, and no wishes (`team_with` / `team_avoid`) in the table; the cards show them.

## Design

### Entry (`PlayerSheet.svelte`)

A « Comparer avec… » button (`builder.compare.open`) in the sheet opens a picker; choosing a player puts the sheet in compare mode with that player as B (the sheet's player is A). The picker is a search field over a list of every other player in the roster, alphabetical by last then first name, each row showing the name, the team (`builder.team`, or `builder.preview.tray`) and the overall rating. Typing filters by name, accent-insensitively, with the same normalisation as `$lib/builder/names.js`. Compare mode has a « Changer » button back to the picker and a « Fermer la comparaison » button back to the single profile. The sheet's own Escape, focus trap and focus return are unchanged; Escape inside the picker closes the picker first.

The page keeps one extra value next to `preview`: `compareId` (null when not comparing), reset to null when the sheet closes, when A changes, and when B leaves the roster.

### Butterfly table (compare mode)

One table at every width, replacing the profile body (the sheet's header, summary and sports keep their place, doubled):

1. Header row: A's name on the left, B's on the right, each with its team or « En attente ».
2. Summary rows: overall rating, global level and frequency, A's value on the left, B's on the right, with the label in the middle.
3. One row per edition skill, in `skills` order: A's bar growing leftwards from the centre, the skill name in the middle, B's bar growing rightwards, each value beside its bar. An estimated value (missing skill) is dimmed and marked « estimé », as in the single profile. The higher side of a row gets a small `+n` marker (none on a tie). The marker is text, so it does not rest on colour.
4. « Profil incomplet » under a name whose profile has an estimated part.
5. Sports, one list under each name (`sport · level`), « Aucun sport » when empty.

Both profiles come from `playerProfile` (`$lib/builder/profile.js`), so the table, the single sheet and the scorer agree on every fallback. The table is a real `<table>` with a header row naming the two players, so a screen reader reads each row as skill, A, B; the bars are `aria-hidden` and the values are text.

### Swap

A « Échanger » button (`builder.compare.swap`) sits under the table. The sheet dispatches `swap` with `{ a, b }`; the page applies it in one draft update (`swapPlayers(draft, a, b)` in `$lib/builder/plan.js`, pure) and saves once. Placement rules:

| A | B | Swap |
|---|---|---|
| team X | team Y | each takes the other's team |
| team X | tray | B takes A's team, A goes to the tray |
| tray | team Y | A takes B's team, B goes to the tray |
| tray | tray | disabled |
| team X | team X | disabled |

A swap is disabled, with a one-line reason shown under the button and tied to it with `aria-describedby`, when:

- either player is locked (`builder.compare.locked`: « Un joueur verrouillé ne peut pas être échangé »);
- both are in the same team (`builder.compare.sameTeam`);
- both are in the tray, which includes the whole draft before any team is proposed (`builder.compare.bothTray`);
- the draft cannot be edited (the stale or applying state that already disables the cards' moves).

`swapPlayers` replaces each id by the other in place, so a player takes the other's slot in the team's list, and leaves `locked` as it is (a swap never runs with a lock, so it has none to drop). After a swap the sheet stays open on the same pair with their placements updated (`previewTeam` and B's team are derived from the draft, so they follow), so a second click on « Échanger » reverses it exactly. That is the only undo.

### Swap preview

Shown under the table only while the swap is enabled. It runs the page's scorer on the swapped draft without committing it: `scorer(teamIds)` for the current teams and for the teams `swapPlayers` would give, both through the existing `makeScorer`. It prints:

- one line per team the swap touches (one for a team and tray swap, two otherwise): `builder.compare.average`, « Équipe 2 : 6,4 → 6,7 », and a word, « mieux » or « moins bien », by the direction of the average;
- one line for the draft's total of unmet wishes, `builder.compare.unmet`, « Souhaits non satisfaits : 5 → 3 », with « mieux » for fewer and « moins bien » for more.

An unchanged value prints « inchangé ». The words always accompany any colour. The scorer's total score is not shown, and the tray gets no line. The line is `aria-live="polite"` so a swap's new "before → after" is read out once; it must not use `role="status"`, which the save indicator holds alone.

### Pure logic

- `$lib/builder/plan.js`: `swapPlayers(draft, a, b)` returns the new draft, or `null` when the swap is not allowed (the same rules as the table above, so the sheet and the page cannot disagree). The sheet asks it for the reason through `swapBlock(draft, a, b)`, returning `null` or `'locked' | 'sameTeam' | 'bothTray'`.
- `$lib/builder/compare.js` (new): `compareProfiles(a, b, skills, locale)` returns the rows (`{ identifier, name, a, b, lead }` with `lead` `'a'`, `'b'` or `null` and `delta`) and the summary rows, built from two `playerProfile`s. `swapPreview(draft, a, b, scorer, byId)` returns `{ teams: [{ index, before, after }], unmet: { before, after } }` or `null` when the swap is blocked.

### i18n

New keys in `fr.js` and `en.js` (parity-tested): `builder.compare.open`, `.pick`, `.search`, `.change`, `.close`, `.swap`, `.locked`, `.sameTeam`, `.bothTray`, `.average`, `.unmet`, `.better`, `.worse`, `.same`, `.noResults`. Reused: `builder.team`, `builder.preview.*`, `builder.incomplete`.

## Tests

- `plan.test.js`: `swapPlayers` for team vs team, team vs tray both ways, in-place slots, and `null` for each blocked case; `swapBlock` reasons and their order; a second swap restores the draft.
- `compare.test.js`: rows and `lead`/`delta` with a tie, an estimated value, a missing frequency; `swapPreview` for one and two teams, unmet counts, `null` when blocked, and that the real draft is not touched.
- `PlayerSheet.test.js`: the picker lists everyone but A, filters accent-insensitively and with no result, choosing B shows the table, « Changer » and « Fermer la comparaison », the swap button disabled with its reason for locked, same team and both in the tray, `swap` dispatched with the ids, the preview lines with their words, a French rendering.
- Page test: swapping through the sheet changes both placements in one save, the sheet stays open on the pair, a second swap restores them, and `compareId` clears when B leaves the roster or the sheet closes.

On the fixture `$lib/fixtures/builder.js`; a locked player and a two-team draft are added to it if it has none.

## Later

Suggestions (the swap that most improves the scorer) would reuse `swapPreview` per candidate; the picker would only gain a group above the list.

## Open items

None.
