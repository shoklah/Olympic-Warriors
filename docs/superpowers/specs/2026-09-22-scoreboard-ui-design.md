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
hub.

## Current behaviour

- Two themes: the hub is black with a pale accent, every other page is white
  with black text, switched by a `.hub` class. Body font is Arial; a Fira Mono
  import is unused.
- Ranking rows and discipline rows are pale cards with gold, silver and bronze
  gradient backgrounds for the top three; the disciplines and teams grids are
  bare cards; the team page is a plain table; the schedule and games sections
  are unstyled lists.
- Navigation is a top bar with three uppercase links, a year `<select>`, and a
  hamburger overlay on phones. No breadcrumb; inner pages do not say which
  edition or section they belong to.

## Decisions

- **One dark theme** on every page. Tokens in `styles.css`, no `.hub` split.
- **Type:** Bebas Neue for headings, numbers, navigation and labels that act
  as headings; Inter for everything else. Loaded from Google Fonts in
  `app.html`, with `font-display: swap`.
- **Medals as accents only:** a coloured left border plus rank digit on
  ranking rows, a coloured top bar plus ordinal on result tiles. No gradient
  backgrounds.
- **Navigation:** desktop top bar with logo, year pill, section tabs;
  phone top bar with logo and year pill plus a fixed bottom tab bar with the
  three sections. Breadcrumb on every inner page.
- **Schedule** as compact rows; **team results** as tiles; **teams grid** in
  rank order with the roster inline; **disciplines grid** with a subtitle.
- **Hub** keeps the eclipse image and the discipline icon columns.
- **Scope:** front only. No API change, no new data. Behaviour (links,
  reveal rules, 404s, redirects) unchanged.

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
	--font-display: 'Bebas Neue', 'Arial Narrow', sans-serif;
	--font-body: Inter, -apple-system, 'Segoe UI', Roboto, sans-serif;
	--radius: 6px;  --radius-lg: 10px;  --radius-pill: 999px;
	--page: min(96%, 900px);  /* content column */
	--tabbar: 64px;           /* bottom tab bar height on phones */
}
```

Body: `background: var(--bg); color: var(--text); font-family: var(--font-body)`;
`h1`–`h3` in the display face with `letter-spacing: 0.06em`; numbers use
`font-variant-numeric: tabular-nums`. Below 1000 px the body gets
`padding-bottom: var(--tabbar)` so the tab bar never covers content.

## Components (`front/src/lib/components/`)

- `Header.svelte` (moved from `routes/`): logo, year pill (`<select>` styled
  as a bordered pill, `selected` on the current option for SSR), section tabs
  in the display face, active tab in accent. Hidden tabs below 1000 px.
- `TabBar.svelte`: fixed bottom bar, three items (icon placeholder square +
  label in the display face), active in accent, shown below 1000 px only,
  hidden on `/`, `/[year=year]` (the hub) and `/login`.
- `Breadcrumb.svelte`: `items: [{label, href?}]`, renders
  `2026 › Disciplines › Rugby` with the last item in accent, uppercase 12 px
  letter-spaced. Used by ranking, disciplines, discipline, teams, team pages.
- `MedalRank.svelte`: a rank digit in the display face coloured gold, silver,
  bronze or faint; used by the ranking rows, teams grid and result tiles.
- `GameRow.svelte`: the compact schedule row, props `team1Name`, `team2Name`,
  `score1`, `score2`, `isPlayed`, `refereeName`, optional `team1Href`,
  `team2Href`. Score `13 : 0` centred in the display face; `— : —` in ghost
  when unplayed; "played" in muted when played but scores null; winner name
  in ink and weight 600, loser in muted, both in text on a draw.
- The old `menu.svelte` is deleted.

## Pages

**Hub** (`EditionHub.svelte`): eclipse and icon columns as now; title image
stays; the date line, countdown labels, Ranking button and year chips use the
display face and the tokens. No breadcrumb, no tab bar.

**Ranking:** breadcrumb `2026 › Ranking`; `h1 Ranking`; the discipline rail
as 44 px square tiles (accent background, icon inside, dimmed with
`aria-disabled` when unrevealed) above the rows on phones and to the right on
desktop as now; rows: `MedalRank`, name, points in the display face, left
border in the medal colour or `--line-strong`.

**Disciplines:** breadcrumb `2026 › Disciplines`; two-column card grid (one
below 580 px): icon tile, name in the display face, subtitle from the summary:
`N rounds · M games` when the discipline has rounds, else `points` or `time`
from `result_type`; unrevealed cards dimmed.

**Discipline:** breadcrumb `2026 › Disciplines › Rugby`; `h1` with the icon
tile; ranking rows as on the ranking page plus the points difference in muted
before the points (`+26  12`); "Results not revealed yet" in muted when
hidden; `Schedule` section heading, then per round a header line
`ROUND 1` left and `3 games` or `1 to play` right (count of unplayed), then
`GameRow`s.

**Teams:** breadcrumb `2026 › Teams`; one card per team in rank order:
`MedalRank`, name in weight 600, roster on one line in muted
(`A · B · C`), points in the display face on the right.

**Team:** breadcrumb `2026 › Teams › LOS TIGRES`; `h1` name; standing line
`1st` in gold display face, `OVERALL` muted label, `33` in ink display face,
`PTS` label; roster as pill chips; `Results` heading; tiles in a three-column
grid (two on phones): icon, discipline name, ordinal in the medal colour
(`4th` in text when off the podium), value (`12 pts`, `11:48`), top border in
the medal colour; unrevealed tiles show `—` and `not revealed` in muted.
`Games` heading; per discipline a muted uppercase label then `GameRow`-like
rows in the team form: `ROUND 1` label, `vs 3PE`, score in the display face
with the team's own score first, outcome label `WON` (`--win`), `LOST`
(`--loss`), `DRAW` (text), `TO PLAY` (`--todo`), `REFEREE` (muted, with
`A vs B` in place of `vs X`).

**Error page and login:** same tokens; the error page keeps its shape.
`error.html` (static, outside the layout) gets the same background and
accent colours inline.

## Behaviour that must not change

Routes, redirects, 404s, the reveal rules (nulls render as dashes or
"played"), external Photos link, year switching through `switchYearPath`,
the hub countdown and phase logic, every `href`.

## Tests

- Existing page and component tests are the contract: they assert text,
  links, medal classes and `data-testid` rows. They keep passing, with these
  known adjustments: the ranking page and discipline page rows change from
  `.gold/.silver/.bronze` on the row to the same classes on the row (kept),
  the schedule row text becomes `Bisons 12 : 9 Aigles` (colon, not en dash),
  the team page game rows become `Round 1 · vs Bisons · 9 : 12 · lost`.
  Tests that assert those strings are updated in the same commit as the page.
- New component tests: `Breadcrumb` (labels, last item not a link),
  `GameRow` (three score states, winner emphasis), `TabBar` (three links with
  the year in the href, active item by pathname prop), `MedalRank` (class by
  rank).
- `Header` stays untested (it reads `$page`), as today.

## Out of scope

Organiser tools; per-discipline colours; animations beyond the existing view
transitions; a light theme; an app icon or PWA manifest.
