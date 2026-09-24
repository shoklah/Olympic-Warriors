# All-time player table per discipline

## Goal

A follow-up to the player profiles (the leaderboard, the places per discipline, the
badges): for each discipline, rank every person on their places in it across editions,
shown on the discipline page next to the edition's own data. The "Out of scope" of the
places-per-discipline spec deferred these per-discipline leaderboards.

Nothing is stored.

## Decisions

Settled with Hugo on 2026-09-24:

1. **A person's place in a discipline is their team's rank there**, given to the whole
   roster. Every player competes in every event (injuries and schedule clashes aside),
   so no per-player line-up is recorded. This is the place « Par épreuve » and the
   `specialist` badge already use, so the table never disagrees with a profile.
2. **Order: the leaderboard's medal table** (`_places_key`): more 1st places first,
   then more 2nd places, and so on; an extra lower place counts in a person's favour;
   identical places share a position. No weighting by the number of teams, no
   average-rank tie-break.
3. **What counts: the profile's rule.** Only counted participations (finished, ranked,
   at least 2 teams) and ranked results (revealed, scored). A running edition enters the
   table the day after its `end_date`, when the profiles and the leaderboard pick it up. The
   table lists only people with at least one place in the discipline: there is no
   "not ranked yet" section.
4. **Every discipline with a counted place has a table**, including one held once.
5. **Where: a tab on the edition's discipline page**, `/<year>/disciplines/<id>`, not a
   route of its own. The server resolves the discipline's name from the id, so no slug is
   needed.
6. **Tabs separate the edition from all time**: « Édition 2026 » / « Palmarès ». The
   all-time table is fetched only on its tab, so the edition tab (the busiest page on
   event day) never pays for it.
7. **The table is the same on every year's page**: every finished edition as of today,
   not a snapshot up to the page's year.
8. **A row reads like the profile's « Par épreuve » row**, with the person's name in
   place of the discipline's: position, name, places as a coloured rank and its year.
   No average rank.
9. **The all-time tab is always shown**, with an empty state when nothing counts yet.
10. **The profile's « Par épreuve » rows link to the table**, without showing the
    person's all-time position.

## Definitions

- **Discipline identity across editions.** `Discipline.name`, as for « Par épreuve »,
  the badges and scoring.
- **Places of a person in a discipline.** The person's `DisciplinePlaces` entry for that
  name (`PlayerRecord.disciplines`): their counted participations' ranked results in it,
  best first (lower rank, then newer year).
- **Table of a discipline.** Every person with a `DisciplinePlaces` entry for its name,
  sorted by `_places_key(places)` and then by accent-insensitive name (`_by_name`), with
  shared positions from `_positioned` (1, 1, 3, …).
- **Years of a table.** The distinct years of its places, oldest first. A year where the
  discipline was held but gave nobody a place (hidden, unscored) is not one of them.

## Backend

### `profiles.py`

- `DisciplinePlace` gains `discipline_id`, the `Discipline` row of that edition, read
  from the `DisciplineStanding` it is built from (no query).
- `DisciplinePlaces` gains a `latest` property: its newest place (highest year), which the
  profile's link points to.
- New `discipline_table(name, today=None)` returns
  `DisciplineTable(name, years, rows)`, each row a
  `DisciplineRow(user_id, first_name, last_name, places, position)`. It builds the records
  as `leaderboard()` does (`_record` over `participations(today)`), keeps each record's
  entry for `name`, and orders and positions the rows by the definition above. No new
  query: `participations()` already loads everything.

### API

New public view `getDisciplineAllTime`, route `discipline/<int:discipline_id>/all-time/`,
`@permission_classes([AllowAny])` below `@api_view`:

- 404 unless the discipline is active and its edition is active (one query for its
  name), then `discipline_table(name)`.
- Queries: 1 + `PROFILES_QUERIES` (2 + 3 × finished editions with players), pinned as
  `DISCIPLINE_TABLE_QUERIES`.

```json
{
  "name": "Rugby",
  "years": [2024, 2025],
  "players": [
    {
      "id": 12,
      "first_name": "Léa",
      "last_name": "Martin",
      "position": 1,
      "places": [{"year": 2025, "rank": 1}, {"year": 2024, "rank": 2}]
    }
  ]
}
```

`id` is the user id, as on `/profiles/`. Names only, never the username or the email.
An empty table is `{"name": …, "years": [], "players": []}` with status 200.

`GET /profile/<user_id>/`: each `disciplines[]` entry gains
`"latest": {"year": 2025, "discipline": 41}`, the year and discipline id of the person's
newest place there. `GET /profiles/` is unchanged.

## Front

### Discipline page (`/<year>/disciplines/<id>`)

- **Layout.** Breadcrumb, title, `DisciplineRail`, then the tabs, then the tab's content.
  The organiser's `StaffBar` moves from above the rail to the top of the edition tab, so
  the rail and the tabs don't move when switching tabs. Every organiser control stays on
  the edition tab.
