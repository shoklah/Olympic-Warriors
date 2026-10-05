# Team builder: player preview

Date: 2026-10-06. Extends `2026-10-05-team-builder-design.md`. Front only.

## Goal

While building teams, an organiser can open a player's full rating profile from their card: overall rating, global level, frequency, one bar per skill and the sports history. Today a card shows only the overall `rating`; the per-team averages and skill bars say nothing about an individual.

## Non-goals

- No server change: `GET /builder/<year>/` already returns `rating`, `global_level`, `ratings` (by skill identifier), `sport_frequency` and `sports` per player, and the edition's `skills`.
- No move, lock or placement control in the sheet; the card keeps those.
- No wishes (`team_with` / `team_avoid`) in the sheet; the card already shows them as notes.
- No sort or filter of the tray by skill. Kept in mind, not built (see "Later").

## Design

### Trigger (`PlayerCard.svelte`)

- A new info icon button (an "i" in a circle, first an eye) beside the lock, same `icon-button` style, on every card (tray and teams). Accessible name `builder.preview` with the player's name.
- A click dispatches `preview` with `{ id: player.id }`. It starts no drag and does not touch the card's `draggable`.
- `BuilderTeams` forwards `preview` from both its tray and team cards. `+page.svelte` owns one `previewId` (null when closed), set by the event, and passes the player and the opener to the sheet.

### Sheet (`$lib/components/builder/PlayerSheet.svelte`, new)

A dialog using `use:modal={{ onClose }}` from `$lib/modal.js`, like `BadgeSheet` and `ScoreSheet`: a bottom sheet below 1000px, a centred dialog above; Escape closes, Tab wraps, page scroll is locked. Focus returns to the info button that opened it through an `opener` prop (as `PhotoEditor` does), since the card may move or re-render while open.

Content, top to bottom:

1. Header: the player's name; a subtitle with where they stand, `builder.team` (« Équipe 3 ») or `builder.preview.tray` (« En attente »).
2. Summary line: overall rating, `global_level` (`—` when null, as on editions imported before it existed) and the frequency label. Frequency reuses `register.frequency.*`; a missing frequency shows `—` and counts as estimated (`hour`), as in `features`.
3. Skill bars: one per edition skill, in `skills` order, labelled by `name_fr`/`name_en` per locale, value 1 to 10 (width `value × 10%`, the per-team bars' look). A missing skill takes the overall rating, as `features` does, drawn dimmed with « estimé ».
4. Notice `builder.incomplete` (« Profil incomplet ») when anything above was estimated.
5. Sports: `sport · level` per row, the level through `register.level.*`; `builder.preview.noSports` when empty.

The sheet renders only while open, like the other dialogs. A player who leaves the roster while it is open (a reloaded draft) closes it.

### Pure logic (`$lib/builder/profile.js`, new)

`playerProfile(player, skills, locale)` returns `{ rating, globalLevel, frequency, bars: [{ identifier, name, value, estimated }], sports, incomplete }`. It derives the fallbacks from `features` in `score.js` instead of repeating them: `features(player, skills).skills` gives the values, and `estimated` is a skill whose `player.ratings[identifier]` is null or absent. `incomplete` is `features(...).incomplete`, so the sheet and the scorer never disagree on what is estimated. The sheet only draws this object.

### i18n

New keys in `fr.js` and `en.js` (parity-tested): `builder.preview` (« Voir le profil de {name} »), `builder.preview.tray`, `.rating`, `.frequency`, `.skills`, `.estimated`, `.sports`, `.noSports`, `.close`. Reused: `builder.team`, `builder.incomplete`, `register.globalLevel`, `register.frequency.*`, `register.level.*`.

## Tests

- `profile.test.js`: all skills present; one missing (estimated, takes the overall rating); no frequency (incomplete); empty `ratings`; locale picks the skill name; `global_level` null.
- `PlayerSheet.test.js`: header and summary, one bar per skill, the estimated bar and notice, sports list and empty state, tray versus team subtitle, a French rendering, Escape calls `onClose`.
- `PlayerCard.test.js`: the info button exists with its name, dispatches `preview` with the id, and is present for tray and team cards.
- Page test: clicking the info button opens the sheet, closing it returns focus to the button, and a player removed by a reload closes it.
- `modal.test.js` already covers the dialog mechanics.

All on the fixture `$lib/fixtures/builder.js`: player 5 (empty ratings, no frequency) is the incomplete case, player 3 has a sport.

## Later (sort and filter)

`playerProfile` and the skills list are what a tray sort-by-skill needs, so a later change reuses them; the sheet does not change.

## Open items

None.
