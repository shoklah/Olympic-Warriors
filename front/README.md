# Olympic Warriors: front

This folder holds the public Olympic Warriors website, built with SvelteKit. Every page is rendered on the server from the Django API, and organisers use the same site to score on the day. For an overview of the whole repository and the quick start, see the [root README](../README.md).

## Stack

- SvelteKit 2 and Svelte 4, in plain JavaScript (no TypeScript)
- `@sveltejs/adapter-node`: the production build is a Node server
- Vitest with jsdom and `@testing-library/svelte` for the tests
- Node 22
- No CSS framework, no store library and no lint tooling

## Setup

The front needs one setting: `API_URL`, the address of the Django API. SvelteKit reads it through `$env/static/private`, so:

- **It is fixed at build time.** Changing it later means rebuilding.
- **It never reaches the browser.** Every API call happens on the server.

```bash
cp .env.example .env
```

Set `API_URL` in `.env` depending on where the front runs:

| Where the front runs | `API_URL` |
| --- | --- |
| In docker compose | `http://server:3003` |
| Natively on your machine | `http://localhost:3003` |

A missing `.env` fails the production build. In dev, it makes the server throw a clear error instead of fetching `undefined/...`.

### In docker compose

`docker compose up --build` at the repository root starts the front on http://localhost:5173 with hot reload, next to the API. Its `node_modules` is an anonymous volume. After a dependency or Dockerfile change, recreate the container so it gets fresh dependencies:

```bash
docker compose up -d -V --build front
```

To run the tests there, without Node on your machine:

```bash
docker compose exec front npm test
```

### Natively

You need Node 22 and the API running, for example the compose `server` service. Stop the compose front first (`docker compose stop front`), because both use port 5173. Then:

```bash
npm ci
```

```bash
npm run dev
```

## Scripts

| Script | What it does |
| --- | --- |
| `npm run dev` | Vite dev server on port 5173, listening on all interfaces |
| `npm test` | Runs every `src/**/*.test.js` file once with Vitest |
| `npm run build` | Production build into `build/` |
| `npm run preview` | Serves the production build locally |

There is no `check` or `lint` script. CI runs `npm ci`, `npm test` and `npm run build` on Node 22, and a failure blocks the merge.

## Routes

Every edition page lives under a four-digit year segment. `src/params/year.js` matches exactly four digits, so `/<year>` never swallows `/login`.

| Path | Page |
| --- | --- |
| `/` | The latest edition's hub, without a redirect. Returns 404 "No edition yet" until an edition exists. |
| `/<year>` | The edition hub: the discipline icons, host and dates, a countdown before the event and a link to the ranking after it, and links to the other editions |
| `/<year>/ranking` | The team ranking: podium, rosters, points, with the discipline rail under the title |
| `/<year>/disciplines` | Every discipline of the edition |
| `/<year>/disciplines/<id>` | One discipline: its ranking, then its schedule by round. For organisers, also the scoring tools. |
| `/<year>/teams/<id>` | One team: its results and the games it played |
| `/<year>/teams` | Redirects to that year's ranking (kept for old links) |
| `/ranking`, `/disciplines`, `/teams` | Redirect to the latest year |
| `/login`, `/logout` | Organiser sign-in and sign-out |
| `/lang` | Target of the language switch (form POST only) |

Detail pages take a numeric id, not a slug. All read pages are public: no route requires a login.

## How data flows

1. **The root layout** (`src/routes/+layout.server.js`) loads `/editions/` on every request. It exposes three things to every page:
   - `editions` (newest first) and `latestYear`.
   - The locale, from the `lang` cookie.
   - Whether the visitor is an organiser. It finds out by calling `/user/current/` with the `token` cookie.
2. **The year layout** (`src/routes/[year=year]/+layout.server.js`) fetches `/edition/year/<year>/summary/` **once**. Every page below it reads `summary` from `data` or `parent()` and never fetches again.
   - An organiser's summary is fetched with their token, so hidden scores come back too.
   - The layout also returns `editable`, which is true for an organiser on the latest year.
3. **The two detail pages** use a universal `+page.js` that finds the id inside that summary, and throw a 404 when it is missing.
4. **Every derivation** is a pure function in `src/lib/edition.js`, which makes each one testable without Svelte or a network. They include rankings, a discipline's results and schedule, a team's games, the edition phase and countdown, date and time formatting, and the year switch.

