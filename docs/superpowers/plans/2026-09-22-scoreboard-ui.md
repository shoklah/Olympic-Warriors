# Scoreboard UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Implementers run ONE AT A TIME on this checkout (shared git index).

**Goal:** Restyle the SvelteKit front into the dark "Scoreboard" identity: one theme, Bebas Neue + Inter, medal accents, breadcrumbs, a bottom tab bar on phones, compact schedule rows and result tiles.

**Architecture:** Design tokens in `styles.css` drive every page; five small components (`Header`, `TabBar`, `Breadcrumb`, `MedalRank`, `GameRow`) carry the shared pieces; each page is restyled in its own commit against its existing tests. No API or data change.

**Tech Stack:** SvelteKit 2 / Svelte 4, Vitest + Testing Library, Google Fonts.

**Spec:** `docs/superpowers/specs/2026-09-22-scoreboard-ui-design.md` (tokens, component contracts and per-page layout live there; this plan does not repeat them).

**Reference mockups** (on the author's machine, gitignored): `.superpowers/brainstorm/91113-1790101156/content/direction.html` (card A), `discipline-page.html` (variant 1), `team-page-nav.html` (variants 2 and 4), `type-and-grids.html`. Copy their CSS values rather than reinventing.

---

## Working environment

Main checkout `/Users/shoklah/Work/Playground/Olympic-Warriors`, branch `claude/scoreboard-ui` (already created off `dev`). `front/.env` exists. Commands in `front/`: `npm test`, `npm run build`. The compose front on `http://localhost:5173` serves this checkout live for visual checks (`docker compose logs front` if it misbehaves).

Commit prefix `[FEAT]`/`[FIX]`/`[TEST]`/`[DOCS]`, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## File structure

| File | Change |
|---|---|
| `front/src/app.html` | Google Fonts link (Bebas Neue, Inter), `<title>` |
| `front/src/routes/styles.css` | tokens, base type, body padding for the tab bar; remove `.hub` and light theme |
| `front/src/routes/+layout.svelte` | render `Header`, `TabBar`; drop the `hub` class logic |
| `front/src/lib/components/Header.svelte` | moved from `routes/Header.svelte`, restyled |
| `front/src/lib/components/TabBar.svelte`, `TabBar.test.js` | new |
| `front/src/lib/components/Breadcrumb.svelte`, `Breadcrumb.test.js` | new |
| `front/src/lib/components/MedalRank.svelte`, `MedalRank.test.js` | new |
| `front/src/lib/components/GameRow.svelte`, `GameRow.test.js` | new |
| `front/src/routes/menu.svelte` | delete |
| `front/src/lib/components/EditionHub.svelte` | restyle |
| `front/src/routes/[year=year]/ranking/+page.svelte` (+ test) | restyle |
| `front/src/routes/[year=year]/disciplines/+page.svelte` (+ test) | restyle, subtitle |
| `front/src/routes/[year=year]/disciplines/[id]/+page.svelte` (+ test) | restyle, `GameRow` |
| `front/src/routes/[year=year]/teams/+page.svelte` (+ test) | rank order, roster inline |
| `front/src/routes/[year=year]/teams/[id]/+page.svelte` (+ test) | tiles, games rows |
| `front/src/routes/+error.svelte`, `front/src/error.html`, `front/src/routes/login/login.svelte` | tokens |
| `CLAUDE.md` | theme paragraph, components |

---

## Task 1: Tokens, fonts, base styles, layout

**Files:** `front/src/app.html`, `front/src/routes/styles.css`, `front/src/routes/+layout.svelte`.

- [ ] **Step 1:** In `app.html` add before `%sveltekit.head%`:
  `<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">` and `<title>Olympic Warriors</title>`.
- [ ] **Step 2:** Rewrite `styles.css`: the `:root` block from the spec (drop the Fira Mono import and the old `--color-*` names; keep a `--color-bg-0: var(--bg)` and `--color-theme-1: var(--accent)` alias for one commit so pages not yet migrated still render, remove the aliases in Task 8), `body` (background, colour, font, `margin: 0`, `min-height: 100vh`), `h1, h2, h3 { font-family: var(--font-display); letter-spacing: 0.06em; font-weight: 400; color: var(--ink); margin: 0 }` with sizes 2.75rem / 1.4rem / 1.1rem, `a { color: inherit; text-decoration: none }`, `a:hover { color: var(--accent) }`, `ul { list-style: none; padding: 0; margin: 0 }`, a `.label` utility (`font: 600 0.75rem/1 var(--font-body); letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted)`), a `.num` utility (`font-family: var(--font-display); font-variant-numeric: tabular-nums`), `@media (max-width: 999px) { body { padding-bottom: var(--tabbar) } }`, keep `.visually-hidden`. Delete the `.hub` rule.
- [ ] **Step 3:** In `+layout.svelte` remove `HUB_ROUTES`/`isHub`/`class:hub`; keep `onNavigate`; render `<Header />` and `<TabBar />` (imported from `$lib/components`, created in Task 2; for this commit keep importing the existing `./Header.svelte` and skip `TabBar`). `.app` loses its background rule (body has it).
- [ ] **Step 4:** `npm test` (all green: nothing asserts on colours), `npm run build`, open `http://localhost:5173/2026/ranking`: dark background, new fonts, pages readable even if unstyled. Commit `[FEAT] front: scoreboard tokens, fonts and base styles`.

## Task 2: Header, TabBar, Breadcrumb, MedalRank, GameRow (TDD)

**Files:** the five components and four tests under `front/src/lib/components/`; delete `front/src/routes/menu.svelte`; move `front/src/routes/Header.svelte` to `front/src/lib/components/Header.svelte` (`git mv`); update the import in `+layout.svelte` and add `<TabBar />`.

- [ ] **Step 1 (tests first):**
  - `Breadcrumb.test.js`: `render(Breadcrumb, { items: [{ label: '2026', href: '/2026' }, { label: 'Disciplines', href: '/2026/disciplines' }, { label: 'Rugby' }] })` → links `2026` and `Disciplines` with those hrefs, `Rugby` present and not a link, `nav` has `aria-label="Breadcrumb"`.
  - `MedalRank.test.js`: `render(MedalRank, { rank: 1 })` element has class `gold` and text `1`; rank 2 `silver`, 3 `bronze`, 4 none of them; `rank: null` renders `—` with class `none`.
  - `GameRow.test.js`: played 12–9 → text matches `/Bisons\s*12 : 9\s*Aigles/`, `Bisons` has class `winner`, `Aigles` has `loser`, `ref: Cerfs` present; unplayed → `— : —`; played with null scores → `played`; draw → neither name has `winner`; with `team1Href` the name is a link.
  - `TabBar.test.js`: `render(TabBar, { year: 2026, pathname: '/2026/teams' })` → three links `Ranking`, `Teams`, `Disciplines` with hrefs `/2026/ranking` etc., `Teams` has `aria-current="page"`; with `year: null` renders nothing.
- [ ] **Step 2:** run, see them fail on missing modules.
- [ ] **Step 3:** implement per the spec contracts. `TabBar` takes props (`year`, `pathname`) so it is testable; `+layout.svelte` passes `$page.params.year ?? $page.data.latestYear` and `$page.url.pathname`, and hides it with `{#if !isHub}` where `isHub = ['/', '/[year=year]', '/login'].includes($page.route.id)` (this is the only place route ids are read). `Header` drops the mobile menu and the `Menu` import, keeps the `<select>` with `selected`, styles per the mockup top bar (padding 12px 18px, bottom rule `--line`, logo image 2.2rem high, year pill in the display face, tabs hidden under 1000px).
- [ ] **Step 4:** `npm test`, `npm run build`, check `/2026/ranking` at phone width in the browser: tab bar visible, hamburger gone. Commit `[FEAT] front: header, tab bar, breadcrumb, medal rank and game row components`.

## Task 3: Hub

**Files:** `EditionHub.svelte`, `EditionHub.test.js` (should not change).

- [ ] Restyle: `.where` in the display face 1.1rem letter-spaced accent; countdown digits in the display face 3rem, labels `.label`; Ranking button as the mock (`background: var(--accent); color: var(--bg); font-family: var(--font-display); font-size: 1.6rem; letter-spacing: 0.15em; padding: .7rem 3rem; border-radius: var(--radius)`); year chips bordered `--faint`, display face. Keep eclipse, title image, icon columns. Tests unchanged and green. Commit `[FEAT] front: hub in the scoreboard style`.

## Task 4: Ranking page

**Files:** `ranking/+page.svelte`, `ranking/page.test.js`.

- [ ] Add `Breadcrumb` (`[{label: year, href: /year}, {label: 'Ranking'}]`), `h1 Ranking`, rows per spec using `MedalRank` (keep `data-testid="team-row"`, the row is still the `<a>`, keep `class:gold/silver/bronze` on the row because the test asserts them), rail tiles (keep `aria-label`, `aria-disabled`, `tabindex`). Test unchanged except nothing. Commit `[FEAT] front: ranking page in the scoreboard style`.

## Task 5: Disciplines grid and discipline page

**Files:** `disciplines/+page.svelte`, `disciplines/page.test.js`, `disciplines/[id]/+page.svelte`, `disciplines/[id]/page.test.js`, `front/src/lib/edition.js` (+ test) for the subtitle.

- [ ] `edition.js`: add `disciplineSubtitle(summary, discipline)` → `'5 rounds · 15 games'` (rounds and games of that discipline, singular when 1) or `'points'` / `'time'` / `''` by `result_type`; test it in `edition.test.js` with the fixture (Relay → `2 rounds · 3 games`, Orienteering → `1 round · 1 game`, a discipline without rounds → `points`).
- [ ] Grid: breadcrumb, cards per spec (`class:dimmed={!discipline.reveal_score}`), test adds an assertion on the Relay subtitle.
- [ ] Discipline page: breadcrumb with three items, `h1` with icon tile, rows with `MedalRank` and the difference (`formatDifference`) in muted before the points, schedule rendered with `GameRow` per game, round header `ROUND N` + `k games` / `k to play`; tests: update the schedule regexes to the colon form (`/Bisons\s*12 : 9\s*Aigles/`, `/Cerfs\s*— : —\s*Bisons/`, `/Aigles\s*played\s*Bisons/`), keep every other assertion. Commit `[FEAT] front: disciplines grid and discipline page in the scoreboard style`.

## Task 6: Teams grid and team page

**Files:** `teams/+page.svelte`, `teams/page.test.js`, `teams/[id]/+page.svelte`, `teams/[id]/page.test.js`.

- [ ] Grid: rank order via `rankedTeams`, card per spec with `MedalRank`, roster inline `A · B · C`; test: links now in rank order (`Bisons`, `Aigles`, `Cerfs`), update the assertion.
- [ ] Team page: breadcrumb, `h1`, standing line, roster chips, tiles per spec (keep `data-testid="discipline-row"` on each tile so the existing two-row test holds: `Relay 2 5 pts` → make the tile text `Relay 2nd 5 pts` and update the regex to `/Relay\s*2nd\s*5 pts/`, unrevealed `/Orienteering\s*—/`), games rows per spec keeping `data-testid="game-row"` and the text shape `Round 1 · vs Bisons · 9 : 12 · lost` (update the four regexes to colons). Commit `[FEAT] front: teams grid and team page in the scoreboard style`.

## Task 7: Error page, login, static fallback

**Files:** `+error.svelte`, `error.html`, `login/login.svelte`.

- [ ] Tokens only: backgrounds, accent button, display-face `h1`, Inter inputs with a `--line` bottom border and accent focus. `error.html` inline colours `#0a0a0a` / `#F9F3C1` / Inter fallback. Commit `[FEAT] front: error and login pages on the tokens`.

## Task 8: Cleanup, smoke, docs, PR

- [ ] Remove the `--color-*` aliases from `styles.css`; `grep -rn "color-theme\|color-bg" front/src` must be empty. `npm test`, `npm run build`.
- [ ] Browser smoke on `http://localhost:5173`: hub, ranking, disciplines, Rugby, teams, LOS TIGRES, `/1999`, `/login`, each at desktop and 375 px (tab bar present on inner pages only, breadcrumb links work, year switch keeps the section).
- [ ] CLAUDE.md: Presentation paragraph rewritten (tokens in `styles.css`, one dark theme, components list, tab bar and breadcrumb), remove the `.hub` sentence.
- [ ] Push `claude/scoreboard-ui`, `gh pr create --base dev` with a before/after note and the mockup filenames.
