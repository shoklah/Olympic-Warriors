# Olympic Warriors

Website and back office for **Olympic Warriors**, a yearly team event whose disciplines come from a catalogue of about two dozen: rugby, dodgeball, relay, blindtest, quizzes, darts and more. Each year is an *edition* with its own teams, players and disciplines. The public site shows the schedule, results and overall ranking of every edition, in French and English. On the day, organisers enter scores from the same site.

- **Public pages** for each edition (`/<year>`):
  - a hub with a countdown
  - the overall ranking (podium, rosters, points)
  - the list of disciplines
  - each discipline's ranking and schedule
  - each team's results and games
- **Scheduling.** Each discipline uses one of two pairing systems:
  - Round robin: every round is generated up front, with referees assigned.
  - Swiss: the next round is generated when the previous one closes.
- **Scores stay hidden** until an organiser reveals the discipline. Visitors can see the pairings before that.
- **Organiser tools.** A staff account logged in at `/login` can do the following from the discipline pages of the latest edition:
  - enter game scores, points or times
  - reveal disciplines
  - close Swiss rounds
- **Registration import.** Uploading the registration form CSV on an edition creates its players and their skill ratings.
- **Edition transfer.** An edition can be exported to JSON and imported into another database, for example from local to production.

## Stack

| Part | Tech | Details |
| --- | --- | --- |
| [`server/`](server/) | Python 3.11, Django 4.2, Django REST Framework, PostgreSQL 16 | [server/README.md](server/README.md) |
| [`front/`](front/) | SvelteKit 2, Svelte 4 (plain JS), `adapter-node`, Vitest, Node 22 | [front/README.md](front/README.md) |
| Tooling | Docker Compose (dev and prod), GitHub Actions | |

```
browser ──> front (SvelteKit, server-side loads) ──> server (Django REST API) ──> PostgreSQL
```

The front never touches the database. For each edition it reads `/editions/` and one summary payload, `/edition/year/<year>/summary/`. Rankings are computed on the fly rather than stored. The one exception is a finishing order entered by hand for an old edition that has no result data.

## Repository layout

```
server/                          Django project (single app olympic_warriors): models, API, admin,
                                 schedulers, management commands, tests
front/                           SvelteKit site: routes, components, i18n, tests
docs/superpowers/specs/          one design spec per feature
docs/superpowers/plans/          the matching implementation plans
docker-compose.yml               development stack
docker-compose.prod.example.yml  production template (gunicorn, Node, nginx + certbot, stage stack)
.github/workflows/test.yml       CI
CLAUDE.md                        detailed architecture notes
```

`server/docker-compose.yml` is stale. Always use the compose file at the root.

## Getting started

You need Docker with Compose v2. You don't need Python or Node on your machine.

1. **Prepare the server config.** Copy the env template, then set `SECRET_KEY` in `server/dev.env` to any non-empty string. Keep `server` in `ALLOWED_HOSTS`, because the front container calls the API under that hostname.

   ```bash
   cp server/.env.example server/dev.env
   ```

2. **Prepare the front config.** The template already points at the compose API.

   ```bash
   cp front/.env.example front/.env
   ```

3. **Start the stack.** This runs the migrations, the Django dev server and the Vite dev server. It stays in the foreground, so use a second terminal for the next steps.

   ```bash
   docker compose up --build
   ```

4. **Create an admin account.** The username and password come from `SU_USERNAME` and `SU_PASSWORD` in `dev.env`.

   ```bash
   docker compose exec server python manage.py createsu
   ```

5. **Add an edition.** Until one exists, the site's home page is a 404 ("No edition yet"). Either create an edition in the Django admin, or import a file someone exported with `export_edition` (see [server/README.md](server/README.md#management-commands)).

Once the stack is up, these are the local addresses:

| Service | Address |
| --- | --- |
| Site | http://localhost:5173 |
| API | http://localhost:3003 (there is no page at `/`; try `/editions/`) |
| Django admin | http://localhost:3003/admin/ |
| API docs (Swagger) | http://localhost:3003/api/schema/swagger/ |
| pgAdmin | http://localhost:5051, login `pgadmin4@pgadmin.org` / `admin`. To add the database inside pgAdmin, use host `db` and port `5433`. |
| PostgreSQL from your machine | `localhost:5433`, database `mydb-dev`, user `user` / `password` |