`src/lib/api.js` (`apiGet`, `apiPost`, `apiPatch`) throws a SvelteKit `error(status, message)` on any non-2xx response or network failure, so loaders never check return values. `src/lib/server/urls.js` prefixes `API_URL`. Errors are shown in two places:

- **`src/routes/+error.svelte`** renders an error inside the layout.
- **`src/error.html`** is the static fallback for when the root layout itself fails, for example when the API is down. It carries both languages.

## Source layout

```
src/
  app.html              document shell: font preloads, favicons, <html lang="%lang%">
  error.html            static fallback error page
  hooks.server.js       sets <html lang> from the lang cookie, and Vary: Cookie
  params/year.js        the four-digit year matcher
  routes/               pages, layouts, form actions, and a page.test.js beside each page
    styles.css          design tokens and global utilities
  lib/
    api.js              fetch helpers that throw SvelteKit errors
    server/urls.js      API_URL prefix (server only)
    edition.js          every pure derivation from the summary
    session.js          token cookie name and options, organiser context
    icons.js            discipline name -> SVG icon
    components/         Header, TabBar, Breadcrumb, EditionHub, DisciplineRail, GameRow,
                        MedalRank, StaffBar, ScoreSheet
    i18n/               fr.js, en.js, disciplines.js, t / useT / useLocale
    img/                logo, and icons/ with one SVG per discipline
    fixtures/summary.js summary payloads for the tests
    test-utils.js       renderWith()
static/                 favicons and the self-hosted fonts
```

Components are imported by explicit path (`$lib/components/GameRow.svelte`). `+layout.svelte` is the only file that reads route ids, to decide where the phone tab bar shows.

## Languages

The site is in French first, with English as the second language.

- **Messages.** Every visible string goes through `t`.
  - `src/lib/i18n/fr.js` is the reference dictionary.
  - `en.js` mirrors it key for key. `parity.test.js` fails when the two drift apart.
  - A message that counts things is `{ one, other }`, picked with `Intl.PluralRules`. French puts 0 in the singular, as in `0 match`.
- **Discipline names.** The database stores discipline names in English. `disciplines.js` maps them to French in `FRENCH_NAMES`, or lists them in `SAME_IN_FRENCH` when the name doesn't change.
- **Choosing the language.** The `lang` cookie decides; anything but `en` is French.
  - The header's `FR | EN` form posts to `/lang`. That stores the cookie for a year and redirects back, so the page reloads fully in the new language.
  - Never add `use:enhance` to that form.
- **In components.** Call `useT()` or `useLocale()` at component init only. Svelte's `getContext` throws anywhere else. Helpers in `edition.js` take the locale as an argument when they need one.
- **Case.** Text stays in sentence case, with its accents, in the markup. Uppercase comes from CSS `text-transform`.

## Organisers

A staff account created in the Django admin logs in at `/login`.

- **Login.** The form posts to the API's `/auth/token/` and stores the token in an httpOnly `token` cookie for a week. `/logout` deletes the cookie.
- **Throttling.** The login forwards the visitor's IP to the API's login throttle. A throttled attempt shows a message.
- **The header** shows `Connexion` to visitors and an `ORGA` logout pill to organisers.

The scoring tools appear only when `data.editable` is true, that is for an organiser on the latest edition, and only on the discipline page. They are:

| Tool | What it does |
| --- | --- |
| `StaffBar` | Shows whether the discipline is hidden or public and how many results are missing, with a button to reveal or hide it. |
| `ScoreSheet` | Enters a game's score. It is a bottom sheet on phones and a dialog from 1000px, with steppers and a "played" switch. |
| Result lines | Enter points or a `mm:ss` time, for disciplines without games. An empty value clears it. |
| `Clore le tour` | Closes a complete Swiss round. The API then schedules the next one. |

Each tool posts to a named action in `src/routes/[year=year]/disciplines/[id]/+page.server.js`: `score`, `result`, `reveal` or `close`.
- **API call.** The action validates the input, then calls the API's organiser endpoint with the token.
- **Errors.** A failure comes back as a dictionary key, which the page translates.
- **Success.** `use:enhance` re-runs the loads, so the page shows the new state.

## Design

The site has one dark theme, "Scoreboard". Its tokens are defined on `:root` in `src/routes/styles.css`:

