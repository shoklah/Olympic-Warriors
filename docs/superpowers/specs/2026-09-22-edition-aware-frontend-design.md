# Edition-aware frontend — design

Date: 2026-09-22

## Goal

Make the SvelteKit front show one edition at a time, with every edition
browsable all year by participants, and stop mixing the 2024, 2025 and 2026
rows that the API now holds. The current edition is a default, not a special
case. Along the way, remove the login wall from read-only pages, replace the
hard-coded 2024 landing page, and give the front real error handling and test
tooling.

Organiser tools (scoring, entering results) and the schedule/games pages are
follow-up specs, not part of this one.

## Current behaviour

- Every list page calls `/disciplines` or `/teams`, which return all active
  rows of every edition. With three editions loaded, the grids and the global
  ranking mix years.
- The home page has a countdown to a hard-coded September 2024 date that never
  renders (`OwStarted` starts at `true`) and six hard-coded discipline icons.
- Discipline icons come from a six-entry map keyed by name; Darts (added in
  migration 0026) and any future discipline render a broken image.
- Teams, rankings and team pages redirect to `/login` without a cookie. The
  `hooks.server.js` stub sets a fake `locals.user` that nothing reads.
- `requestAPI()` returns `{error}` objects and no load checks them, so an
  expired token or a 404 crashes the page render.
- The global ranking sorts on `team.global_points`, a field the API does not
  return, so teams arrive in database order. The discipline ranking page does
  one request per team for names the results serializer already carries.
- `/profile`, `/action/blindtest` and `/photos` are placeholders.
- `getTeamResultsByEdition` filters `TeamResult` on an `edition` field that
  does not exist on the model, so the endpoint raises.
- The front has no test, lint or check tooling.

## Decisions

- **Audience:** participants, all year. Past editions are first-class.
- **Edition in the URL:** a four-digit year path segment (`/2026/teams`).
  Ids change between local and prod on every transfer; years do not.
- **Current edition:** the active edition with the highest year. No date logic,
  no flag.
- **Visibility:** everything read-only is public. Login stays only for the
  future organiser tools. Per-discipline secrecy keeps using
  `Discipline.reveal_score`.
- **Home:** `/` is the hub of the latest edition and `/<year>` the hub of any
  edition, rendered by one shared component.
- **Depth:** rankings and rosters only. No rounds, games or events.
- **Data assembly:** one aggregated, public summary endpoint per edition. The
  front makes two API calls per page at most (editions list + summary).
- **Photos:** an optional `photos_url` on the edition, shown as an external
  header link when set.
- **Tests:** Vitest unit tests on pure derivation helpers plus
  `@testing-library/svelte` component tests on the main pages.

## Backend

### `Edition` model (`server/olympic_warriors/models/Edition.py`)

- `year` gains `unique=True`. The URL contract depends on it.
- New `photos_url = models.URLField(blank=True, null=True)`. It appears in the
  Edition admin automatically (the admin does not restrict fields).
- One migration, `0027`, for both changes. The existing data has one edition
  per year, so the unique constraint applies cleanly.

### Summary endpoint

`GET /edition/year/<int:year>/summary/`, decorated `@api_view(["GET"])` then
`@permission_classes([AllowAny])` below it (the order matters, see
CLAUDE.md). Returns 404 `{"error": "Edition not found"}` when no active
edition has that year.

Payload:

```json
{
  "edition":     {"id", "year", "host", "start_date", "end_date", "photos_url"},
  "disciplines": [{"id", "name", "result_type", "reveal_score"}],
  "teams":       [{"id", "name", "ranking", "total_points",
                   "players": [{"id", "first_name", "last_name"}]}],
  "results":     [{"id", "team", "discipline", "result_type", "ranking",
                   "points", "time", "points_difference", "global_points"}]
}
```

Rules:

- Only `is_active=True` rows for disciplines, teams, players and results.
- `disciplines` in id order; `teams` in name order; `results` in id order.
  Sorting for display is the front's job.
- For a discipline whose `reveal_score` is false, every result of that
  discipline has `ranking`, `points`, `time`, `points_difference` and
  `global_points` set to `null`. The endpoint is public and must not leak a
  score before it is revealed.
- `teams[].ranking` and `teams[].total_points` come from the existing `Team`
  properties, which already honour `reveal_score`.
- The view uses the existing model properties for rankings; it does not
  duplicate ranking logic. Around ten teams by eight disciplines is a few
  hundred small queries, acceptable. If it ever shows on prod, compute the
  per-discipline rankings once in the view; do not change the payload.