Three things tend to trip people up:

- `server/dev.env` is only read when the server starts. After editing it, run `docker compose restart server`.
- `API_URL` in `front/.env` is baked in at build time. Use `http://server:3003` inside Compose, and `http://localhost:3003` when the front runs natively.
- The front container's `node_modules` is an anonymous volume. After a dependency or Dockerfile change, run `docker compose up -d -V --build front` to recreate it.

## Everyday commands

Everything runs through the containers:

```bash
docker compose exec server python manage.py test
```

```bash
docker compose exec server python manage.py makemigrations
```

```bash
docker compose exec front npm test
```

```bash
docker compose exec front npm run build
```

The part READMEs have the rest:

- [server/README.md](server/README.md): configuration, the domain model and scoring rules, the API, management commands, edition transfer, lint, adding a discipline.
- [front/README.md](front/README.md): running the front natively, routes, data flow, i18n, organiser tools, design tokens, test conventions.

## CI

[`.github/workflows/test.yml`](.github/workflows/test.yml) runs on every push and on pull requests to `main` and `dev`. It has three jobs:

- **`server`** runs the Django suite on Python 3.11 against a Postgres 16 service container, after `makemigrations --check --dry-run`, which fails when a model change has no migration. Its settings come from job variables, not from an env file.
- **`front`** runs `npm ci`, `npm test` and `npm run build` on Node 22.
- **`test`** is advisory. It runs pylint with `continue-on-error`, then builds the images and starts the containers. Nothing checks that the containers stay up.

A failure in `server` or `front` fails the workflow. Neither is a required status check, so look at them before merging.

## Deployment

[`docker-compose.prod.example.yml`](docker-compose.prod.example.yml) is the starting point. It runs:

- the API under gunicorn
- the front as a Node server
- nginx with Let's Encrypt in front of both
- a stage copy of the stack next to production

Before the first deploy, work through these points:

- **Fill in the template.** The database settings and `ports` are blank, and so is `CERTBOT_EMAIL`. Adjust the absolute `/opt/OW_stage/...` paths of the stage stack as well.
- **Server config.** Create `server/prod.env`: `ENV=prod` reads it instead of `dev.env`. The image build needs it too, because it runs `collectstatic` with `ENV=prod`, so it must hold at least `SECRET_KEY`, `DEBUG` and the `DB_*` keys. It is copied into the image at build time, so after editing `prod.env`, rebuild `server` rather than restarting it.
- **Migrations.** Nothing runs them in production. After each deploy that adds migrations, run `migrate`. After the first deploy, also run `createsu`.
- **Admin credentials.** Before that first `createsu`, set your own `SU_USERNAME` and a strong `SU_PASSWORD` in `prod.env`. Without them, `createsu` creates a superuser named `admin` with the password `password`. Changing them later does not update an account that already exists: use `manage.py changepassword` for that.
- **Front config.** `front/.env` must hold the production `API_URL` before you build the front image.
- **`ORIGIN`.** Set it on each front, `front-stage` included (the template has it only on `front`). Without it, SvelteKit refuses every form POST behind the TLS-terminating proxy: the language switch, login, logout and the organiser tools.
- **Client IPs.** The login throttle identifies clients by the last `X-Forwarded-For` entry. For that reason:
  - The app ports are bound to `127.0.0.1`.
  - Every nginx location that proxies to the server or the front must set `X-Forwarded-For $proxy_add_x_forwarded_for`.
- **nginx site config.** It lives on the host under `nginx/user_conf.d` and is not in the repository.
- **Moving an edition.** To copy an edition from local to production, use `export_edition` / `import_edition`. Media files are not part of the export. On production `mediafiles` is a Docker volume, so copy them with `docker compose cp`. The runbook is in [the edition transfer spec](docs/superpowers/specs/2026-09-19-edition-transfer-design.md).

Each part's README has its production details.

## Further reading

- [server/README.md](server/README.md) and [front/README.md](front/README.md): each part in depth.
- [CLAUDE.md](CLAUDE.md): architecture notes for the whole repository, kept up to date with every change.
- [`docs/superpowers/specs/`](docs/superpowers/specs/): one design document per feature.
- The Swagger UI at `/api/schema/swagger/` on a running server.

## License

Apache License 2.0, see [`server/LICENSE`](server/LICENSE).
