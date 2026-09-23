# Organiser tools

**Date:** 2026-09-23
**Status:** approved in conversation, awaiting spec review
**Scope:** `server/` (four write endpoints, the staff-aware summary, one serializer
field, a data fix) and `front/` (session, controls on the discipline page).

## Goal

On the day, an organiser opens the same public pages as everyone else on a
phone at the pitch and, being logged in, can score a game, enter the results
of a discipline without games, reveal a discipline and close a Swiss round.
Setup work (editions, teams, players, disciplines, schedules) stays in the
Django admin.

## Decisions taken

- **Actions on the site:** score a game (two scores, played flag), enter a
  points or time result per team for a discipline without games, reveal or
  hide a discipline, close a Swiss round. Nothing else.
- **Who:** Django's staff flag. A user who can log into the admin is an
  organiser. No new role.
- **Where:** inline on the public discipline page, rendered only for staff.
  An anonymous visitor gets today's page byte for byte. The team and
  ranking pages stay read-only.
- **How:** SvelteKit form actions, like `/login` and `/lang`. The token never
  reaches the browser, the API needs no CORS.
- **Only the latest edition** (highest `year`) can be edited from the site,
  enforced by the API. Older editions go through the admin.
- **What staff see before reveal:** the scores of every game and the stored
  points or time of every result, so they can check and edit. The ranking
  of a hidden discipline (`ranking`, `points_difference`, `global_points`)
  stays null for everyone until it is revealed.
- **Scores are overwritten** by the sheet. A game is scored either from the
  site or through game events, never both: events add on top of the stored
  score, and they are an unused, admin-only feature today (the backend is
  ready, the UX is a separate future project).
- **Close round** exists only on Swiss disciplines, where it schedules the
  next round; on a round robin it would only set a flag. `pairing_system`
  joins the summary's discipline rows so the page knows.
- **Times** are entered as `mm:ss`, stored as `00:mm:ss`, shown as `mm:ss`
  with the hours only when they are not zero. The six 2026 crossfit rows
  stored as `mm:ss:00` get a one-off fix on prod.
- **Reveal is always allowed**; the staff bar says what is missing.
- **Last write wins**; no version check on saves.
- **Result values:** points are integers zero or more; times `mm:ss` with
  seconds below 60; an empty field clears the value (the team shows a dash).
  A fresh result of a discipline without games has `points = None` and a
  timed one `time = None` (`Discipline.register_teams` no longer writes `0`
  and `00:00:00` there), so "no result yet" is a null, never a zero; a
  discipline with games keeps `points = 0` until a game is played.
- **Sheet on phones, dialog on desktop**, same component, split at 1000px.
- **Out of scope:** audit trail of who changed what, reopening a round,
  game events, controls on the team and ranking pages, a login link in the
  nav (organisers type `/login`).

## API

### Permission

`olympic_warriors/permissions.py` defines `IsOrganiser`: the request user is
authenticated and `is_staff`. Every write view below carries
`@permission_classes([IsOrganiser])` under its `@api_view`, so no token is
401 and a player's token is 403.

Each write view also checks the edition: the target row must belong to the
active edition with the highest `year` (`Edition.objects.filter(is_active=True).order_by("-year").first()`),
else `409 {"error": "Only the latest edition can be edited"}`. The helper
`latest_edition()` lives in `models/Edition.py`.

Every write goes through the model's `save()` so the existing logic runs:
`Game.save()` recomputes league points, `TeamSportRound.save()` schedules
the next Swiss round.

### Endpoints

| Method and path | Body | Effect | Errors |
|---|---|---|---|
| `PATCH /game/<id>/score/` | `{"score1": int, "score2": int, "is_played": bool}` (all three required) | sets the three fields, saves | 400 on a missing field, a negative or non-integer score; 404 on an inactive or unknown game; 409 outside the latest edition |
| `PATCH /result/<id>/value/` | `{"points": int \| null}` for a `PTS` discipline, `{"time": "mm:ss" \| null}` for a `TIM` one | sets the value (`null` clears it), saves | 400 on the wrong field for the type, a negative or non-integer points value, a time not matching `^\d{1,3}:[0-5]\d$`, or a `NON` discipline; 400 when the discipline has rounds (its points are computed); 404; 409 |
| `PATCH /discipline/<id>/reveal/` | `{"reveal_score": bool}` | sets the flag, saves | 400 on a missing flag; 404; 409 |
| `PATCH /round/<id>/close/` | none | sets `is_over = True`, saves (which schedules the next Swiss round) | 409 `{"error": "Some games are not played yet"}` while an active game of the round is unplayed; 409 when already over; 404; 409 outside the latest edition |