Implementation: a `EditionSummarySerializer` in `serializer.py` built from
nested `ModelSerializer`s for the edition, disciplines and players, plus a
small results serializer that applies the null rule from a `revealed` flag
passed in context. The view builds the querysets and hands them to the
serializer. Registered in `urls.py` next to the other edition routes.

### Bug fix

`getTeamResultsByEdition` filters on `discipline__edition=edition_id`.

### Untouched

No other view, permission or serializer changes. The front stops calling
`/teams`, `/team/<id>`, `/discipline/<id>`, `/disciplines` and
`/results/discipline/<id>`, but they remain for the API's other consumers.

## Frontend

### Routes

`src/params/year.js` matches `^\d{4}$`, so `/login` never hits the year route.

| Route file | URL | Content |
|---|---|---|
| `routes/+page.svelte` | `/` | Hub of the latest edition |
| `routes/[year=year]/+page.svelte` | `/2026` | Hub of that edition |
| `routes/[year=year]/ranking/+page.svelte` | `/2026/ranking` | Global ranking and discipline rail |
| `routes/[year=year]/disciplines/+page.svelte` | `/2026/disciplines` | Discipline cards |
| `routes/[year=year]/disciplines/[id]/+page.svelte` | `/2026/disciplines/12` | Discipline ranking |
| `routes/[year=year]/teams/+page.svelte` | `/2026/teams` | Teams with rosters |
| `routes/[year=year]/teams/[id]/+page.svelte` | `/2026/teams/42` | Roster and results |
| `routes/login/…` | `/login` | Unchanged, out of the nav |
| `routes/ranking/+page.server.js` | `/ranking` | 301 to `/<latest>/ranking` |
| `routes/teams/+page.server.js` | `/teams` | 301 to `/<latest>/teams` |
| `routes/disciplines/+page.server.js` | `/disciplines` | 301 to `/<latest>/disciplines` |

Deleted: `routes/profile`, `routes/action`, `routes/photos`,
`routes/disciplines/[slug]` (both levels), `routes/teams/[slug]`,
`routes/login/register.svelte`, `hooks.server.js`, `Footer.svelte` (already
unused). Legacy id URLs get no redirect: ids changed in the prod migration.

### Data flow

- **Root layout load** (`routes/+layout.server.js`): fetches `/editions/`,
  keeps active ones, sorts by year descending, returns
  `{editions, latestYear}`. `editions` carries `year`, `host`, `photos_url`.
- **Year layout load** (`routes/[year=year]/+layout.server.js`): fetches the
  summary for `params.year`, returns `{summary}`. A 404 from the API becomes
  `error(404, "No edition in <year>")`.
- **Home load** (`routes/+page.server.js`): reads `latestYear` from `parent()`,
  fetches that summary, returns `{summary}`. If there is no edition at all it
  throws `error(404, "No edition yet")`.
- **Pages** read `summary` from their data and call pure helpers from
  `$lib/edition.js`. No page has its own `+page.server.js` except the three
  redirects, so navigating within a year reuses the layout data and the
  summary is fetched once per year visited.

### `$lib/api.js`

One function, `apiGet(fetch, path)`: prefixes `API_URL`, uses SvelteKit's
`fetch`, returns parsed JSON on 2xx and throws `error(response.status,
message)` otherwise, with `message` from the body's `error` or `detail` field
when present. A network failure throws `error(502, "API unreachable")`.
The login action switches to a sibling `apiPost(fetch, path, body)` with the
same rules, catching the thrown error to return `fail(...)` as today.
`requestAPI` is removed.

### `$lib/edition.js` (pure, unit-tested)

- `rankedTeams(summary)`: teams sorted by `ranking` then name.
- `disciplineResults(summary, disciplineId)`: results for the discipline with
  `teamName` joined in, sorted by `ranking`, or `null` when the discipline is
  not revealed.
- `teamResults(summary, teamId)`: one row per discipline in id order with
  `disciplineName`, `revealed`, `ranking`, `points`, `time`, `result_type`.
- `findTeam(summary, teamId)` and `findDiscipline(summary, disciplineId)`:
  return the row or `null`. Pages throw `error(404)` on `null`.
- `editionPhase(edition, now)`: `"upcoming"` before `start_date` 09:00 local
  time, else `"started"`.
- `formatDifference(n)`: `+3`, `0`, `-2`.

### `$lib/icons.js`

`import.meta.glob("$lib/img/icons/*.svg", {eager: true, query: "?url",
import: "default"})` keyed by file stem. `iconFor(name)` lowercases the
discipline name, strips spaces and apostrophes, and returns the matching URL
or `default.svg`. Add `darts.svg` and `default.svg`. `cleanString` goes away.

