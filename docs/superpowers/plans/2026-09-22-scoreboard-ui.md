# Scoreboard UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Implementers run ONE AT A TIME on this checkout (shared git index).

**Goal:** Restyle the SvelteKit front into the dark "Scoreboard" identity: one theme, self-hosted Bebas Neue + Inter, medal accents, breadcrumbs, a bottom tab bar on phones, compact schedule rows and result tiles.

**Architecture:** Design tokens in `styles.css` drive every page; six small components (`Header`, `TabBar`, `Breadcrumb`, `MedalRank`, `GameRow`, `TeamGameRow`) carry the shared pieces; each page is restyled in its own commit against its existing tests, with the exact assertion rewrites listed in the spec. No API or data change.

**Tech Stack:** SvelteKit 2 / Svelte 4, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-22-scoreboard-ui-design.md`. It is the contract: tokens, component props, per-page markup rules and the exact test rewrites live there and are not repeated below. Where a mockup and the spec disagree, the spec wins.

**Reference mockups** (author's machine, gitignored): `.superpowers/brainstorm/91113-1790101156/content/direction.html` (card A), `discipline-page.html` (variant 1), `team-page-nav.html` (variants 2 and 4), `type-and-grids.html`. Copy their CSS values for spacing, sizes and colours.

---

## Working environment

Main checkout `/Users/shoklah/Work/Playground/Olympic-Warriors`, branch `claude/scoreboard-ui`. `front/.env` exists. `node_modules` lives in the front container's anonymous volume, so run tests and builds INSIDE the container: `docker compose exec -T front npm test`, `docker compose exec -T front npm run build`. The compose front on `http://localhost:5173` serves this checkout live for visual checks.

Commit prefix `[FEAT]`/`[FIX]`/`[TEST]`/`[DOCS]`, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Never `git reset`, `git stash` or `git checkout`.

---

## File structure

| File | Task | Change |
|---|---|---|
| `front/static/fonts/*.woff2`, `front/src/routes/styles.css` | 1 | self-hosted fonts, tokens, base type, utilities; aliases kept until Task 8 |
| `front/src/app.html` | 1 | `<title>`, preload of the two font files |
| `front/src/routes/+layout.svelte` | 1, 2 | Task 1: drop the `hub` class logic; Task 2: import `Header` from `$lib/components/Header.svelte`, add `TabBar` and `has-tabbar` |
| `front/src/lib/edition.js` (+ test) | 2, 5 | `ordinal(n)` (Task 2), `disciplineSubtitle` (Task 5) |
| `front/src/lib/components/Header.svelte` | 2 | `git mv` from `routes/`, restyled, no mobile menu |
| `front/src/lib/components/{TabBar,Breadcrumb,MedalRank,GameRow,TeamGameRow}.svelte` (+ tests) | 2 | new |
| `front/src/routes/menu.svelte` | 2 | delete (only `Header` imports it) |
| `front/src/lib/components/EditionHub.svelte` | 3 | restyle, test unchanged |
| `front/src/routes/[year=year]/ranking/+page.svelte` (+ test) | 4 | restyle |
| `front/src/routes/[year=year]/disciplines/+page.svelte`, `disciplines/[id]/+page.svelte` (+ tests) | 5 | restyle, subtitle, `GameRow` |
| `front/src/routes/[year=year]/teams/+page.svelte`, `teams/[id]/+page.svelte` (+ tests) | 6 | rank order, tiles, `TeamGameRow` |
| `front/src/routes/+error.svelte`, `front/src/error.html`, `front/src/routes/login/login.svelte` | 7 | tokens |
| `CLAUDE.md` | 8 | presentation paragraph |

---

## Task 1: Fonts, tokens, base styles