- **Tabs.** A `nav` labelled « Sections de l'épreuve » / "Discipline sections"
  (`discipline.tabs`) holding two plain links with `aria-current`,
  `data-sveltekit-noscroll` and `data-sveltekit-keepfocus`, styled like the profile's:
  - « Édition 2026 » / "2026 edition" (`discipline.tab.edition`, no parameter): today's
    page, unchanged;
  - « Palmarès » / "All time" (`discipline.tab.allTime`, `?tab=all-time`).
  Any other `tab` value is the edition tab.
- **Loading.** `+page.server.js` gains a `load` (next to its actions) returning
  `{ tab, allTime }`. It calls `/discipline/<id>/all-time/` only when `tab` is
  `all-time` and the id is one of the year summary's disciplines (from `parent()`);
  otherwise `allTime` is `null`, and `+page.js` answers the 404 as today. `+page.js`
  spreads the server `data` into its return value, since SvelteKit hands the universal
  load the server data but does not merge them.
- **Rail.** `DisciplineRail` gains a `tab` prop (default `null`). On the all-time tab
  its tiles link to `?tab=all-time`, so one can flip through the disciplines' tables.
  The ranking page passes nothing, so its rail is unchanged.
- **All-time tab.** A new `AllTimeTable` component (`src/lib/components/`) renders:
  - a visually hidden `h2` « Palmarès » / "All time";
  - a subtitle naming the years with `Intl.ListFormat` (conjunction), so a gap shows
    (« Éditions 2024 et 2026 », "2024 and 2026 editions"; « Édition 2024 » / "2024
    edition" for one year; `discipline.allTime.years`, plural on the year count);
  - an ordered list, one row per person: a link to `/players/<id>` holding
    `MedalRank` (the shared position), the full name (`fullName`), and the places as a
    `.num` rank coloured gold, silver or bronze for 1–3 and `--muted` after, each
    followed by its year, small and muted, as in « Par épreuve ». The places are
    `aria-hidden` behind the spoken `spokenPlaces` sentence. Rows are styled like the
    leaderboard's: metal left border for positions 1–3, same hover and focus.
  - without rows, « Aucune édition terminée pour cette épreuve » / "No finished edition
    for this discipline yet" (`discipline.allTime.empty`) instead of the subtitle and the
    list.
- **Year switch.** Unchanged: the header sends a discipline page to the other year's
  discipline list, dropping the tab.

### Profile (`/players/<id>`)

Each « Par épreuve » row becomes a link to
`/<latest.year>/disciplines/<latest.discipline>?tab=all-time`, styled like the other
row links (no underline, hover and focus on the row). Its text and its spoken sentence are
unchanged, so the row still reads `Relay 1 2026 2 2023`.

### Keys

`discipline.tabs`, `discipline.tab.edition` (`{year}`), `discipline.tab.allTime`,
`discipline.allTime.years` (`{ one, other }`, `{years}` already joined),
`discipline.allTime.empty`, in `fr.js` and `en.js`.

## Testing

Server (`test_profiles.py`, or a new `test_discipline_table.py`):

- `discipline_table`:
  - aggregates places by name across editions, each row's places best first;
  - orders rows by the medal table, ties sharing a position and listed by name;
  - leaves out a running edition, a hidden or unscored result, an inactive discipline,
    team or edition, and a person without a place in the discipline;
  - `years` holds only the years that give a place, oldest first;
  - gives an empty table for a discipline without any counted place.
- `/discipline/<id>/all-time/`:
  - is public, and ids of the same discipline name in two editions give the same payload;
  - 404 for an unknown id, an inactive discipline, and a discipline of an inactive
    edition;
  - carries names only (no username, no email);
  - runs in `DISCIPLINE_TABLE_QUERIES`.
- `/profile/<id>/`: `disciplines[].latest` points to the newest place's year and
  discipline id; `PROFILES_QUERIES` still holds.
- `test_routes.py` covers the new route by itself.

Front:

- `page.server.test.js` (discipline): the load fetches only with `?tab=all-time`, and
  not for an id outside the summary.
- `page.test.js` (discipline):
  - two tabs, with `aria-current` on the shown one; the edition tab unchanged;
  - `StaffBar` only on the edition tab;
  - an all-time row reads `1 Léa Martin 1 2025 2 2024`, its link named
    `1 Léa Martin 1st place in 2025, 2nd place in 2024`, pointing to `/players/<id>`;
  - the subtitle's years, and the empty state;
  - one French test (« Palmarès », « Édition 2026 », « Éditions 2024 et 2025 »).
- `AllTimeTable.test.js`: medal positions, shared positions, places `aria-hidden`.
- `DisciplineRail.test.js`: tiles keep `?tab=all-time` when given the tab.
- Profile `page.test.js`: each « Par épreuve » row links to its `latest` page's
  all-time tab.
- Fixtures: an all-time payload in `src/lib/fixtures/players.js`, and `latest` on the
  profile fixture's disciplines.

## Out of scope

- Per-player line-ups (who actually played a discipline).
- Weighting places by the number of teams.
- The person's all-time position on the profile's « Par épreuve » rows.
- A snapshot of the table as of a past year.
- A route outside the year segment, and a discipline picker on `/players`.
- Keeping the tab when switching years.
- Linking the `specialist` badge sheet to the table.
