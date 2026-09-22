# Scoreboard UI — design

Date: 2026-09-22

## Goal

Make the front feel like a finished app instead of a prototype: one visual
identity on every page, data presented for scanning, and navigation that
always shows where you are. Decided in a visual brainstorm (mockups under
`.superpowers/brainstorm/91113-1790101156/content/`, gitignored, kept on the
author's machine): direction "Scoreboard" over "Editorial" and "Club",
compact schedule rows over match cards, result tiles over a table, a bottom
tab bar over the hamburger, Bebas Neue + Inter, and the eclipse stays on the
hub. Where a mockup and this document disagree, this document wins: the
mockups were drawn before the test contract was checked.

## Current behaviour

- Two themes: the hub is black with a pale accent, every other page is white
  with black text, switched by a `.hub` class. Body font is Arial; a Fira Mono
  import is unused.
- Ranking rows and discipline rows are pale cards with gold, silver and bronze
  gradient backgrounds for the top three; the disciplines and teams grids are
  bare cards with a hidden `h1`; the team page is a plain table; the schedule
  and games sections are unstyled lists.
- Navigation is a top bar with three uppercase links, a year `<select>`, and a
  hamburger overlay on phones which is also the only way to reach the Photos
  link on a phone. No breadcrumb.

## Decisions

- **One dark theme** on every page. Tokens in `styles.css`, no `.hub` split.
- **Type:** Bebas Neue for headings, numbers, navigation and labels that act
  as headings; Inter for everything else. **Self-hosted** woff2 files under
  `front/static/fonts/` with `@font-face` and `font-display: swap`: no
  third-party request on the event's phone network and no Google Fonts GDPR
  question. System fallbacks in the stacks.
- **Uppercase is always CSS** (`text-transform: uppercase`); markup keeps
  sentence case so accessible names and tests read "Round 1", "won",
  "Ranking".
- **Medals as accents only:** a coloured left border plus rank digit on
  ranking rows, a coloured top bar plus ordinal on result tiles. No gradient
  backgrounds.
- **Navigation:** desktop top bar with logo, year pill, section tabs; phone
  top bar with logo and year pill plus a fixed bottom tab bar with the three
  sections and, when the edition has a `photos_url`, a fourth external
  "Photos" item. Breadcrumb on every inner page. Breakpoint: tabs and
  desktop layout from 1000 px up, tab bar at 999 px and below.
- **Schedule** as compact rows; **team results** as tiles; **teams grid** in
  rank order with the roster inline; **disciplines grid** with a subtitle.
- **Hub** keeps the eclipse image and the discipline icon columns.
- **Scope:** front only. No API change, no new data. Behaviour (links,
  reveal rules, 404s, redirects, the Photos link on every screen size)
  unchanged.

## Design tokens (`front/src/routes/styles.css`)

```css
:root {
	--bg: #0a0a0a;            /* page */
	--bg-raised: #141414;     /* rows, cards, tiles */
	--bg-sunken: #121212;     /* schedule rows */
	--line: #262626;          /* borders, rules */
	--line-strong: #2a2a2a;   /* neutral rank border */
	--ink: #ffffff;           /* headings, winners */
	--text: #f2ecc8;          /* body */
	--muted: #8a8674;         /* secondary */
	--faint: #6f6b5c;         /* tertiary, unranked digits */
	--ghost: #4f4c40;         /* placeholders (dashes) */
	--accent: #F9F3C1;        /* brand */
	--gold: #e6b800;  --silver: #c9c9c9;  --bronze: #cd7f32;
	--win: #7bd88f;   --loss: #d87b7b;    --todo: #4f8cff;
	--font-display: 'Bebas Neue', 'Arial Narrow', Impact, sans-serif;
	--font-body: Inter, -apple-system, 'Segoe UI', Roboto, sans-serif;
	--radius: 6px;  --radius-lg: 10px;  --radius-pill: 999px;
	--page: min(96%, 900px);  /* every inner page's content column */
	--tabbar: 64px;           /* bottom tab bar height on phones */
}
```

Body: `background: var(--bg); color: var(--text); font-family: var(--font-body);
margin: 0`. `h1`–`h3` in the display face, `letter-spacing: 0.06em`,
`font-weight: 400`, colour `--ink`, sizes 2.75rem / 1.4rem / 1.1rem. Utilities:
`.label` (Inter 600 0.75rem, `letter-spacing: 0.1em`, uppercase, `--muted`),
`.num` (display face, `font-variant-numeric: tabular-nums`), `.dimmed`
(`opacity: 0.35`, and `pointer-events: none` when on a link), `.page`
(`width: var(--page); margin-inline: auto`), `.visually-hidden` kept. Every
inner page wraps its content in `.page`. The typo `view-transision-name` and
the Fira Mono import are dropped. The `.app` wrapper gets
`padding-bottom: var(--tabbar)` at 999 px and below only when it carries the
`has-tabbar` class (see layout), so the hub and the login page keep no dead
strip.

During the transition the file also keeps aliases `--color-bg-0: var(--bg)`,
`--color-theme-1: var(--accent)`, `--color-theme-2: var(--accent)`,
`--color-text: var(--text)` so pages not yet migrated still render; the last
task removes them and checks `grep -rn -- "--color-\|--font-mono\|--column-width" front/src`
is empty.

## Components (`front/src/lib/components/`, imported by explicit path)

- `Header.svelte` (moved from `routes/`): logo, year pill (`<select>` styled
  as a bordered pill; keep the `selected` attribute on the current option and
  its comment, Svelte 4 SSR ignores `value` on `<select>`), section tabs in
  the display face, active tab in accent, `aria-current` by `startsWith` as
  today, Photos tab when `photos_url` is set. Tabs hidden at 999 px and
  below. The year is `($page.error ? null : $page.params.year) ?? $page.data.latestYear`
  as today. `view-transition-name: navbar` stays here and is not reused.
- `TabBar.svelte`: props `year`, `pathname`, `photosUrl = null`. Renders
  nothing when `year` is null, undefined or NaN. A fixed bottom `nav` with
  Ranking, Teams, Disciplines (hrefs `/{year}/...`) and, when `photosUrl` is
  set, Photos (external, `target="_blank"`). Active item: the one whose href
  is a prefix of `pathname`, with `aria-current="page"`. Labels in the
  display face, an icon placeholder square above each; display `none` from
  1000 px up.
- `Breadcrumb.svelte`: `items: [{label, href?}]`, `<nav aria-label="Breadcrumb">`,
  items joined by `›` in separate `<span>`s so link names stay exact; the
  last item is not a link and is in accent; `.label` typography.
- `MedalRank.svelte`: props `rank`, `ordinal = false`. Renders the rank in the
  display face with class `gold` / `silver` / `bronze` for 1, 2, 3, `none`
  for other numbers and for `null` (rendered as `—`). With `ordinal`, renders
  `1st`, `2nd`, `3rd`, `4th`, `11th`… using `ordinal(n)` from `edition.js`
  (moved there from the team page, unit-tested).
- `GameRow.svelte` (discipline schedule): props `team1Name`, `team2Name`,
  `score1`, `score2`, `isPlayed`, `refereeName`, optional `team1Href`,
  `team2Href`. Root element carries `data-testid="game-row"`. Text order:
  team1, score, team2, then `ref: {refereeName}` on its own line. Score cell:
  `13 : 0` in the display face when played with scores; `— : —` in ghost when
  unplayed; `played` in muted when played but scores null. Winner name gets
  class `winner` (ink, weight 600), loser `loser` (muted); on a draw or
  without scores neither.
- `TeamGameRow.svelte` (team page games): props `round` (0-based), `role`
  (`play` | `referee`), `opponentName`, `team1Name`, `team2Name`, `isPlayed`,
  `ownScore`, `theirScore`, `result` (`win` | `loss` | `draw` | null). Root
  carries `data-testid="game-row"`. Text keeps literal ` · ` separators
  between cells, exactly: `Round 1 · vs Bisons · 9 : 12 · lost`,
  `Round 1 · vs Cerfs · to play`, `Round 1 · vs Bisons · played` (played,
  scores null), `Round 1 · referee · Cerfs vs Bisons`. Outcome word classes:
  `won` in `--win`, `lost` in `--loss`, `draw` in text, `to play` in
  `--todo`, `referee` in muted; the round cell in `.label`.
- `menu.svelte` is deleted; `Footer` is already gone.

## Layout (`front/src/routes/+layout.svelte`)

Renders `Header`, `main`, and `TabBar` with `year`, `pathname` and
`photosUrl` (from `$page.data.editions` for the current year) when the route
is not the hub (`/`, `/[year=year]`) nor `/login`; the same flag adds
`has-tabbar` to `.app`. This is the only place route ids are read.

## Pages

**Hub** (`EditionHub.svelte`): eclipse, title image and icon columns as now.
The date line in the display face 1.1rem letter-spaced accent; countdown
digits in the display face 3rem, the unit words styled through the
countdown `div` itself (`<div class="label"><span class="num">{n}</span>Days</div>`,
the word stays a bare text node beside the digit span, the existing test
depends on it); Ranking button `background: var(--accent); color: var(--bg);
font-family: var(--font-display); font-size: 1.6rem; letter-spacing: .15em;
padding: .7rem 3rem; border-radius: var(--radius)` with the link text
`Ranking` in sentence case; year chips bordered `--faint` in the display face.

**Ranking:** `.page`; breadcrumb `[year] › Ranking`; `h1 Ranking`; the
discipline rail as 44 px square tiles (accent background, icon `alt=""`,
`aria-label` the discipline name, `.dimmed` + `aria-disabled` + `tabindex=-1`
when unrevealed), DOM order rail then rows, desktop keeps the existing
`order` swap so the rail sits to the right; rows keep `data-testid="team-row"`,
the row is the `<a>` with `class:gold/silver/bronze`, content `MedalRank`,
name, points as `33 pts` in the display face (the `pts` suffix stays),
left border in the medal colour or `--line-strong`.

**Disciplines:** `.page`; breadcrumb `[year] › Disciplines`; real `h1
Disciplines` (the hidden-`h1` hack goes); two-column card grid (one below
580 px): each card an `<a>` with `aria-label={discipline.name}` (so the link
name stays the bare name), icon tile (`alt=""`), name in the display face,
subtitle in `.label`: `disciplineSubtitle(summary, discipline)` →
`N rounds · M games` counting the discipline's rounds and games (singular
for 1, `0 games` allowed) when it has rounds, else `points` / `time` / `` by
`result_type`; `reveal_score` does not change the subtitle, it adds
`.dimmed`.