Each success returns the row as the summary serialises it for staff
(`SummaryGameSerializer`, `SummaryResultSerializer`, `SummaryDisciplineSerializer`,
`SummaryRoundSerializer`), status 200. Time input `mm:ss` is stored as
`datetime.time(mm // 60, mm % 60, ss)` so minutes above 59 roll into hours.

The URL list in `urls.py` gains the four paths next to their read siblings.

### Staff-aware summary

`getEditionSummary` stays `@permission_classes([AllowAny])`. It passes
`staff=request.user.is_staff` (False for anonymous) into the serializer
context, next to `totals`. Behaviour by `reveal_score` and `staff`:

| Field | public, hidden | staff, hidden | revealed (anyone) |
|---|---|---|---|
| game `score1`, `score2` | null | value | value |
| result `points`, `time` | null | value (null when unset) | value |
| result `ranking`, `points_difference`, `global_points` | null | null | value |

`SummaryDisciplineSerializer` gains `pairing_system` (the `PairingSystem`
value, `NONE`, `RR` or `SW`).

`/user/current/` keeps `UserSerializer` and that serializer gains `is_staff`
(fields stay an explicit tuple: no password hash).

### Time display

A revealed time result is serialised as stored (`HH:MM:SS`); the front
formats it. Nothing else changes in the API.

### Data fix

On prod, once, in `manage.py shell`, for the 2026 crossfit results whose
seconds are zero and hours non-zero: `time = time(0, t.hour, t.minute)`.
The command is in the deploy notes of the PR and the runbook section
below.

### Tests

`tests/test_organiser.py`: for each endpoint, no token 401, player token 403,
staff token happy path; the edition guard 409; the validation 400s listed
above; close round 409 on a partial round and a Swiss next round scheduled
on a full one; the result endpoint refusing a discipline with rounds.
`test_summary.py` gains: staff summary on a hidden discipline shows scores
and stored points but null ranking; public summary unchanged;
`pairing_system` present.

## Front

### Session

- `/login` stores the bare token in a cookie named `token` (httpOnly,
  secure off localhost, SameSite lax so an organiser arriving from an outside
  link is still logged in, path `/`, one week). The old
  `Authorization` cookie name and its `Bearer` prefix go; the API wants
  `Authorization: Token <key>` and `api.js` builds that header from the
  cookie value when one is given.
- `/logout/+page.server.js`: a default action deleting the cookie and
  303-redirecting to the local `redirectTo` it was given (same guard as
  `/lang`), a `load` that 303s to `/`.
- The root `+layout.server.js` reads the cookie. With one, it calls
  `/user/current/` with the token: `is_staff` true gives `organiser: true`;
  a 401 or 403 deletes the cookie and gives `organiser: false`; a player's
  token (200, not staff) and any other failure give `organiser: false` and
  keep the cookie. Without a cookie,
  `organiser: false`. The layout returns `organiser` next to `editions`,
  `latestYear` and `locale`, and `+layout.svelte` puts it in context under
  `ORGANISER` (exported from `$lib/session.js` with `useOrganiser()`, the
  same shape as `I18N`/`useLocale`).
- The `[year=year]` layout fetches the summary with the token when there
  is one, so staff get the staff-aware payload. It also returns
  `editable: organiser && Number(params.year) === latestYear`, the one
  flag the discipline page uses to render controls.
- `Header.svelte`: for an organiser, an `ORGA` pill in the display face,
  accent border, left of the language switch; it is a form posting to
  `/logout` with the hidden `redirectTo`, `aria-label` `orga.logout`.

### The discipline page (`disciplines/[id]`)

Rendered only when `data.editable`:

