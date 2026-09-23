# Olympic Warriors: server

This folder holds the Django project behind the Olympic Warriors site. It serves the REST API that the front reads, and the Django admin where organisers prepare an edition. For an overview of the whole repository and the quick start, see the [root README](../README.md).

## Stack

- Python 3.11 (the version in the Docker images)
- Django 4.2 and Django REST Framework 3.15, with token authentication
- drf-spectacular for the OpenAPI schema and the Swagger and ReDoc pages
- PostgreSQL only: there is no SQLite fallback, and the tests need Postgres as well
- pydantic-settings to load the configuration, pandas to parse the registration CSV, whitenoise to serve static files and gunicorn in production

## Layout

```
server/
  manage.py
  requirements.txt       pinned dependencies
  .env.example           template for dev.env and prod.env
  Dockerfile             dev image (the root compose file mounts ./server over its code)
  Dockerfile.prod        production image: code copied in, collectstatic at build, run by gunicorn
  Dockerfile.stage       same, for the stage stack
  olympic_warriors/
    settings.py          Django settings, built from config.py
    config.py            DevConfig / ProdConfig (pydantic-settings)
    models/              Edition, Team, Player, Discipline (with rounds, games, events), one file per discipline
    schedule/            round_robin.py and swiss.py, the game schedulers
    standings.py         every ranking and total of an edition, computed in one pass
    registration.py      registration form CSV -> players and skill ratings
    transfer.py          export and import of a whole edition as JSON
    views.py, urls.py    the API: flat function views and one hand-written URL list
    serializer.py        DRF serializers, including the edition summary
    permissions.py       IsOrganiser (staff only)
    throttling.py        the login throttle
    admin.py             Django admin configuration
    signals.py           creates an API token for every new user
    management/commands/ createsu, create_tokens_for_users, export_edition, import_edition
    migrations/
    tests/               Django tests; tests/fixtures/ holds sample registration CSVs
  static/                images served as Django static files
```

A few files are dead or stale, so don't be misled by them:

- `olympic_warriors/models.py` is shadowed by the `models/` package.
- `server/docker-compose.yml` is an old near-duplicate of the root compose file. Use the root one.
- The `bootstrap5` and `crispy_forms` apps are installed but unused.

## Running it

### With Docker Compose

