# Disciplines list: every discipline ever held

## Goal

The disciplines list (`/<year>/disciplines`) shows the selected edition's disciplines first,
as today, then every discipline ever recorded, each leading to its all-time table: the
« Palmarès » tab of the discipline page (`2026-09-24-discipline-all-time-table-design.md`).
Until now a discipline's table was reachable only from an edition that held it, through that
edition's list, or from a profile's « Par épreuve » row.

Nothing is stored.

## Decisions

1. **A deck of cards below the edition's**, not a tab: both lists stay in view on the busiest
   page, and the edition's cards keep their place.
2. **Every discipline name an active edition held** through an active row, finished edition
   or not, revealed result or not: its table then shows its own empty state. Names match
   across editions as for the table.
3. **A card leads to the « Palmarès » tab of the discipline's page in the browsed year** when
   that edition held it, so the visitor stays in the year they browse, **else in its newest
   edition**, like the profile's links. The table is the same on every edition's page.

## Backend

`profiles.held_disciplines()` (one query): the active discipline rows of active editions,
nameless rows left out, grouped by name in accent-insensitive name order. Each is a
`HeldDiscipline(name, editions)`, the editions oldest first as `HeldEdition(year,
discipline_id)`, the lowest id when an edition held the name twice.

Public `GET /disciplines/all-time/` (view `getHeldDisciplines`, `AllowAny`):

```json
[
  {"name": "Relay", "editions": [{"year": 2024, "discipline": 7}, {"year": 2026, "discipline": 10}]}
]
```

## Front

- The page's `+page.server.js` fetches the index. It reads no param, so a year switch reuses
  it; it does not await `parent()`, so it re-runs no layout load.
- Under the edition's cards, a section « Palmarès » / "All time" with the intro « Toutes les
  épreuves déjà disputées, chacune avec le classement de ses joueurs toutes éditions
  confondues. », absent when nothing was ever held.
- One card per held discipline, sorted by the name shown in the locale (`byShownName`):
  icon, name, `4 éditions · 2023–2026` (`yearSpan`, a single year alone), named
  « Relais, palmarès » / "Relay, all time" apart from the edition's own « Relais » card, and
  leading to `allTimePath(discipline, year)`.
- Both decks render `DisciplineCard`, one link named `label ?? name` (resolved on render, so a
  card an each block reuses on a year switch never keeps an old name). One image per
  component keeps the white-icon guard of `styles.test.js` to a single filter rule.
- New keys: `disciplines.allTime`, `disciplines.allTimeIntro`, `disciplines.allTimeOf`,
  `disciplines.editions` (plural).

## Testing

- Server (`TestHeldDisciplines` in `test_profiles.py`): names in order with their editions,
  a discipline without results, the lowest id per year, inactive rows and editions left out,
  a nameless row left out, the public endpoint's payload in one query.
- Front: `all-time.test.js` (the order in both languages, the span, the link to the browsed
  year or the newest), `DisciplineCard.test.js`, the page (the deck, its links, its absence,
  French) and its loader.