### Header (`routes/Header.svelte`, `routes/menu.svelte`)

Logo, a native `<select>` of years bound to navigation, then Ranking, Teams,
Disciplines, and Photos when `photos_url` is set (external, new tab). The
active year is the `[year]` param, or `latestYear` on `/`, `/login` and error
pages. Changing the year keeps the current section: `/2026/teams` goes to
`/2025/teams`; the hub goes to the hub. The mobile menu lists the same items
with the years as links.

### Hub (`$lib/components/EditionHub.svelte`)

Hero and title as today. Discipline icons are the edition's disciplines via
`iconFor`, split into two columns. Under the hero: host and dates. Then,
by `editionPhase`: a live countdown to `start_date` 09:00 (days, hours,
minutes, seconds, ticking in `onMount`) or a Ranking button to
`/<year>/ranking`. At the bottom, the other editions as year chips linking to
their hubs. The layout's CSS-variable theme swap keys on the hub routes
(`/` and `/[year=year]`) instead of `pathname === "/"`.

### Ranking page

Rows from `rankedTeams`: rank, name, total points, top three styled gold,
silver, bronze. Discipline rail from `summary.disciplines`, each linking to
`/<year>/disciplines/<id>`, dimmed and unclickable when not revealed.

### Disciplines page

Card grid unchanged, icons via `iconFor`, links year-scoped.

### Discipline page

Title, then `disciplineResults`. If `null`: one line, "Results not revealed
yet". Otherwise rows: rank, team name linking to the team page, then
`points pts (+diff)` for points disciplines or the time for timed ones.

### Teams page

Grid sorted by name, full roster on each card. No shuffle.

### Team page

Name, global rank and total points, full roster, then a table from
`teamResults`: discipline, rank, points or time, with an em dash on
unrevealed rows.

### Error page

`routes/+error.svelte` in the site theme showing `$page.status` and
`$page.error.message` with a link back to `/`.

### Login

Keep `login.svelte`; drop the Log in / Sign in toggle and `register.svelte`.
The action uses `apiPost`. Nothing links to `/login`; it stays for the
organiser tools spec.

## Tests

### Backend (`server/olympic_warriors/tests/test_summary.py`)

- 200 without a token; 404 for an unknown year and for an inactive edition.
- Payload keys and the edition fields, including `photos_url`.
- Rosters: only active players of the edition's teams.
- Unrevealed discipline: score fields null; revealed: real values.
- Inactive teams, disciplines and results excluded.
- `getTeamResultsByEdition` returns only that edition's results (regression
  for the filter fix).

### Frontend

Tooling added to `front/package.json`: `vitest`, `jsdom`,
`@testing-library/svelte`, `@testing-library/jest-dom`, with `npm test`
running `vitest run`. `vite.config.js` gets the `test` block (jsdom
environment, `$lib` alias already provided by the SvelteKit plugin). A
`src/lib/fixtures/summary.js` holds one fixture edition with a revealed and
an unrevealed discipline, three teams and their results.

- `edition.test.js`: every helper above, including tie order, the null
  return for unrevealed, the em-dash rows, and both phases of `editionPhase`.
- `icons.test.js`: known name, name with spaces and apostrophe, fallback.
- `api.test.js`: 2xx returns JSON, 404 throws with the body message, network
  failure throws 502.
- Component tests with the fixture: `EditionHub` shows the countdown before
  `start_date` and the Ranking button after; the ranking page lists teams in
  rank order; the discipline page shows the rows for a revealed discipline
  and the "not revealed" line for the other; the team page shows the roster
  and a dash for the unrevealed discipline.

CI (`.github/workflows/test.yml`) gets a `front` job: `npm ci` and
`npm test` in `front/`, not `continue-on-error`. The backend job is unchanged.

### Manual smoke

`npm run build` passes. In the built-in browser against the compose stack:
`/` with a future and a past `start_date`, year switch on `/2026/teams`, an
unrevealed discipline page, a team page, `/1999` giving the themed 404,
mobile viewport for the header.

## Delivery

- Branch `claude/edition-aware-front` in a worktree, off `dev`. Backend and
  front land in one PR into `dev`; the front cannot work without the endpoint.
- On prod deploy: `migrate` runs as usual, then set `photos_url` per edition
  in the admin. No nginx change: the front calls the API server-side.
- Promotion `dev` to `main` is Hugo's call.

## Out of scope

- Rounds, games, events and referees on discipline and team pages.
- Organiser tools and anything that writes through the front.
- A per-edition flag to hide team compositions before the event.
- Blindtest and culture quiz answer entry.