**Discipline:** `.page`; breadcrumb `[year] › Disciplines › [name]`; `h1`
containing the icon as `<img alt="">` then the name; result rows keep
`data-testid="result-row"`, the row is the `<a>` with the medal classes,
content `MedalRank`, name, the difference in muted (`+4`), then `10 pts` in
the display face (timed: the time); "Results not revealed yet" in muted when
hidden; `h2 Schedule`; per round a flex header with `<h3>Round {n}</h3>` and
a sibling `.label` with `k games` or `k to play` (count of unplayed), never
inside the heading; then `GameRow`s. Rounds without games render nothing.

**Teams:** `.page`; breadcrumb `[year] › Teams`; real `h1 Teams`; one card
per team in rank order (`rankedTeams`), `data-testid="team-card"`, the card is
the `<a>`: `MedalRank`, name (weight 600), roster with each player in its own
`<span>` and the `·` added by CSS (`span + span::before { content: ' · ' }`),
points as `33 pts` in the display face.

**Team:** `.page`; breadcrumb `[year] › Teams › [name]`; `h1` name; standing
line with `data-testid="standing"`: `2nd` (gold/silver/bronze/text by rank,
display face), `overall` label, `3` in ink display face, `pts` label; roster
as pill chips; `h2 Results`; tiles in `repeat(3, 1fr)` above 580 px and
`repeat(2, 1fr)` below, each `data-testid="discipline-row"`: icon (`alt=""`),
discipline name in `.label`, `MedalRank` with `ordinal` (`2nd`), value
(`5 pts` or the time), top border in the medal colour; unrevealed tiles show
`—` for the rank and `not revealed` in muted, so their text starts
`Orienteering —`. `h2 Games`; per discipline a `.label` heading then
`TeamGameRow`s.

