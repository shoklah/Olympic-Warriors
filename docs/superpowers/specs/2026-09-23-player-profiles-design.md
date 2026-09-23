# Player profiles: edition history, places and average rank

## Goal

Give every person who played a public profile with their rank in each edition and their
average rank across editions, plus an all-time leaderboard of players at `/players`,
ranked like a medal table on their places.

> **Revised 2026-09-23 (after the first build):** the leaderboard no longer ranks on the
> averages. It ranks on places (number of 1st places, then 2nd places, and so on), and
> its rows show those places.
>
> **Second revision, same day:** the teams-beaten share is gone everywhere, and the
> average rank is shown on the leaderboard rows (right-hand column) as well as on the
> profile. It still plays no part in the order. The leaderboard subtitle is « Le
> panthéon des Warriors » / "The Warriors hall of fame".

This is the first of three steps:

1. **This spec.** A profile and a leaderboard, built from team ranks.
2. **Later.** Rankings per discipline, meaning the team's rank in each discipline across
   editions.
3. **Later.** Awards and badges.

Nothing here builds steps 2 or 3, but the payloads leave room for them (see
"Room for later steps").

## Definitions

- **Person.** A `django.contrib.auth.User` with at least one active `Player` row in an
  active edition. The profile is keyed by the user id.
- **Participation.** One (user, edition) pair, from the user's active `Player` rows in that
  active edition. When a user has several such rows in one edition (it happens today:
  user 34 has two active 2024 rows), the lowest id among the rows with a valid team
  (active, of the player's edition) wins, otherwise the lowest id. No constraint or migration is added: the admin refuses new
  duplicates (see "Admin"), and sorting out the existing ones stays an admin task.
  `User.is_active` plays no part, because it controls who can log in, not who played.
- **Edition rank.** The rank of the participation's team in `compute_standings(edition)`.
  That is the computed rank, or `Team.final_rank` in a hand-ranked edition. It is `None`
  when:
  - the player has no team;
  - the team is inactive;
  - the team has no `final_rank` in a hand-ranked edition, or a `final_rank` of 0;
  - the edition has not finished (see below);
  - the edition is computed (not hand-ranked) and none of its results has a rank, because
    nothing was revealed or no discipline has a result type. The standings would then
    rank every team 1st on nothing, and missing data must never count as a win (decided
    2026-09-23 after the code review; the 2024 data on prod, still with
    `result_type='NON'`, is a live case).
- **Teams.** The number of active teams in the edition.
- **Finished.** `edition.end_date < today`, where today is the calendar date in
  Europe/Paris. `settings.TIME_ZONE` is UTC, so the date is taken with
  `datetime.now(ZoneInfo("Europe/Paris")).date()`, not `timezone.localdate()`.
- **Counted participation.** Finished, with a rank, in an edition of at least 2 teams.
- **Places.** The ranks of a person's counted participations, sorted best first (a
  lower rank first; equal ranks newest edition first). Each place keeps its year.
- **Average rank** (shown on the leaderboard rows and on the profile), over counted
  participations:
  - `average_rank`: the mean rank, rounded to one decimal (Python's `round`, which
    rounds halves to even), `None` when `counted` is 0;
  - `counted`: the number of counted participations.
- **Leaderboard.** Every person, split into two groups:
  - **Ranked** (`counted` ≥ 1): ordered like a medal table on their places: more 1st
    places first; at equal 1st places, more 2nd places; then more 3rd places; and so on
    down every place. An extra lower place therefore counts in a person's favour: one
    1st place and one 5th place ranks above a lone 1st place. People with the same count
    at every place share a position (1, 1, 3) and are listed by last name then first name
    (accent-insensitive). The average rank plays no part.
  - **Not ranked yet** (`counted` = 0): `position` is `None`, sorted by last name and
    first name.

  There is no minimum number of editions: each row shows its places, so a small sample
  is visible.

## Backend

### `olympic_warriors/profiles.py`

A module built like `standings.py`, with pure computation over a few queries, and nothing
stored.

```python
@dataclass(frozen=True)
class Participation:
    year: int
    team_id: int | None
    team_name: str | None
    rank: int | None      # None: see "Edition rank"
    teams: int
    finished: bool

@dataclass(frozen=True)
class PlayerRecord:
    user_id: int
    first_name: str
    last_name: str
    participations: tuple[Participation, ...]   # newest edition first
    places: tuple[Participation, ...]           # counted ones, best rank first
    counted: int
    average_rank: float | None
    position: int | None

def leaderboard(today=None) -> list[PlayerRecord]   # sorted as defined above
```

