# Olympic Warriors

Website and back office for **Olympic Warriors**, a yearly team event that mixes two dozen disciplines: rugby, dodgeball, relay, blindtest, quizzes, darts and more. Each year is an *edition* with its own teams, players and disciplines. The public site shows the schedule, results and overall ranking of every edition in French and English. On the day, organisers enter scores from the same site.

- **Public pages** for each edition (`/<year>`): a hub with a countdown, the overall ranking (podium, rosters, points), the list of disciplines, each discipline's ranking and schedule, and each team's games.
- **Scheduling**: a discipline can be a round robin (every round is generated up front, with referees assigned) or a Swiss system (the next round is generated when the previous one closes).
- **Scores stay hidden** until an organiser reveals the discipline. Visitors see the pairings before that, but no scores.
- **Organiser tools**: with a staff account, you can enter game scores, points or times, reveal disciplines and close Swiss rounds from the discipline page.
- **Registration import**: uploading the registration form CSV on an edition creates its players and their skill ratings.
- **Edition transfer**: you can export an edition to JSON and import it into another database, for example from local to production.

## Stack

| Part | Tech |
| --- | --- |
| `server/` | Python 3.11, Django 4.2, Django REST Framework, drf-spectacular, PostgreSQL 16 |
| `front/` | SvelteKit 2, Svelte 4 (plain JS), `adapter-node`, Vitest, Node 22 |
| Tooling | Docker Compose for dev and prod, GitHub Actions |

```
browser ──> front (SvelteKit, server-side loads) ──> server (Django REST API) ──> PostgreSQL
```

The front never touches the database. For each edition it reads `/editions/` and one summary payload, `/edition/year/<year>/summary/`. Rankings are computed on the fly and never stored.

## Repository layout

```
server/                          Django project, single app olympic_warriors
  olympic_warriors/models/         one file per model, one per discipline
  olympic_warriors/schedule/       round robin and Swiss pairing
  olympic_warriors/management/     createsu, create_tokens_for_users, export_edition, import_edition
  olympic_warriors/tests/          Django tests
front/                           SvelteKit site
  src/routes/                      pages (every edition page lives under /<year>)
  src/lib/                         components, pure helpers (edition.js), i18n, fixtures
docs/superpowers/                design specs and implementation plans, one per feature
docker-compose.yml               development stack
docker-compose.prod.example.yml  production template (gunicorn, adapter-node, nginx + certbot, stage)
.github/workflows/test.yml       CI
CLAUDE.md                        detailed architecture notes
```

## Getting started

You need Docker with Compose v2. Node 22 is only needed if you want to run the front tests outside Docker.

1. **Create the two env files.** Both are gitignored.

   ```bash
   cp server/.env.example server/dev.env
   ```

   ```bash
   cp front/.env.example front/.env
   ```

   In `server/dev.env`, set `SECRET_KEY` to any non-empty string. Keep `server` in `ALLOWED_HOSTS`, because the front container calls the API under that hostname.

2. **Start the stack.** This runs the migrations, the Django dev server and the Vite dev server.

   ```bash
   docker compose up --build
   ```

3. **Create an admin account.** The username and password come from `SU_USERNAME` and `SU_PASSWORD` in `dev.env`.

   ```bash
   docker compose exec server python manage.py createsu
   ```

4. **Add an edition** in the Django admin, or import one with `import_edition` (see below).

| Service | URL |
| --- | --- |
| Site | http://localhost:5173 |
| API | http://localhost:3003 |
| Django admin | http://localhost:3003/admin/ |
| API docs (Swagger) | http://localhost:3003/api/schema/swagger/ |
| pgAdmin | http://localhost:5051 (`pgadmin4@pgadmin.org` / `admin`) |
| PostgreSQL | `localhost:5433`, database `mydb-dev`, `user` / `password` |

A few things can trip you up:

- `dev.env` is only read when the server starts. After editing it, run `docker compose restart server`.
- `API_URL` in `front/.env` is baked in at build time. Use `http://server:3003` inside Compose and `http://localhost:3003` when the front runs natively.
- `node_modules` in the front container is an anonymous volume. After a dependency or Dockerfile change, run `docker compose up -d -V --build front`.

## Everyday commands

Backend commands run inside the `server` container. The tests need the Compose Postgres.

```bash
docker compose exec server python manage.py test
```

```bash
docker compose exec server python manage.py test olympic_warriors.tests.test_players.TestPlayersAPI.test_get_players
```

```bash
docker compose exec server python manage.py makemigrations
```

```bash
docker compose exec server python manage.py create_tokens_for_users
```

Move an edition between databases. The document carries no database ids. Use `--dry-run` to check the import first and `--replace` to overwrite that year.

```bash
docker compose exec server python manage.py export_edition 2026 --out /server/edition-2026.json
```

```bash
docker compose exec server python manage.py import_edition /server/edition-2026.json --dry-run
```

Lint the backend the way CI does:

```bash
pylint --load-plugins pylint_django --ignore=lib server/
```

The front commands run inside `front/`:

```bash
npm test
```

```bash
npm run build
```

## Adding a discipline

Each discipline is a Django model that subclasses `Discipline`. In short:

1. Add the model in `server/olympic_warriors/models/`, export it from `models/__init__.py` and register it in `admin.py`.
2. Run `makemigrations`.
3. Add an SVG icon in `front/src/lib/img/icons/` and the French name in `front/src/lib/i18n/disciplines.js`.

The full checklist, including the front test that enforces the icon and the translation, is in [CLAUDE.md](CLAUDE.md).

## CI

[`.github/workflows/test.yml`](.github/workflows/test.yml) runs on every push:

- **`front`** (gating): `npm ci`, `npm test`, `npm run build` on Node 22.
- **`test`** (advisory): pylint with `continue-on-error`, then a boot of the Compose stack. The Django migrate and test steps are commented out, so run the backend tests locally before merging.

## Deployment

Copy [`docker-compose.prod.example.yml`](docker-compose.prod.example.yml) as the starting point. It runs the API under gunicorn, the front as a Node server, nginx with Let's Encrypt in front of both, and a stage copy of the stack next to production.

- `ENV=prod` makes the server read `server/prod.env` instead of `dev.env`. Any real environment variable overrides the file.
- The front needs `ORIGIN=https://<public host>`. Without it, SvelteKit refuses the language switch (a form POST) behind the TLS-terminating proxy.
- The login throttle identifies clients by the last `X-Forwarded-For` entry. The app ports are therefore bound to `127.0.0.1`, and every nginx location that proxies to the server or the front must set `X-Forwarded-For $proxy_add_x_forwarded_for`.
- The nginx site config lives on the host under `nginx/user_conf.d` and is not in the repository.
- To move an edition from local to production, use `export_edition` / `import_edition`. Media files are not in the export: on production `mediafiles` is a Docker volume, so copy them with `docker compose cp`. The runbook is in [the edition transfer spec](docs/superpowers/specs/2026-09-19-edition-transfer-design.md).

## Further reading

- [CLAUDE.md](CLAUDE.md): architecture in depth, covering scoring, standings, the summary endpoint, soft deletes, auth, i18n, the front's data flow and theme.
- [`docs/superpowers/specs/`](docs/superpowers/specs/): one design document per feature.
- The Swagger UI at `/api/schema/swagger/` on a running server.

## License

Apache License 2.0, see [`server/LICENSE`](server/LICENSE).