- [ ] **Fonts.** Download the latin woff2 files into `front/static/fonts/`: Bebas Neue 400 and Inter 400, 500, 600, 700. Obtain the URLs from `curl -A "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/120 Safari/537.36" "https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&display=swap"` (the latin `@font-face` blocks, `unicode-range` starting `U+0000-00FF`) and `curl -o` each file as `bebas-neue-400.woff2`, `inter-400.woff2`, … Both families are OFL; add `front/static/fonts/OFL.txt` with the licence text from either family's GitHub repo (or a one-line pointer to it if fetching fails; report which). Total should be under 500 KB; report the sizes.
- [ ] **`styles.css`:** rewrite per the spec's token section: `@font-face` rules (`font-display: swap`, `src: url('/fonts/…') format('woff2')`), `:root` tokens, the four transition aliases, body, headings, `a`, `ul`, `.label`, `.num`, `.dimmed`, `.page`, `.visually-hidden`, `.app.has-tabbar` padding at `max-width: 999px`. No `.hub`, no Fira Mono import, no `view-transision-name`.
- [ ] **`app.html`:** `<title>Olympic Warriors</title>` and `<link rel="preload" as="font" type="font/woff2" crossorigin href="%sveltekit.assets%/fonts/bebas-neue-400.woff2">` (same for `inter-400.woff2`).
- [ ] **`+layout.svelte`:** remove `HUB_ROUTES`, `isHub` and `class:hub`; keep the `page` import (Task 2 uses it); `.app` keeps `min-height: 100vh` but loses its background rule.
- [ ] Verify: `docker compose exec -T front npm test` green (nothing asserts on colours), `npm run build` ok, `http://localhost:5173/2026/ranking` renders dark with the new fonts (`document.fonts.check("1em 'Bebas Neue'")` true in the browser console), `curl -sI http://localhost:5173/fonts/inter-400.woff2` 200. Commit `[FEAT] front: scoreboard tokens, self-hosted fonts and base styles`.

## Task 2: Components (TDD) and layout wiring

- [ ] **Tests first**, per the spec's Tests section: `Breadcrumb.test.js`, `MedalRank.test.js` (1 → `gold` and text `1`; 2 `silver`; 3 `bronze`; 4 `none`; `null` → `—` with `none`; `{rank: 2, ordinal: true}` → `2nd`), `GameRow.test.js`, `TabBar.test.js` (`{year: 2026, pathname: '/2026/teams/1'}` → `Teams` has `aria-current="page"`, hrefs `/2026/ranking` `/2026/teams` `/2026/disciplines`; `year: null` renders nothing; `photosUrl: 'https://x'` adds a `Photos` link with `target="_blank"`), `TeamGameRow.test.js` (the five text shapes from the spec, `won` has class `won`), and in `edition.test.js` the `ordinal` cases 1 → `1st`, 2 → `2nd`, 3 → `3rd`, 4 → `4th`, 11 → `11th`, 12 → `12th`, 13 → `13th`, 21 → `21st`, 22 → `22nd`, 23 → `23rd`, 101 → `101st`, 111 → `111th`.
- [ ] Run: fail on missing modules.
- [ ] **Implement** per the spec's component contracts. `ordinal(n)` moves from `teams/[id]/+page.svelte` into `edition.js` (exported); the team page imports it until Task 6 rewrites it. `git mv front/src/routes/Header.svelte front/src/lib/components/Header.svelte`, remove the `Menu` import and markup, keep the `<select>` with `selected` and its comment, restyle to the tokens (top bar padding 12px 18px, bottom rule `--line`, logo 2.2rem high, year pill display face bordered accent, tabs display face 1.1rem letter-spaced, active in accent, hidden at `max-width: 999px`). `git rm front/src/routes/menu.svelte`. `+layout.svelte`: import `Header` and `TabBar` by explicit path, `const HUB_OR_LOGIN = new Set(['/', '/[year=year]', '/login'])`, `$: showTabBar = !HUB_OR_LOGIN.has($page.route.id)`, `$: year = ($page.error ? null : $page.params.year) ?? $page.data.latestYear`, `$: photosUrl = ($page.data.editions ?? []).find((e) => e.year === Number(year))?.photos_url ?? null`, render `<TabBar {year} pathname={$page.url.pathname} {photosUrl} />` inside `{#if showTabBar}` and `class:has-tabbar={showTabBar}` on `.app`.
- [ ] Verify: tests green, build ok, phone width on `/2026/ranking`: tab bar with three items, no hamburger, top bar with logo and year; `/` and `/login`: no tab bar, no bottom padding. Commit `[FEAT] front: header, tab bar, breadcrumb, medal rank and game row components`.

