# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Olympic Warriors is a tool for running a multi-discipline sports event (rugby, dodgeball, blindtest, relay, etc.) across yearly "editions". Two deployable parts:

- `server/` — Django 4.2 + Django REST Framework API (single app `olympic_warriors`), PostgreSQL only (no sqlite fallback).
- `front/` — SvelteKit 2 / Svelte 4 (plain JS, no TypeScript; Vitest unit and component tests, no lint tooling) served via `adapter-node`.

`client/` is an empty leftover directory. `nginx/nginx.conf` is a dev-only config that no compose file references; production nginx config lives on the host under `nginx/user_conf.d` (not in the repo).

## Commands

Everything runs through the root `docker-compose.yml` (server on 3003, Postgres on **5433**, pgadmin on 5051, front on 5173). `server/docker-compose.yml` is a stale near-duplicate on port 5432; ignore it.

```bash
docker compose up --build              # migrate + runserver + vite dev
docker compose exec server python manage.py test                       # all Django tests (needs Postgres)
docker compose exec server python manage.py test olympic_warriors.tests.test_players.TestPlayersAPI.test_get_players
docker compose exec server python manage.py makemigrations
docker compose exec server python manage.py createsu                   # superuser from SU_USERNAME/SU_PASSWORD
docker compose exec server python manage.py create_tokens_for_users    # backfill DRF tokens
docker compose exec server python manage.py export_edition 2026 --out /server/edition-2026.json   # edition -> JSON without ids
docker compose exec server python manage.py import_edition /server/edition-2026.json --dry-run     # add --replace to overwrite that year
pylint --load-plugins pylint_django --ignore=lib server/               # what CI runs (advisory, no .pylintrc)
```

Front (inside `front/`): `npm run dev`, `npm run build`, `npm run preview`. There is no `check` or `lint` script. `npm test` runs Vitest once over `src/**/*.test.js` (`vite.config.js`: jsdom, `src/setupTests.js` loading `@testing-library/jest-dom/vitest`, components rendered with `@testing-library/svelte`); summary fixtures live in `front/src/lib/fixtures/summary.js`.

Required env files, both gitignored:
- `server/dev.env` (copy `server/.env.example`); `ENV=prod` selects `server/prod.env`. Any real env var overrides the file.
- `front/.env` with `API_URL=http://server:3003` (in compose) or `http://localhost:3003`. `API_URL` is `$env/static/private`, so it is baked in at build time and a missing file fails the build.

CI (`.github/workflows/test.yml`) has two jobs. `test` runs pylint with `continue-on-error` and boots the compose stack; its migrate/test steps are commented out, so the Django side is not a gate. `front` (Node 22) runs `npm ci`, writes a throwaway `.env`, then `npm test` and `npm run build` — that one does gate, so a failing front test or build fails the workflow.

## Backend architecture

**Business logic lives in model `save()` overrides, not views, signals, or services.** Bulk operations (`bulk_create`, `queryset.update()`, `loaddata`) bypass all of it.

Domain: `Edition` owns `Team`s, `Player`s (wraps `auth.User` plus rating facets) and `Discipline`s. `Edition.year` is **unique** — it is the key the front routes and the export/import commands address an edition by, not the pk — and `Edition.photos_url` is an optional link to an external album (migration `0027`) that the front turns into a Photos tab. `Discipline.teams` is M2M through `TeamResult` (points or time, per `ResultTypes`). Team sports have `TeamSportRound`s of `Game`s; `GameEvent` subclasses (`RugbyEvent`, `DodgeballEvent`) log per-player actions and roll scores up into `Game.score*`, which `Game.save()` turns into `TeamResult.points` **as deltas** (a score edited outside that path desyncs results permanently). Rankings are computed properties on `TeamResult` and `Team`, gated by `Discipline.reveal_score`; points disciplines break ties on `TeamResult.points_difference`, which is summed on the fly from active `Game` scores by `annotate_points_difference()` in `models/Team.py` (never stored, so it cannot desync). `Discipline.get_ranking()` is a dead stub.

