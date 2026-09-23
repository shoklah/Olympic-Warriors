# Player profiles: edition history and averages

## Goal

Give every person who played a public profile with their rank in each edition and their
averages across editions, plus an all-time leaderboard of players at `/players`.

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
  user 34 has rows 81 and 249 in 2024), the lowest id among the rows with a team wins,
  otherwise the lowest id. No constraint or migration is added: the admin refuses new
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
- **Share beaten.** `(teams - rank) / (teams - 1)`, clamped to `[0, 1]`: 100% for 1st,
  0% for last, and shared ranks give shared shares. The clamp only matters for bad data,
  such as a `final_rank` larger than the team count.
- **Averages**, over counted participations only:
  - `average_rank`: the mean rank, rounded to one decimal (Python's `round`, which
    rounds halves to even);
  - `average_beaten`: the mean share beaten, as a whole percentage (0 to 100);
  - `counted`: the number of counted participations;
  - both averages are `None` when `counted` is 0.
- **Leaderboard.** Every person, split into two groups:
  - **Ranked** (`counted` ≥ 1): sorted by `average_beaten` descending, then `average_rank`
    ascending, then `counted` descending, then last name and first name. `position` is
    1 + the number of ranked people with a strictly better (`average_beaten`,
    `average_rank`) pair, compared on the rounded values the API returns. Ties share a
    position (1, 1, 1, 4). The order inside a tie (`counted`, then name) does not change
    the position.
  - **Not ranked yet** (`counted` = 0): `position` is `None`, sorted by last name and
    first name.

  There is no minimum number of editions: each row shows `counted`, so a small sample is
  visible.

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
    counted: int
    average_rank: float | None
    average_beaten: int | None
    position: int | None

def beaten_share(rank, teams) -> float | None
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
  {"id": 12, "first_name": "Léa", "last_name": "Martin",
   "played": 2, "counted": 2, "average_rank": 1.0, "average_beaten": 100, "position": 1}
]
```

`played` is the number of participations, finished or not. The profile below lists them
as `editions` instead.

`GET /profile/<user_id>/`: one person.

```json
{
  "id": 34, "first_name": "Xavier", "last_name": "Baby",
  "position": 4, "counted": 2, "average_rank": 2.5, "average_beaten": 71,
  "editions": [
    {"year": 2030, "team": {"id": 40, "name": "Les Aigles"}, "rank": null, "teams": 4, "finished": false},
    {"year": 2026, "team": {"id": 21, "name": "MxM"}, "rank": 2, "teams": 6, "finished": true},
    {"year": 2024, "team": null, "rank": null, "teams": 8, "finished": true}
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
  one query per row. That is fine at 25 rows.
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
  renders the profile. A 404 from the API goes through `apiGet`'s `error(404)` and is
  rendered by `+error.svelte`.

Both are server loads through `apiGet`, like the other API reads, so `API_URL` stays
server-only.

### Leaderboard page (`/players`)

- `h1` "Joueurs" / "Players", with a muted sentence under it: "Toutes éditions
  confondues, selon la part d'équipes battues" / "All editions, by share of teams
  beaten".
- **Ranked rows** (the list is not rendered when nobody is ranked). Each row shows:
  - `MedalRank` for the position (gold, silver or bronze for 1–3, shared on ties);
  - the name, linking to `/players/<id>`, with a muted line under it giving the mean
    rank and the editions it is based on ("moy. 2,5 sur 2 éditions" / "avg 2.5 over 2
    editions", from `counted`);
  - the share beaten as the main figure (`.num`), on the right.
- **"Pas encore classés" / "Not ranked yet"** section heading, then the name rows with
  `played` ("1 édition" / "1 edition"), and no position or figures. "sur 2 éditions"
  versus a bare "N éditions" keeps the two counts apart (review decision, 2026-09-23).
- The server sends the order, and the page does not re-sort.

### Profile page (`/players/<id>`)

- `Breadcrumb`: Joueurs → the name.
- `h1` the name.
- **Position line.** `MedalRank` for the all-time position as a plain number (a French
  ordinal would have to guess the player's gender: 1er or 1re), with the label
  "général" / "all-time", linking to `/players`. It is omitted when `position` is null.
- **Two figures**, side by side at the same size, neither one the headline:
  - Average rank: `average_rank`, shown as `2,5` in French and `2.5` in English.
  - Teams beaten: `average_beaten`, shown as `71 %` in French and `71%` in English.
  - When `counted` is 0, both show `—` and a line reads "Aucune édition classée pour
    l'instant" / "No ranked edition yet".
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
  countdown, because the leaderboard covers past editions. On a phone the hub has neither the tab bar nor the
  header tabs, and without this link the leaderboard would be two taps away from the
  home page.

### Helpers and i18n

- `src/lib/players.js` holds pure, locale-aware formatters:
  - `formatAverage(value, locale)`: one decimal, with a French comma;
  - `formatShare(value, locale)`: `Intl.NumberFormat` percent, giving a no-break
    space before `%` in French;
  - `editionStatus(participation)`: `'ranked' | 'inProgress' | 'unranked'`.
- New keys in `fr.js` and `en.js`, kept at parity:
  - `nav.players`;
  - the page titles and subtitle;
  - "Not ranked yet";
  - the average rank and teams beaten labels;
  - "all-time";
  - the counts, as `{ one, other }` plural messages;
  - "No team recorded";
  - "In progress";
  - "No ranked edition yet";
  - the leaderboard's secondary line (`players.over`, a plural message).

## Room for later steps

- **Rankings per discipline** could add a `disciplines` field to the profile, built from
  the `Standings.results` that `leaderboard()` already computes for each edition.
- **Computed badges** (champion, podium, veteran) can come from `participations`.
  Badges given out by hand would need their own model.

Neither is built here.

## Testing

Server (`tests/test_profiles.py`):
- `beaten_share`:
  - 1st gives 1.0, last gives 0.0, shared ranks give equal shares;
  - `None` below 2 teams;
  - clamped when the rank is larger than the team count.
- `leaderboard()` with an injected `today`:
  - an unfinished edition shows its team with a `None` rank and is not counted;
  - a finished edition counts from the day after `end_date`, by the Paris date;
  - a player without a team is not counted;
  - a hand-ranked edition uses `final_rank`, and a team without one gives a `None` rank;
  - an inactive player, team or edition drops out;
  - a duplicate (user, edition) pair collapses to the row with a team;
  - the averages and their rounding are correct;
  - the sort and shared positions are correct: teammates tie, two rows tied on the
    rounded pair share a position, and within a tie more editions come first;
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
  - leaderboard rows read like `1 Léa Martin avg 1.0 over 2 editions 100%`;
  - the not-ranked group has no position;
  - one French test.
- `players/[id]/page.test.js`:
  - the headline figures;
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