**Error page and login:** same tokens; the error page keeps its shape.
`error.html` (static, outside the layout) gets `#0a0a0a` / `#F9F3C1` inline
with the system fallbacks (no font files).

## Behaviour that must not change

Routes, redirects, 404s, the reveal rules, the Photos link on desktop and
phone, year switching through `switchYearPath`, the hub countdown and phase
logic, every existing `href`.

## Tests

The existing page and component tests are the contract. Assertions that
change because the text shape changes are rewritten in the same commit as
the page, and only these:

- `ranking/page.test.js`: rows `/1\s*Bisons\s*5 pts/`, `/2\s*Aigles\s*3 pts/`,
  `/3\s*Cerfs\s*2 pts/` (no dot after the rank).
- `disciplines/[id]/page.test.js`: result rows `/1\s*Bisons\s*\+4\s*10 pts/`,
  `/2\s*Aigles\s*-2\s*5 pts/`, `/3\s*Cerfs\s*-2\s*0 pts/`; schedule rows
  `/Bisons\s*12 : 9\s*Aigles/`, `/Cerfs\s*— : —\s*Bisons/`,
  `/Aigles\s*7 : 7\s*Cerfs/`; `ref: Cerfs`, the `Round 1` heading, the
  `Bisons` link and the rest unchanged.