`leaderboard()` runs these queries:
- the active editions, annotated with their active team count (1);
- the active players of those editions with `user` and `team` (1);
- `compute_standings` for each **finished** edition that has a player (3 each). An
  unfinished edition's rank is `None` whatever its standings, so it is not computed.

That makes `2 + 3 × finished editions with players` queries in total. `today` defaults to the Paris date and can
be injected for tests. The profile endpoint uses the same `leaderboard()` and picks its
row, so a profile and the leaderboard can never disagree on a position.

### Endpoints

Both are public, with `@permission_classes([AllowAny])` below `@api_view`, and wired in
`urls.py`. The existing `/players/` and `/player/<id>/` endpoints (authenticated, raw
`Player` rows) are left as they are.

`GET /profiles/`: the leaderboard, in order.

```json
[
  {"id": 12, "first_name": "Léa", "last_name": "Martin", "played": 3, "counted": 2,
   "average_rank": 1.5,
   "places": [{"year": 2024, "rank": 1}, {"year": 2026, "rank": 2}], "position": 1}
]
```

`played` is the number of participations, finished or not. The profile below lists them
as `editions` instead. The average rank is shown on the row but plays no part in the order.

`GET /profile/<user_id>/`: one person.

```json
{
  "id": 34, "first_name": "Xavier", "last_name": "Baby",
  "position": 4, "counted": 2, "average_rank": 2.5,
  "editions": [
    {"year": 2030, "team": {"id": 40, "name": "Les Aigles"}, "rank": null, "teams": 4, "finished": false},
    {"year": 2026, "team": {"id": 21, "name": "MxM"}, "rank": 2, "teams": 6, "finished": true},
    {"year": 2024, "team": null, "rank": null, "teams": 8, "finished": true},
    {"year": 2023, "team": {"id": 5, "name": "Bisons"}, "rank": 3, "teams": 8, "finished": true}
  ]
}
```

It returns 404 when the user has no participation, which covers an unknown id and a user
who never played, such as the superuser.

Neither payload ever carries the username (the `/auth/token/` login name), the email,
`Player.rating` or the `PlayerRating` skill ratings. Everything in them is already public
through the edition summaries.

### Summary: user id on roster players

`SummaryPlayerSerializer` gains `user` (the user id), so the front can link roster chips
to `/players/<user>`. `SUMMARY_QUERIES` should not change, because `user` is already
selected for the names. The test pins it either way.

### Admin: assigning teams to players

- `PlayerAdmin.list_editable = ["team"]`, so an organiser can filter the changelist by
  edition and assign every player's team from one screen, with a single save.
- The team dropdowns of `PlayerAdmin` label a team `"<name> (<year>)"`. This goes through
  `formfield_for_foreignkey`, with a queryset using `select_related("edition")` ordered by
  year (newest first) then name, and a `ModelChoiceField` subclass overriding
  `label_from_instance`. `Team.__str__` is left as it is, since the blindtest guess string
  and other admin pages use it.