Run these from the repository root. The [root README](../README.md#getting-started) has the full walkthrough.

```bash
cp server/.env.example server/dev.env
```

```bash
docker compose up --build
```

- **`dev.env`:** set a non-empty `SECRET_KEY`. The rest of the example works as it is with the compose database.
- **What the `server` service runs:** `migrate`, then `runserver 0.0.0.0:3003`. It mounts `./server`, so code changes reload without a rebuild.
- **Editing `dev.env`:** the file is read only at startup, so run `docker compose restart server` afterwards.

### Without Docker

You need Python 3.11 and a PostgreSQL server. First create `server/dev.env` as described above. The easiest way to get a database is to start only the compose database:

```bash
docker compose up -d db
```

The compose `server` service needs `DB_HOST=db` in `dev.env`, so keep it there. Pass `DB_HOST=localhost` as a real environment variable instead, which wins over the file. The port stays `5433`. From `server/`:

```bash
python -m venv venv
```

```bash
source venv/bin/activate
```

```bash
pip install -r requirements.txt
```

```bash
DB_HOST=localhost python manage.py migrate
```

```bash
DB_HOST=localhost python manage.py runserver 0.0.0.0:3003
```

- **Working directory:** run `manage.py` from `server/`, because the configuration reads `dev.env` from the current directory.
- **Port:** keep 3003. That is the port the front's `API_URL` points at.

## Configuration

`ENV` picks the configuration class and its file:

| `ENV` | Class | File |
| --- | --- | --- |
| `dev`, or unset | `DevConfig` | `dev.env` |
| `prod` | `ProdConfig` | `prod.env` |

Any other value leaves the configuration empty, and Django fails to start. A real environment variable always overrides the same key in the file. That override assigns the raw string without validation, so only override string and number keys this way. As an environment variable, `DEBUG=False` is a non-empty string and therefore true, and a JSON list stays a string. Change booleans and lists in the file. Both files are gitignored, and `.env.example` is the template for both.

| Variable | Default | Notes |
| --- | --- | --- |
| `SECRET_KEY` | required | Must not be empty. |
| `DEBUG` | required | `True` in dev. |
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASS`, `DB_PORT` | required | The PostgreSQL connection. The compose database is `db`, port `5433`. |
| `DATABASE_URL` | unset | Replaces the `DB_*` connection when set. It is read from the real environment only, never from the env file, and the loader still requires the `DB_*` keys. |
| `LOG_FILE` | `asset_monitor.log` | Path relative to `server/`. The example uses `logs/olympic_warriors.log`. The settings create the folder at startup when it is missing (it is gitignored). |
| `LOG_LEVEL_CONSOLE`, `LOG_LEVEL_FILE` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `SU_USERNAME`, `SU_PASSWORD` | `admin` / `password` | Read by `createsu`. Set your own in `prod.env`. |
| `ALLOWED_HOSTS` | `["*"]` | A JSON list. It must include `server`, the hostname the front container uses, or every front page fails with a 400. |
| `CSRF_TRUSTED_ORIGINS` | `["https://*", "http://*"]` | A JSON list. |
| `LOGIN_THROTTLE_RATE` | `5/min` | Login attempts per client IP, counted across `/auth/token/` and `/admin/login/` together. |
| `NUM_PROXIES` | `1` | How many `X-Forwarded-For` entries to trust when identifying the client IP (see [Login throttle](#login-throttle)). |
| `BASE_URL` | `localhost` | Loaded but not used. |

Some settings are not configurable:

- **Language and time zone:** Django runs in French (`LANGUAGE_CODE = "fr"`) on UTC.
- **Media:** uploads (registration forms, rule PDFs) go to `mediafiles/`. Django serves them only when `ENV=dev`.
- **Cache:** the throttle counts live in a file cache in the system temp directory, so every gunicorn worker of a container shares them.

## Domain model

| Model | What it holds |
| --- | --- |
| `Edition` | One year of the event: `year` (unique), `host`, `start_date` / `end_date`, an optional `registration_form` CSV and an optional `photos_url`. The front and the export and import commands address an edition by year, not by id. |
| `Team` | A team of one edition. `final_rank` is an optional finishing order, entered by hand for an old edition that has no result data. |
| `Player` | A Django `User` taking part in an edition. It holds a team and a global `rating` from 1 to 10. |
| `PlayerRating` | One skill rating of a player, from the registration form. |
| `Discipline` | A concrete base model. Each discipline is a subclass with its own table (multi-table inheritance). See the field list below. |
| `TeamResult` | A team's result in a discipline: `points` or `time`. A `null` value means no result yet. |
| `TeamSportRound` | A round of games in a discipline: `order`, and `is_over`. |
| `Game` | Two teams, `score1` / `score2`, the refereeing team and `is_played`. |
| `GameEvent`, `RugbyEvent`, `DodgeballEvent` | Per-player actions in a game (try, tackle, hit, catch, and so on). They roll up into the game score. The site does not use them today. |
| `Blindtest`, `BlindtestRound`, `BlindtestGuess` | The blindtest, its rounds, and each team's artist and song guess per round. |

`Discipline` has these fields:
- `result_type`: points, time or none.
- `pairing_system`: `NO` (none), `RR` (round robin) or `SW` (Swiss).
- `max_rounds`.
- `reveal_score`: whether the scores are public yet.
- `rules`: an optional PDF.

Nearly every model has an `is_active` flag, used for soft deletes. The admin changelists show only active rows by default. Inactive rows stay in the database, and every computation ignores them.

### Business rules live in `save()`

Business rules live in the models' `save()` overrides, not in views, signals or services. The one exception is `signals.py`, which creates API tokens. The consequence is that `bulk_create`, `queryset.update()` and `loaddata` skip all of these rules:

- **A discipline subclass's `save()`** sets `name` and `result_type` on the first save.
- **`Discipline.save()`** creates a `TeamResult` for every active team on the first save.
  - `points` starts at `0` only for a points discipline with a pairing system, because its games compute the points.
  - Every other result starts at `null`, so "no result yet" is never a zero.
  - The same method also starts the scheduling (see [Scheduling](#scheduling)).
- **`Game.save()`** recomputes the `TeamResult.points` of both teams from the discipline's active, played games of active rounds: 3 points per win and 1 per draw.
  - Editing a score, the `is_played` flag or the teams, or deactivating a game, all resync the points.
  - An unplayed game counts for nothing.
  - Points of a discipline without games are entered by hand and never recomputed.
- **Closing a Swiss round** (setting `is_over`) schedules the next round.
- **`BlindtestGuess.save()`** adds 1 point to the team's blindtest result for each correct artist or song, and takes it back if the flag is unset. A guess for a team of another edition is refused.

Some admin and validation code matches on the discipline **name string**, for example which event inlines a game shows and `RugbyEvent` validation. Renaming a discipline therefore breaks its scoring.

### Standings

Rankings are never stored. `standings.compute_standings(edition)` computes every ranking and total of an edition in one pass, from three queries:

1. **Discipline rank.** A result is ranked only once its discipline is revealed and it has a score.
   - Points disciplines rank by points. Ties are broken by the points difference, summed from the scores of active, played games.
   - Time disciplines rank by time.
   - Tied results share a rank.
2. **Global points.** A rank earns `registered − rank + 1` points, where `registered` counts the discipline's active results of active teams. First place adds a 2-point bonus, and second and third place add 1.
3. **Team total and team rank.** A team's total is the sum of its global points over the active disciplines. Teams rank by that total.

When any team of an edition has a `final_rank`, the edition counts as manual. The team ranking then follows that stored order, and every total is `null`.

The model properties `TeamResult.ranking`, `Team.total_points` and similar recompute the whole edition on every access. To read many rows, call `compute_standings` once instead of reading those properties in a loop.

## Scheduling

When a discipline gets a pairing system, either at creation or later while it still has no round, the scheduler creates its games. Both schedulers create games as unplayed.

- **Round robin** (`schedule/round_robin.py`) generates every round up front with the circle method. It assigns a refereeing team from the teams not playing. `max_rounds` defaults to one full round robin.
- **Swiss** (`schedule/swiss.py`) generates only the next round. It runs again each time a round is closed. `max_rounds` defaults to log2 of the team count, rounded up.

## API

The API has about 70 function views in `views.py`, wired in one hand-written list in `urls.py`. There is no router and no `/api/` prefix. Serializers are mostly `fields="__all__"` model serializers.

### Authentication

`POST /auth/token/` with `{"username": ..., "password": ...}` returns `{"token": ...}`. Send the token on later requests as `Authorization: Token <token>`. Every user gets a token automatically when they are created. Run `create_tokens_for_users` to backfill tokens for users created before that.

Every endpoint requires a token unless it is listed as public below.

### Public endpoints

| Endpoint | Returns |
| --- | --- |
| `GET /editions/` | Every active edition |
| `GET /edition/<id>/` | One edition |
| `GET /edition/year/<year>/summary/` | The whole edition in one payload (see below) |
| `GET /disciplines/`, `/discipline/<id>/`, `/disciplines/<edition_id>/` | Disciplines |

`/auth/token/`, the admin login page and `/api/schema/*` need no token either. Of the read endpoints, the front uses only `/editions/` and the summary. It also calls `/user/current/`, `/auth/token/` and the organiser endpoints below.

The summary returns the edition's active rows: `edition`, `disciplines`, `teams` (each with its roster, `ranking` and `total_points`), `results`, `rounds` and `games`. Until a discipline is revealed, its scores are hidden:

- Its results come back with `ranking`, `points`, `time`, `points_difference` and `global_points` set to `null`.
- Its games come back with `score1` and `score2` set to `null`. Pairings, referees and `is_played` stay visible.

With a staff token, stored points, times and game scores stay visible before the reveal, so an organiser can check them. The computed ranking fields stay `null` until the reveal, even for staff.

### Organiser endpoints

These endpoints are for staff users only. They return 401 without a token, 403 for a non-staff user, and 409 for anything outside the latest active edition.

| Endpoint | Body |
| --- | --- |
| `PATCH /game/<id>/score/` | `{"score1": 12, "score2": 9, "is_played": true}` |
| `PATCH /result/<id>/value/` | `{"points": 5}` or `{"time": "12:34"}` (`mm:ss`). Send `{"points": null}` or `{"time": null}` to clear. Only for a discipline without rounds. |
| `PATCH /discipline/<id>/reveal/` | `{"reveal_score": true}` |
| `PATCH /round/<id>/close/` | No body. Refused until every game of the round is played. For a Swiss discipline it schedules the next round. |

All four go through the models' `save()`, so league points and Swiss rounds update exactly as they do from the admin.

### Login throttle

`/auth/token/` and the admin login share one per-IP bucket of `LOGIN_THROTTLE_RATE` attempts. Every attempt counts, whether it fails or succeeds. Past the limit, the API returns a 429 with `Retry-After`, and the admin shows an error message instead of checking the password.

The client IP is the last `X-Forwarded-For` entry, as set by nginx, or by the front for a login through the site. With `NUM_PROXIES=1`, that is only safe while every request reaches Django through nginx or the front.

### Schema

- `/api/schema/`: the OpenAPI document
- `/api/schema/swagger/`: Swagger UI
- `/api/schema/redoc/`: ReDoc

### Writing a view

Put per-view policy decorators such as `@permission_classes` **below** `@api_view`. Placed above it, the pinned DRF 3.15 silently ignores them, and the view falls back to `IsAuthenticated`. For an organiser endpoint, that would let any logged-in player write. DRF 3.16+ raises a `TypeError` at import instead. `test_public_endpoints` and `test_organiser` catch the first case.

## Admin

The Django admin at `/admin/` is where an edition is prepared. Any staff account can log in there, and the same account unlocks the organiser tools on the site. Use it to:

- **Set up the edition.** Create the edition and upload its registration CSV. That creates the players, as described in the next section.
- **Build the teams.** Create the teams and assign players to them.
- **Add disciplines** for the edition. Each discipline type has its own admin entry and sets its own name and result type. You choose the pairing system and the maximum number of rounds. Create the teams first: a discipline creates results only for the teams that exist when it is created.
- **Fix games from the changelist.** `score1`, `score2` and `is_played` are editable directly in the list.
- **Enter the rest by hand:** blindtest guesses, results of disciplines without games, and `final_rank` for an old edition without results.

The admin login counts against the same login throttle as the API.

## Registration import

Saving an edition with a new `registration_form` CSV runs `Edition.create_players_from_registration_form`, which calls `registration.py`.

- **Column matching.** Columns are found by stable fragments of their headers: the bracketed skill criterion such as `[Cardio]`, the start of the global-level question, `Prénom et Nom`, and an optional `Adresse e-mail`. Rewording the form from one year to the next needs no code change.
- **Skill sets.** The set of skills is versioned in `FORM_PROFILES`: `"2024"` and `"2025"` (the 2025 set is also used for 2026). The first profile whose criteria all match wins. A form with a new set of skills needs a new profile, and each skill `id` is limited to 4 characters.
- **Linking players.** Returning players are matched by a username derived from their name, with accents kept.
- **Re-uploading.** The upload creates or updates players and ratings, so a corrected form refreshes the ratings without creating duplicates. The whole import runs in the same transaction as the edition save.

`olympic_warriors/tests/fixtures/` has a sample CSV for each profile.

## Management commands

Run these inside the container, for example `docker compose exec server python manage.py <command>`.

| Command | What it does |
| --- | --- |
| `createsu` | Creates a superuser from `SU_USERNAME` / `SU_PASSWORD`. It does nothing if that user already exists, and prints "Superuser has been created." either way. |
| `create_tokens_for_users` | Creates the missing API tokens for existing users. |
| `export_edition <year> --out <file>` | Writes an edition to JSON, with no database ids. |
| `import_edition <file> [--dry-run] [--replace]` | Imports an edition. `--dry-run` reports what would happen and rolls back. `--replace` first deletes the edition with the same year (users are kept). |

The exported file contains player names and emails. Write it as `server/edition-<year>.json` (in the container, `--out /server/edition-2026.json`), because that is the only name the repository ignores. Delete the file once you have finished with it.

### Edition transfer

`export_edition` and `import_edition` move a whole edition between databases, typically from local to production.

- **Export.** The document carries no database ids: users are referenced by username, and rows by throwaway `_id`s.
- **Import.** Rows are inserted raw, so no `save()` rule runs. Existing users are reused by username, and missing ones are created with a random password.
- **Media.** Uploaded files are not included. Copy them into the `mediafiles` volume separately.

The runbook is in [the edition transfer spec](../docs/superpowers/specs/2026-09-19-edition-transfer-design.md).

## Tests

The tests need the compose Postgres. Django creates and drops its own `test_` database, so your dev data is not touched.

```bash
docker compose exec server python manage.py test
```

```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_summary
```

The tests live in `olympic_warriors/tests/`, one file per area: `test_summary`, `test_organiser`, `test_standings`, `test_scheduling`, `test_registration`, `test_transfer`, `test_blindtest`, `test_auth_token`, `test_admin_login`, and so on. `test_summary.py` and `test_organiser.py` pin their query counts (`SUMMARY_QUERIES`, `RESULT_PATCH_QUERIES`), so a view that queries once per row fails the suite.

CI does not run these tests (the steps are commented out in `.github/workflows/test.yml`), so run them before you merge.

### Lint

CI runs pylint as an advisory check. There is no `.pylintrc`. From the repository root:

```bash
pip install pylint pylint-django
```

```bash
pylint --load-plugins pylint_django --ignore=lib server/
```

## Adding a discipline

1. **Create the model** in `models/<Name>.py` as a subclass of `Discipline`. Override `save()` to set `self.name` and `self.result_type` when `self.pk is None`, then call `super().save()`.
   - `models/Relay.py` is the minimal example.
   - `models/Rugby.py` also has a `GameEvent` subclass and scoring.
2. **Export it** from `models/__init__.py`.
3. **Register it** with `site.register(<Name>, DisciplineAdmin)` in `admin.py`.
4. **Create its table.** Write the migration, then restart the server, which applies migrations when it starts:

   ```bash
   docker compose exec server python manage.py makemigrations
   ```

   ```bash
   docker compose restart server
   ```

5. **Add it to the front.** Add an SVG icon and a French name there, as described in [front/README.md](../front/README.md#adding-a-discipline-icon). A front test fails until both exist.

## Production

`docker-compose.prod.example.yml` at the repository root is the template. It runs `Dockerfile.prod` under gunicorn on port 3003, bound to `127.0.0.1`, with nginx in front.

- **The image contains the code.** `Dockerfile.prod` copies `server/` into the image, `prod.env` included. After changing code or `prod.env`, rebuild the image: a restart is not enough. The build itself runs `collectstatic` with `ENV=prod`, so `prod.env` must be in the build context with at least `SECRET_KEY`, `DEBUG` and the `DB_*` keys. It does not connect to the database.
- **Static files.** whitenoise serves them from `staticfiles/`. The production compose file mounts a named volume there, and Docker fills that volume from the image only when it is created, so rebuilding does not refresh it. After a deploy that changes static files, run `docker compose exec server python manage.py collectstatic --no-input`.
- **Migrations are manual.** The production command only starts gunicorn, so after a deploy that adds migrations, run `docker compose exec server python manage.py migrate`. The first time, also run `createsu`.
- **Set the superuser before `createsu`.** Put your own `SU_USERNAME` and a strong `SU_PASSWORD` in `prod.env` first. Otherwise `createsu` creates `admin` with the password `password`. It only creates a missing user and never updates a password, so after changing `SU_PASSWORD`, run `docker compose exec server python manage.py changepassword <username>` instead.
- **Media files** (`mediafiles/`) live in a Docker volume shared with nginx, which serves them.
- **nginx must set `X-Forwarded-For`** (`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`) on the locations that proxy to the server and to the front. Otherwise the login throttle trusts an IP the client chose.

## License

Apache License 2.0, see [LICENSE](LICENSE).