## Task 3: Hub

- [ ] Restyle `EditionHub.svelte` per the spec's Hub paragraph (keep eclipse, title image, icon columns; countdown structure exactly `<div class="label"><span class="num">{parts.days}</span>Days</div>`). `EditionHub.test.js` unchanged and green. Commit `[FEAT] front: hub in the scoreboard style`.

## Task 4: Ranking page

- [ ] Restyle per the spec's Ranking paragraph; rewrite the three row regexes in `ranking/page.test.js` as listed in the spec's Tests section; everything else in that test unchanged. Commit `[FEAT] front: ranking page in the scoreboard style`.

## Task 5: Disciplines grid and discipline page

- [ ] `edition.js`: `disciplineSubtitle(summary, discipline)` with tests (fixture: Relay → `2 rounds · 3 games`, Orienteering → `1 round · 1 game`, a discipline without rounds and `result_type: 'PTS'` → `points`, `'TIM'` → `time`, `'NON'` → ``).
- [ ] Grid per the spec's Disciplines paragraph (`aria-label` on the card link, `alt=""` icon, real `h1`); add the Relay subtitle assertion.
- [ ] Discipline page per the spec's Discipline paragraph (`h1` icon `alt=""`, `<h3>Round {n}</h3>` with the count in a sibling, `GameRow` per game, `ref: ` prefix comes from `GameRow`); rewrite the six regexes listed in the spec's Tests section, keep the rest. Commit `[FEAT] front: disciplines grid and discipline page in the scoreboard style`.

## Task 6: Teams grid and team page

- [ ] Grid per the spec's Teams paragraph (`data-testid="team-card"`, each player in its own `<span>`); rewrite the link assertion to `getAllByTestId('team-card')` hrefs in rank order; `Ana Lopez` assertion unchanged.
- [ ] Team page per the spec's Team paragraph (`data-testid="standing"`, tiles with `data-testid="discipline-row"`, `TeamGameRow`s); rewrite the standing, tile and game-row assertions exactly as listed in the spec's Tests section; the `load` 404 test unchanged. Commit `[FEAT] front: teams grid and team page in the scoreboard style`.

## Task 7: Error page, login, static fallback

- [ ] Tokens only (`+error.svelte`, `login/login.svelte`: Inter inputs with a `--line` bottom border and accent focus, accent button; `error.html`: inline `#0a0a0a` / `#F9F3C1`, system fonts). Commit `[FEAT] front: error and login pages on the tokens`.

## Task 8: Cleanup, smoke, docs, PR

- [ ] Remove the four aliases from `styles.css`; `grep -rn -- "--color-\|--font-mono\|--column-width" front/src` must be empty; tests and build green.
- [ ] Browser smoke on `http://localhost:5173`: hub, ranking, disciplines, Rugby, teams, LOS TIGRES, `/1999`, `/login`, each at desktop and 375 px (tab bar on inner pages only, Photos item when the edition has a URL, breadcrumb links, year switch keeps the section, fonts loaded from `/fonts/`).
- [ ] CLAUDE.md: Presentation paragraph rewritten (tokens in `styles.css`, one dark theme, self-hosted fonts, the six components, tab bar and breadcrumb), remove the `.hub` sentence.
- [ ] Push `claude/scoreboard-ui`, `gh pr create --base dev` with a before/after note.