**Adding a discipline** (Django multi-table inheritance, `Discipline` is concrete):
1. `models/<Name>.py`: subclass `Discipline`, override `save()` to set `self.name` and `self.result_type` when `self.pk is None`, then call `super().save()`. See `models/Relay.py` for the minimal version, `models/Rugby.py` for one with a `GameEvent` subclass and scoring.
2. Export it from `models/__init__.py`.
3. `site.register(<Name>, DisciplineAdmin)` in `admin.py`.
4. `makemigrations` (each discipline gets its own table).
5. Add a matching SVG in `front/src/lib/img/icons/` — `iconFor()` in `front/src/lib/icons.js` derives the file stem from the discipline name, so a missing icon falls back to `default.svg`. Add the name to `DISCIPLINE_NAMES` in `front/src/lib/icons.test.js`, which fails until the icon exists.

The base `Discipline.save()` creates a `TeamResult` per active team on first save and dispatches scheduling by `pairing_system`, both on creation and when the pairing system is later set on a discipline with no round yet: round robin (`schedule/round_robin.py`, a full circle-method round robin up front with referee assignment, `max_rounds` defaulting to a single round robin) or Swiss (`schedule/swiss.py`, next round only, re-triggered when a `TeamSportRound.is_over` flips, `max_rounds` defaulting to log2 of the team count). The schedulers use `apps.get_model()` to avoid circular imports.

Discipline-specific admin and validation match on the discipline **name string** (`GameAdmin.get_inline_instances`, `RugbyEvent._discipline_validation`); renaming a discipline breaks scoring.

**Registration import:** saving an `Edition` with a new `registration_form` CSV runs `Edition.create_players_from_registration_form`, which delegates to `olympic_warriors/registration.py`. Columns are matched by stable fragments (the bracketed skill criterion such as `[Cardio]`, the prefix of the global-level question, `Prénom et Nom`, optional `Adresse e-mail`), so yearly wording changes need no code change. The skill set itself is versioned in `FORM_PROFILES` (`"2024"`: ten skills with `Observation et orientation` and a single `Endurance et cardio`; `"2025"`: the 2025/2026 set, also exported as `RATINGS`); `resolve_columns` returns the first profile whose criteria all match and `compute_ratings` weights with that profile's coefficients, so a form with a new skill set needs a new profile (each `id` at most 4 characters, the `PlayerRating.identifier` limit). The Edition row and the import share one transaction, returning players are linked by name-derived username (accents kept), the form email is stored when present, and both `Player` and `PlayerRating` rows are update-or-created so re-uploading a corrected form refreshes ratings without duplicates. `Player.rating` is the rounded global rating.

**Edition transfer:** `olympic_warriors/transfer.py` moves a whole edition between databases (local to prod). The export carries no database ids (users by username, rows cross-referenced by throwaway `_id`s, MTI children as `subclass`/`child`); the import inserts with `save_base(raw=True)` so no model `save()` side effect runs, reuses existing users by username and creates missing ones with a random password. Media files are not in the document; on prod, `mediafiles` is a docker volume, so copy them into the container (`docker compose cp`), not into the repo folder. The runbook is in the transfer design spec under `docs/superpowers/specs/`.

**API:** ~70 flat `@api_view` functions in `views.py` wired in one hand-written list in `urls.py` (no routers, no `/api/` prefix except the schema at `/api/schema/swagger/`). Global auth is DRF `TokenAuthentication` + `IsAuthenticated`. Six edition/discipline read views carry `@permission_classes([AllowAny])` below `@api_view` and are public; everything else returns 401 without a token. Per-view policy decorators must go below `@api_view`: stacked above it DRF used to ignore them silently, and DRF 3.16+ raises a `TypeError` at import, so the wrong order stops the server from booting. Tokens are issued at `/auth/token/` and auto-created per user by `signals.py`. Serializers are `fields="__all__"` `ModelSerializer`s with a few computed read-only fields.

**Summary endpoint:** public `GET /edition/year/<year>/summary/` (view `getEditionSummary`, `EditionSummarySerializer` and the `Summary*` serializers in `serializer.py`) returns the whole edition in one payload, active rows only: `edition`, `disciplines`, `teams` (each with its roster, `ranking` and `total_points`) and `results`. Together with `/editions/` it is everything the front reads. `SummaryResultSerializer` nulls `ranking`, `points`, `time`, `points_difference` and `global_points` whenever the discipline's `reveal_score` is off or the result has no score for its type, so the public payload never leaks a score early (`TeamResult.ranking` itself returns 0 in those cases). Team totals are computed once per request into a `totals` dict passed through serializer context: `Team.ranking` is quadratic, so never call it per team when serializing a list. `getTeamResultsByEdition` filters on `discipline__edition`.