- **Staff bar** (`StaffBar.svelte`) between the title and the rail. Hidden
  discipline: `orga.hidden` (`Résultats masqués pour le public`), the
  missing count, and a `orga.reveal` button. Revealed: `orga.public`
  (`Résultats publics`) and a `orga.hide` button, no count. The missing count:
  `discipline.toPlay` with the unplayed games for a discipline with rounds,
  `orga.missingResults` (`{n} équipe sans résultat` / `{n} équipes sans
  résultat`) for one without; nothing when nothing is missing. One form
  posting to the `reveal` action with the target value.
- **Results entry** for a discipline without rounds: replaces the results
  list (or the not-revealed line). One line per team, `data-testid="result-line"`,
  in rank order when revealed else by name: the team name, a field
  (`inputmode="numeric"` for points; for time a plain text field with the
  default keyboard, since the numeric keypad has no colon, placeholder
  `mm:ss` and pattern `[0-9]{1,3}:[0-5][0-9]`), a `orga.save` button.
  Each line is a form posting to the `result` action with the result id.
  For a discipline with rounds the results list stays as it is (points are
  computed).
- **Game rows** get `onEdit`: `GameRow` renders its pairing as a `<button
  type="button">` when the callback is set, with the score inside, and the
  page opens `ScoreSheet` for that game. Public rows are unchanged.
- **`ScoreSheet.svelte`**: props `game` (a `disciplineSchedule` game),
  `roundNumber`, `open`, `error`. A `div` with `role="dialog"` and
  `aria-modal` over a backdrop (jsdom has no `<dialog>` support; no focus
  trap, the backdrop covers the page and Escape closes): below 1000px it is a bottom
  sheet (full width, rounded top corners, slides up), from 1000px a centred
  420px dialog. Contents: a label line `Tour n · arbitre : X`, one line per
  team with the name, a minus button, a number field (`inputmode="numeric"`,
  min 0), a plus button; a `joué` switch (a checkbox styled as a switch,
  checked when the game is played, and checked by default when the sheet
  opens on an unplayed game); `orga.cancel` and `orga.save`. One form
  posting to the `score` action with the game id, `use:enhance`. The
  steppers change the field locally and never go below 0. Escape, the
  backdrop and cancel close it. Focus goes to the first field on open and
  back to the row's button on close (the page keeps the opener).
- **Close round**: on a Swiss discipline, when every game of a round is
  played and the round is not over, the round header shows a
  `orga.closeRound` button (`Clore le tour`) posting to the `close` action
  with the round id. A closed round shows `orga.roundClosed` (`Terminé`) in
  its label instead of the game count.
- **Errors**: an action returns `fail(status, { action, id, error: key })`
  where `key` is one of `orga.error.unauthorised` (401, `Session expirée,
  reconnectez-vous`), `orga.error.forbidden` (403), `orga.error.invalid`
  (400, `Valeur refusée`, also when the action itself refuses a non-numeric
  or negative value),
  `orga.error.conflict` (409, `Impossible pour cette édition ou ce tour`),
  `orga.error.failed` (anything else). The control that failed shows the
  line under itself; the sheet stays open on failure.

### Actions (`disciplines/[id]/+page.server.js`)

`score`, `result`, `reveal`, `close`. Each: reads the `token` cookie, returns
`fail(401, …)` without one; reads the form fields; calls `apiPatch(fetch,
api(path), body, token)`; on an `error()` thrown by `api.js` catches it and
returns `fail(status, { action, id, error })`; on success returns
`{ ok: true, action, id }`. With `use:enhance`, SvelteKit re-runs the loads
after a successful action, so the summary is fetched again and the page
shows the new state; without JavaScript the page reloads. `apiPatch` joins
`apiGet`/`apiPost` in `api.js`, taking an optional token that becomes
`Authorization: Token <key>`.

### Time formatting

`formatTime(hhmmss)` in `edition.js`: `"00:13:15"` → `13:15`,
`"01:02:03"` → `1:02:03`, `null` → `null`. Used by the discipline page
result rows, the results entry field value, and the team page tiles.

### Dictionary

Keys added to both files (French first):