- `disciplines/page.test.js`: unchanged (link names via `aria-label`), plus an
  assertion that the Relay card shows `2 rounds · 3 games`.
- `teams/page.test.js`: cards via `getAllByTestId('team-card')` in rank order
  `/2026/teams/2`, `/2026/teams/1`, `/2026/teams/3`; `Ana Lopez` unchanged
  (own span).
- `teams/[id]/page.test.js`: `getByTestId('standing')` has text
  `/2nd\s*overall\s*3\s*pts/`; tiles `/Relay\s*2nd\s*5 pts/`,
  `/Orienteering\s*—/`; game rows `/Round 1 · vs Bisons · 9 : 12 · lost/`,
  `/Round 1 · referee · Cerfs vs Bisons/`, `/Round 2 · vs Cerfs · 7 : 7 · draw/`,
  `/Round 1 · vs Bisons · played/`, `/Round 1 · vs Cerfs · to play/`,
  `/Round 1 · vs Aigles · 12 : 9 · won/`; the `load` 404 test unchanged.
- `EditionHub.test.js`: unchanged.
- New: `Breadcrumb`, `MedalRank` (digits, `none`, `null`, `ordinal`),
  `GameRow` (three score states, winner/loser classes, draw, link), `TabBar`
  (three links, active by prefix on `/2026/teams/1`, nothing for `null`
  year, Photos item when `photosUrl`), `TeamGameRow` (five states),
  `ordinal` and `disciplineSubtitle` in `edition.test.js`.

`Header` stays untested (reads `$page`), as today.

## Out of scope

Organiser tools; per-discipline colours; animations beyond the existing view
transitions; a light theme; an app icon or PWA manifest.