**Soft deletes:** nearly every model has `is_active`; the admin injects `is_active__exact=1` into every changelist via `request_only_active`, so inactive rows are hidden but still exist.

Settings: `olympic_warriors/config.py` (pydantic-settings) reads `ENV` and loads `DevConfig`/`ProdConfig`; any other value silently yields an empty config. `DATABASE_URL` wins over the `DB_*` vars. Media is served by Django only when `ENV=dev`.

Known dead code: `olympic_warriors/models.py` (shadowed by the `models/` package), the empty `templates/` dir, and the unused `bootstrap5`/`crispy_forms` apps.

## Frontend architecture

**Every edition page is under a year segment.** `front/src/params/year.js` matches exactly four digits, so `[year=year]` never swallows `/login`: the routes are `/<year>` (hub), `/<year>/ranking`, `/<year>/disciplines`, `/<year>/disciplines/<id>`, `/<year>/teams`, `/<year>/teams/<id>`. `/` renders the latest edition's hub through the same `front/src/lib/components/EditionHub.svelte` as `/<year>`, without redirecting. The bare `/ranking`, `/teams` and `/disciplines` are `+page.server.js`-only 302 redirects to the latest year. Detail routes take a numeric id, not a slug. All read pages are public — no route checks a cookie.

Data flow: the root `+layout.server.js` fetches `/editions/` (sorted newest first) and exposes `editions` and `latestYear`; the `[year=year]/+layout.server.js` fetches `/edition/year/<year>/summary/` **once** and every page below reads `summary` from `parent()` or `data` rather than fetching again. The two detail pages use a universal `+page.js` that resolves the id inside that summary and throws 404 when it is missing. Every derivation is a pure function in `front/src/lib/edition.js` — `rankedTeams`, `disciplineResults`, `teamResults`, `findTeam`, `findDiscipline`, `editionPhase`, `countdownParts`, `startInstant` (the event starts at 09:00 Europe/Paris whatever the renderer's timezone), `formatDateRange`, `formatDifference`, `switchYearPath` — so they are unit-testable with no Svelte or network.

API and errors: `front/src/lib/api.js` (`apiGet`/`apiPost`) throws a SvelteKit `error(status, message)` on any non-2xx or network failure, so loaders do not check return values; `front/src/lib/server/urls.js` prefixes `API_URL` (`$env/static/private`, baked in at build time, server-only). `front/src/routes/+error.svelte` renders thrown errors inside the layout; `front/src/error.html` is the static fallback for when the root layout itself fails (e.g. the API is down).

Presentation: `front/src/lib/icons.js` maps a discipline name to an SVG in `front/src/lib/img/icons/` — the file stem is the name lowercased with spaces and apostrophes removed — and falls back to `default.svg`, so a new discipline shows the fallback star until an icon is added; `src/lib/icons.test.js` lists every discipline model and fails when one has no icon. `+layout.svelte` puts a `hub` class on the `.app` wrapper for `/` and `/[year=year]`, and `styles.css` defines the light theme on `:root` and the dark one on `.hub`, so the theme is server-rendered with no flash. The header's year `<select>` and the mobile menu both route through `switchYearPath`, and a Photos link appears only when the edition has a `photos_url`.

Auth: the login form action posts to `/auth/token/` and stores `Authorization: Bearer <token>` in an httpOnly cookie. Nothing reads that cookie yet — `/login` is out of the nav and kept for the future organiser tools; there is no register form and there are no Svelte stores.

Tests sit next to what they cover (`src/lib/*.test.js` for the helpers, `page.test.js` beside a `+page.svelte`) and run on the fixtures in `front/src/lib/fixtures/summary.js`; `npm test` gates in CI, so keep them passing.

## Knowledge graph

`graphify-out/` holds a graphify knowledge graph of this repo (`graph.html`, `graph.json`, `GRAPH_REPORT.md`). For architecture questions, prefer `/graphify query "<question>"` over grepping; after large changes run `/graphify --update`. The checked-in graph predates the edition-aware front restructure, so its front half is stale until the next update.