| Key | fr | en |
|---|---|---|
| `orga.pill` | Orga | Orga |
| `orga.logout` | Se déconnecter | Log out |
| `orga.hidden` | Résultats masqués pour le public | Results hidden from the public |
| `orga.public` | Résultats publics | Results are public |
| `orga.reveal` | Dévoiler | Reveal |
| `orga.hide` | Masquer | Hide |
| `orga.missingResults` | `{one: '{n} équipe sans résultat', other: '{n} équipes sans résultat'}` | `{one: '{n} team without a result', other: '{n} teams without a result'}` |
| `orga.edit` | Saisir le score | Enter the score |
| `orga.played` | Joué | Played |
| `orga.save` | Enregistrer | Save |
| `orga.cancel` | Annuler | Cancel |
| `orga.closeRound` | Clore le tour | Close the round |
| `orga.roundClosed` | Terminé | Done |
| `orga.timeHint` | mm:ss | mm:ss |
| `orga.error.unauthorised` | Session expirée, reconnectez-vous | Session expired, log in again |
| `orga.error.forbidden` | Réservé aux organisateurs | Organisers only |
| `orga.error.invalid` | Valeur refusée | Value refused |
| `orga.error.conflict` | Impossible pour cette édition ou ce tour | Not possible for this edition or round |
| `orga.error.failed` | Échec de l'enregistrement | Could not save |

### Tests

- `session.test.js`: `useOrganiser` default false.
- Root layout load with a fake `fetch`: no cookie, staff, non-staff (cookie
  deleted), API down (cookie kept, `organiser` false).
- `[year=year]` layout load: `editable` true only for staff on the latest year.
- `api.test.js`: `apiPatch` sends the method, the JSON body and the token
  header.
- `ScoreSheet.test.js`: renders both teams and the values, the steppers
  move the fields and stop at 0, the switch defaults on for an unplayed
  game, the form carries the game id.
- `GameRow.test.js`: a button around the pairing only with `onEdit`.
- `StaffBar.test.js`: hidden and revealed states, the missing counts, the
  posted value.
- Discipline page tests with `editable: true`: the bar, the row buttons,
  the result lines for a discipline without rounds (values from the staff
  payload, empty for null), the close button only on a complete Swiss
  round, `Terminé` on a closed round; with `editable: false`: none of it,
  same text shapes as today. One French render of the bar and a result line.
- Action tests with a fake `fetch`: each action's happy path body and
  header, 401 without a cookie, the API error mapped to the right key.
- `Header.test.js`: the pill and the logout form for an organiser, nothing
  otherwise. `logout` action test: cookie deleted, local redirect.
- `edition.test.js`: `formatTime` cases.

### Docs

CLAUDE.md: the Auth paragraph rewritten (token cookie, `/logout`, organiser
resolution, `editable`), a new "Organiser tools" paragraph (the four
actions, `ScoreSheet`, `StaffBar`, the latest-edition rule, the
events-or-sheet rule, the time convention), the summary paragraph updated
for the staff variant and `pairing_system`, the API paragraph updated for
the four write views and `IsOrganiser`.

## Runbook

After deploy, once, on the prod server:

```bash
docker compose -f docker-compose.prod.yml exec server python manage.py shell -c "
from datetime import time
from olympic_warriors.models import TeamResult
rows = TeamResult.objects.filter(discipline__result_type='TIM', discipline__edition__year=2026, time__isnull=False)
for r in rows:
    if r.time.second == 0 and r.time.hour:
        r.time = time(0, r.time.hour, r.time.minute); r.save(update_fields=['time']); print(r.team.name, r.time)
"
```

Then, since this task made a fresh result's points/time null instead of a zero, run
one more guarded one-off for the latest edition, after the fix above: a time
discipline's stored `00:00:00` is unambiguous ("no result yet" under the old code) and
is nulled outright, but `points=0` in a discipline without games can be either a real
zero or the old placeholder, so it is only listed for an organiser to check by hand.

```bash
docker compose -f docker-compose.prod.yml exec server python manage.py shell -c "
from datetime import time
from olympic_warriors.models import TeamResult
TeamResult.objects.filter(discipline__edition__year=2026, discipline__result_type='TIM', time=time(0, 0, 0)).update(time=None)
zero_points = TeamResult.objects.filter(discipline__edition__year=2026, discipline__pairing_system='NO', discipline__result_type='PTS', points=0)
for r in zero_points:
    print(r.team.name, r.discipline.name)
"
```

Then log in on the site as a staff user, open the latest edition's
discipline page, and check the `ORGA` pill, the bar and one score save.