| Group | Tokens |
| --- | --- |
| Surfaces | `--bg`, `--bg-raised`, `--bg-sunken` |
| Rules | `--line`, `--line-strong` |
| Text | `--ink`, `--text`, `--muted`, `--faint`, `--ghost` |
| Accent | `--accent` |
| Medals | `--gold`, `--silver`, `--bronze` |
| Outcomes | `--win`, `--loss`, `--todo` |
| Layout | `--page` (the content column), `--tabbar` |

Styling rules:

- **Tokens only.** Pages use the tokens and never hard-code a colour. There is no theme switch.
- **Fonts.** Bebas Neue for display text (headings, numbers, navigation) and Inter for body text. Both are self-hosted woff2 files in `static/fonts/`, and the hot weights are preloaded in `app.html`, so the site makes no third-party font request.
- **Utility classes:**
  - `.label`: small tracked uppercase labels.
  - `.num`: figures and their unit, such as `33 pts`.
  - `.dimmed`: something not reachable yet.
  - `.visually-hidden`: text for screen readers only.
- **Breakpoint.** At 1000px and wider, the header tabs show. Below that, a fixed bottom tab bar replaces them.
- **Reduced motion.** A `prefers-reduced-motion` block turns off every transition and animation.
- **Favicons.** The favicons in `static/` are rendered from `src/lib/img/logo.svg`. Regenerate all three when the logo changes.

The full design spec is [the Scoreboard UI spec](../docs/superpowers/specs/2026-09-22-scoreboard-ui-design.md).

## Adding a discipline icon

`src/lib/icons.js` finds a discipline's icon from its name. The file stem is the name in lowercase with spaces and apostrophes removed: `Hide and Seek` becomes `hideandseek.svg`. A discipline without an icon shows `default.svg`.

After adding a discipline on the server (see [server/README.md](../server/README.md#adding-a-discipline)):

1. Add `src/lib/img/icons/<stem>.svg`.
2. Add the name to `DISCIPLINE_NAMES` in `src/lib/icons.test.js`.
3. Add the French name to `FRENCH_NAMES` in `src/lib/i18n/disciplines.js`, or add the name to `SAME_IN_FRENCH`.

`icons.test.js` fails until both the icon and the translation exist.

## Tests

Tests sit next to what they cover: `src/lib/*.test.js` for the helpers, and `page.test.js` beside each `+page.svelte`. They run on the summary payloads in `src/lib/fixtures/summary.js`:

| Fixture | What it contains |
| --- | --- |
| `summary` | The default payload for most tests. |
| `summaryAllRevealed` | The same edition with Orienteering revealed and its times filled in. |
| `summaryStaff` | The organiser's payload, with hidden scores included. |
| `summaryManual` | An edition ranked by hand. |

Conventions:

- **Render with `renderWith`.** Use `renderWith(Component, props, locale, organiser)` from `src/lib/test-utils.js`. It defaults to English, and the fourth argument turns on the organiser view. A plain `render()` has no context, so the component renders in French. Keep at least one French test for every translated page or component.
- **Assert on text, not classes.** For example, a ranking row reads `1 Bisons 5 pts` and a team's game row reads `R1 Bisons 12 : 9 Aigles`. If you change a row's markup, update those assertions in the same commit.
- **Stub `use:enhance`.** Pages or components that use it need this stub:

  ```js
  vi.mock('$app/forms', () => ({ enhance: () => ({ destroy() {} }) }));
  ```

- **Discipline page data.** The discipline page tests build their `data` with a local `dataFor(summary, id, editable)` helper.

## Production

`Dockerfile.prod` builds in a `node:22` image with `npm ci` and `npm run build`, and runs `node build`. It copies the whole `front/` folder into the build, so `front/.env` must hold the production `API_URL` before you build.

The production compose file (`docker-compose.prod.example.yml` at the repository root) passes these runtime variables to the front:

| Variable | Why |
| --- | --- |
| `PORT` | The port the Node server listens on: 3000 for production, 4000 for stage. |
| `ORIGIN` | The public origin, such as `https://olympicwarriors.com`. SvelteKit refuses form POSTs whose `Origin` differs, so without it the language switch fails with a 403 behind nginx. Set it on every front, stage included. |
| `ADDRESS_HEADER=x-forwarded-for`, `XFF_DEPTH=1` | Let the login see the visitor's IP rather than nginx's. Only set these if nginx sets `X-Forwarded-For` on the location that proxies to the front, because otherwise a visitor can forge the header. |