- Known cost: a `list_editable` foreign key evaluates its queryset once per row, which is
  one query per row, and saving adds a duplicate check per row. That is fine at the ~25
  rows of one edition, which is the documented workflow (filter by edition first); an
  unfiltered changelist shows up to 100 rows (Django's default page size).
  `list_select_related` keeps the rest of the page flat.
- `Player.clean()` refuses two mistakes, both with a `ValidationError` keyed on `team`:
  - a team whose `edition_id` differs from the player's;
  - another active `Player` of the same user in the same edition, when this row is
    active.

  Both errors are keyed on `team` because it is the only field that every admin form for
  `Player` has (the `list_editable` changelist form, the `TeamAdmin` inline, the change
  form). An error keyed on a field the form lacks makes Django raise `ValueError` ("has
  no field named"), which would turn a changelist save into a 500. This was checked on
  Django 4.2.19.

  The admin form and the `list_editable` formset both run `full_clean`, so the error
  shows on the row. The registration import and `import_edition` do not call `clean()`,
  so they behave as before. While Xavier's two 2024 rows exist, neither can be saved in
  the admin until one is deactivated. That is intended: it forces the choice between them.
  Because Django validates every row of a posted changelist page, the pair also blocks
  saving any other team assignment on the same page, such as the 2024 filter. Deactivate
  row 81 or 249 before assigning 2024's teams.
- On the team page, `team` is the inline's hidden foreign key, and the tabular inline
  never renders a hidden field's errors. `PlayerInline` therefore uses a
  `PlayerInlineForm` that repeats the `team` errors among the row's errors. On a new
  team the check reads the unsaved team object, which already carries the edition chosen
  on the team form, so a player of another edition is refused there too.
- Known gap: two new inline rows for the same person saved in one go both pass, because
  the duplicate check only sees rows already in the database. It is rare, and a
  formset-level check can be added if it ever happens.

## Front

### Routes

Both routes are outside the year segment, because a profile spans editions. The
`params/year.js` matcher (exactly four digits) keeps `/players` from matching `[year=year]`.

- `src/routes/players/+page.server.js` loads `/profiles/`, and `+page.svelte` renders
  the leaderboard.
- `src/routes/players/[id]/+page.server.js` loads `/profile/<id>/`, and `+page.svelte`
  renders the profile. The loader answers 404 itself, without calling the API, unless
  the id is canonical (1 to 10 digits, no leading zero), because it is spliced into an
  API path. A 404 from the API goes through `apiGet`'s `error(404)` and is rendered by
  `+error.svelte`.

Both are server loads through `apiGet`, like the other API reads, so `API_URL` stays
server-only.

### Leaderboard page (`/players`)

- `h1` "Joueurs" / "Players", with a muted subtitle under it: « Le panthéon des
  Warriors » / "The Warriors hall of fame" (it doesn't explain the order).
- **Ranked rows** (the list is not rendered when nobody is ranked). Each row shows:
  - `MedalRank` for the position (gold, silver or bronze for 1–3, shared on ties);
  - the name, linking to `/players/<id>`;
  - under the name, the places best first as `.num` figures coloured like `MedalRank`
    (gold 1, silver 2, bronze 3, plain after), e.g. `1 1 2 4`. At most the best 8 are
    shown, followed by `+N` when there are more. The figures are `aria-hidden`; a
    visually hidden sentence reads them instead: "1re place en 2024, 2e place en 2021" /
    "1st place in 2024, 2nd place in 2021" (French ordinals are feminine, agreeing with
    "place").
  - on the right, the average rank as a large `.num` figure (`formatAverage`: `1,5` /
    `1.5`) with a small `.label` under it, « rang moyen » / "avg rank".
- **"Pas encore classés" / "Not ranked yet"** section heading, then the name rows with
  `played` ("1 édition" / "1 edition"), and no position or places.
- The server sends the order, and the page does not re-sort.

### Profile page (`/players/<id>`)

- `Breadcrumb`: Joueurs → the name.
- `h1` the name.
- **Position line.** `MedalRank` for the all-time position as a plain number (a French
  ordinal would have to guess the player's gender: 1er or 1re), with the label
  "général" / "all-time", linking to `/players`. It is omitted when `position` is null.
- **One figure**, the average rank (`2,5` in French, `2.5` in English), in a card that
  keeps half the width. When `counted` is 0 it shows `—` and a line reads "Aucune
  édition classée pour l'instant" / "No ranked edition yet".
- **Counts line.** "3 éditions · 2 classées" / "3 editions · 2 counted".
- **Editions section**, newest first, one row per participation:
  - the year, linking to `/<year>`;
  - the team, linking to `/<year>/teams/<team id>`, or "Pas d'équipe" / "No team
    recorded" when there is none;
  - then one of:
    - `MedalRank` for the rank as a plain number (no ordinal) followed by "/ <teams>",
      when finished with a rank, e.g. `2 / 6`;
    - an "En cours" / "In progress" tag, when not finished;
    - `—`, when finished without a rank.

### Roster links

The player chips on `/<year>/teams/<id>` become links to `/players/<player.user>`, and
keep their chip styling. The names on `/<year>/ranking` stay plain text: each team card
there is already a single link, and a link cannot contain another link. From the
ranking, a profile is reached through the team page.

### Navigation

- `Header` and `TabBar` get a third internal item, "Joueurs" / "Players", pointing to
  `/players` (not scoped to a year). It goes after Disciplines and before the Photos
  link, and it is current on any path starting with `/players`.
- On `/players…`, the year falls back to `latestYear` as it already does on `/login`, so
  the Ranking and Disciplines tabs point to the latest edition, and the year select sends
  the visitor to that year's hub (`switchYearPath` behaves the same for any path outside
  the year segment).
- The tab bar shows on both new routes, because neither is in `HUB_OR_LOGIN`.
- `EditionHub` gets a "Joueurs" / "Players" link to `/players`, next to its existing
  ranking link and in the same shape, but outlined rather than filled, so the edition's
  ranking stays the main call to action. It also shows before the start, under the
  countdown, because the leaderboard covers past editions; there it is the only button,
  so it stays filled (review decision, 2026-09-23). On a phone the hub has neither the tab bar nor the
  header tabs, and without this link the leaderboard would be two taps away from the
  home page.

### Helpers and i18n

- `src/lib/players.js` holds pure, locale-aware formatters:
  - `formatAverage(value, locale)`: one decimal, with a French comma (leaderboard and
    profile);
  - `editionStatus(participation)`: `'ranked' | 'inProgress' | 'unranked'`;
  - `fullName(person)`: first and last name, or `—` when both are blank (leaderboard,
    profile and team page roster chips).
- New keys in `fr.js` and `en.js`, kept at parity:
  - `nav.players` and `hub.players`;
  - the page titles and subtitle;
  - "Not ranked yet";
  - the average rank labels (`profile.averageRank`, and `players.averageRank` for the
    row);
  - "all-time", and the position link's visually hidden hint (`profile.positionHint`);
  - the counts, as `{ one, other }` plural messages;
  - "No team recorded";
  - "In progress";
  - "No ranked edition yet";
  - the hidden sentence for one place (`players.placeIn`: '{place} place en {year}' /
    '{place} place in {year}', the place written with `ordinal`), and the `+N` overflow
    (`players.more`).

## Room for later steps

- **Rankings per discipline** could add a `disciplines` field to the profile, built from
  the `Standings.results` that `leaderboard()` already computes for each edition.
- **Computed badges** (champion, podium, veteran) can come from `participations`.
  Badges given out by hand would need their own model.

Neither is built here.

## Testing

Server (`tests/test_profiles.py`):
- `leaderboard()` with an injected `today`:
  - an unfinished edition shows its team with a `None` rank and is not counted;
  - a finished edition counts from the day after `end_date`, by the Paris date;
  - a player without a team is not counted;
  - a hand-ranked edition uses `final_rank`, and a team without one gives a `None` rank;
  - an inactive player, team or edition drops out;
  - a duplicate (user, edition) pair collapses to the row with a team;
  - the average rank and its rounding are correct, and no share exists any more;
  - places are the counted ranks, best first, equal ranks newest first;
  - the medal-table order: more 1st places first, then 2nd places, and so on; an extra
    lower place ranks a person above an otherwise equal one; identical counts share a
    position and are listed by name;
  - a person with no counted edition sits in the "not ranked yet" group with a `None`
    position.
- Endpoints:
  - both are public (no token needed);
  - the payload shapes match the examples;
  - 404 for a user with no participation and for an unknown id;
  - no username or email anywhere in the payload;
  - the query counts are pinned (`PROFILES_QUERIES` as a function of the edition count).
- Summary: roster players carry `user`, and `SUMMARY_QUERIES` stays the same.
- Admin: the team is editable from the Player changelist, and the dropdown labels carry
  the year.
- `Player.clean()`:
  - refuses a team from another edition;
  - refuses a second active row for the same (user, edition);
  - accepts an inactive duplicate and a row without a team.

Front:
- `players.test.js` for the formatters and `editionStatus`, including French and English
  outputs.
- `players/page.test.js`:
  - leaderboard rows read like `1 Léa Martin 1 2 1st place in 2024, 2nd place in 2026
    1.5 avg rank` (position, name, places, hidden sentence, average rank);
  - the not-ranked group has no position;
  - one French test.
- `players/[id]/page.test.js`:
  - the average-rank figure, and no teams-beaten figure;
  - edition rows read like `2026 MxM 2 / 6`, `2030 Les Aigles In progress` and
    `2024 No team recorded`;
  - the no-ranked-edition state;
  - one French test.
- `Header` and `TabBar` tests: the Players item, its href, and `aria-current` on
  `/players` and `/players/34`.
- `EditionHub` test: the Players link to `/players`.
- Team page test: roster chips link to `/players/<user>`.
- Fixtures: `summary.js` players gain `user`, plus new profile and leaderboard fixtures.

`npm test` and `npm run build` must pass (the CI gate). The Django suite runs through the
compose stack.

## Known limitations

- The registration import links returning players by a username derived from their
  name. Two different people with the same full name share one user, and therefore one
  profile.
- Stats are only as complete as the rosters. The 2024 players in the local database have
  no team until one is assigned (made easier by the admin change above). Early editions
  without `Player` rows contribute to no one.
- Profiles are public with no opt-out. Adding one later would need a per-user setting
  (a new model), because `User` is Django's own.

## Out of scope

- Rankings per discipline, awards and badges (steps 2 and 3).
- A database unique constraint on (edition, user), and cleaning up the existing duplicates
  automatically. `Player.clean()` only stops new ones from the admin.
- A bulk roster import for past editions.
- Skill ratings on profiles.

## Documentation

The implementation updates `CLAUDE.md`: the `profiles.py` module and its rules, the two
public endpoints, the `user` field on summary players, the `PlayerAdmin` change, and the
`/players` routes with the Players tab.
