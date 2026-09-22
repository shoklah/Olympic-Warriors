# French translation and shared game rows

**Date:** 2026-09-23
**Status:** approved in conversation, awaiting spec review
**Scope:** `front/` only. No API or database change.

## Goal

The public site speaks French by default and English on request, through a
switch in the header. Along the way the team page shows its games with the
same row as the discipline page, and only the games the team played.

## Decisions taken

- **Languages:** French default, English available, a switch in the header.
- **Locale carrier:** a `lang` cookie, no language segment in the URL. A
  first visit is French whatever the browser's `Accept-Language` says.
- **Mechanism:** a hand-rolled dictionary and one lookup function, no
  dependency. Three conventions keep a later move to Paraglide or
  svelte-i18n a conversion rather than a rewrite: flat key files per
  language, every visible string through one `t` call, the locale resolved
  in one place.
- **Team page games:** the discipline page's `GameRow`, with a round label on
  the left of each row; refereed games are not listed.

## Locale resolution

`front/src/lib/i18n/locale.js` exports `LOCALES = ['fr', 'en']`,
`DEFAULT_LOCALE = 'fr'` and `localeFrom(value)`, which returns `value` when
it is one of `LOCALES` and `DEFAULT_LOCALE` otherwise.

The root `+layout.server.js` reads `cookies.get('lang')`, passes it through
`localeFrom` and returns `locale` next to `editions` and `latestYear`. The
root `+layout.svelte` calls `setContext(I18N, data.locale)` with the key
exported from `$lib/i18n` (the string `'i18n'`, one constant used
everywhere). Components never read the cookie or `$page.data.locale`
themselves; they read the context. Nothing on the client decides the
language, so the server-rendered page is already in the right one.

The `<html lang>` attribute follows the locale: `app.html` carries
`lang="%lang%"` and `hooks.server.js` replaces it in `transformPageChunk`
from the same cookie through `localeFrom`. This is the only other place the
cookie is read, and it uses the same helper.

## The switch

`/lang/+page.server.js` has one default form action. It reads `lang` and
`redirectTo` from the form data, sets the cookie
`lang=<localeFrom(lang)>` with `path: '/'`, `maxAge: 60 * 60 * 24 * 365`,
`sameSite: 'lax'`, `httpOnly: false`, and throws a 303 redirect to
`redirectTo` when it is a local path (starts with a single `/`, not `//`),
else to `/`. A `GET` on `/lang` redirects to `/`. No `+page.svelte` renders
anything.

`Header.svelte` renders, right of the year select:

```html
<form method="POST" action="/lang" class="lang" aria-label={t('header.language')}>
	<input type="hidden" name="redirectTo" value={$page.url.pathname} />
	<button name="lang" value="fr" aria-current={locale === 'fr' ? 'true' : undefined}>FR</button>
	<button name="lang" value="en" aria-current={locale === 'en' ? 'true' : undefined}>EN</button>
</form>
```

Both buttons are always rendered so the control reads as a pair; the current
one is in accent and not clickable in effect (posting the current language
is harmless). Display face, letter-spaced, 44 px minimum touch height like
the year select, `:focus-visible` accent ring. Works without JavaScript; with
it SvelteKit's default form handling still results in a full render of the
redirected page.

## Dictionary and lookup

`front/src/lib/i18n/fr.js` and `en.js` each `export default` one flat object:
dotted key to message. French is the reference file. Placeholders are
`{name}`. A message that counts things is an object of plural forms,
`{ one: '…', other: '…' }`, using the CLDR categories `Intl.PluralRules`
returns for the locale (`one` and `other` are enough for both languages).

`front/src/lib/i18n/index.js` exports:

- `I18N`: the context key.
- `t(locale, key, params = {})`: returns the message for `locale`, else the
  French message, else the key itself. Fills `{name}` from `params`. When the
  message is a plural object, picks the form with
  `new Intl.PluralRules(locale).select(params.n)` and falls back to `other`.
- `translator(locale)`: returns `(key, params) => t(locale, key, params)`.
- `useT()`: `translator(getContext(I18N) ?? DEFAULT_LOCALE)`, for use in a
  component's script: `const t = useT();` then `{t('nav.ranking')}` in the
  template. A component rendered without context is French.
- `disciplineName(locale, name)`: the French name from
  `front/src/lib/i18n/disciplines.js` when `locale === 'fr'` and the map has
  it, else `name` unchanged.

`disciplines.js` maps the database name to the French one:

| Database name | French |
|---|---|
| Relay | Relais |
| Orienteering | Course d'orientation |
| Hide and Seek | Cache-cache |
| Fair | Fête foraine |
| Dodgeball | Balle au prisonnier |
| Obstacle Course | Parcours d'obstacles |
| Geography Quizz | Quiz de géographie |
| General Culture Quizz | Quiz de culture générale |
| Petanque | Pétanque |
| Darts | Fléchettes |
| Rugby, Basketball, Crossfit, Blindtest | unchanged (absent from the map) |

Every place that prints a discipline name (hub icon `alt`, rail `aria-label`,
disciplines grid, discipline page `h1`, breadcrumb, team page tiles and
game headings) goes through `disciplineName`. `iconFor` keeps taking the
database name.

## Keys and messages

French first, English second. Uppercasing stays in CSS, so markup keeps
sentence case and accents.

| Key | fr | en |
|---|---|---|
| `nav.ranking` | Classement | Ranking |
| `nav.teams` | Équipes | Teams |
| `nav.disciplines` | Épreuves | Disciplines |
| `nav.photos` | Photos | Photos |
| `nav.sections` | Rubriques | Sections |
| `header.edition` | Édition | Edition |
| `header.language` | Langue | Language |
| `hub.days` / `hours` / `minutes` / `seconds` | Jours / Heures / Minutes / Secondes | Days / Hours / Minutes / Seconds |
| `hub.ranking` | Classement | Ranking |
| `hub.editions` | Éditions | Editions |
| `ranking.title` | Classement | Ranking |
| `ranking.disciplines` | Épreuves | Disciplines |
| `disciplines.title` | Épreuves | Disciplines |
| `discipline.rounds` | `{one: '{n} tour', other: '{n} tours'}` | `{one: '{n} round', other: '{n} rounds'}` |
| `discipline.games` | `{one: '{n} match', other: '{n} matchs'}` | `{one: '{n} game', other: '{n} games'}` |
| `discipline.toPlay` | `{one: '{n} à jouer', other: '{n} à jouer'}` | `{one: '{n} to play', other: '{n} to play'}` |
| `discipline.points` | points | points |
| `discipline.time` | temps | time |
| `discipline.results` | Résultats | Results |
| `discipline.schedule` | Programme | Schedule |
| `discipline.round` | Tour {n} | Round {n} |
| `discipline.roundShort` | T{n} | R{n} |
| `discipline.notRevealed` | Résultats non dévoilés | Results not revealed yet |
| `game.played` | joué | played |
| `game.referee` | arbitre : {name} | ref: {name} |
| `teams.title` | Équipes | Teams |
| `team.overall` | au général | overall |
| `team.pts` | pts | pts |
| `team.results` | Résultats | Results |
| `team.games` | Matchs | Games |
| `team.notRevealed` | non dévoilé | not revealed |
| `team.unknown` | Inconnue | Unknown |
| `breadcrumb.label` | Fil d'Ariane | Breadcrumb |
| `error.back` | Retour aux Olympic Warriors | Back to the Olympic Warriors |
| `error.notFound` | Page introuvable | Page not found |
| `login.title` | Connexion | Log In |
| `login.username` | Identifiant | Username |
| `login.password` | Mot de passe | Password |
| `login.missing` | Champ obligatoire | Required |

The `+error.svelte` page uses `error.back` and shows the thrown message as
today; `error.notFound` covers the 404 the detail loaders throw
(`throw error(404, ...)` keeps its message in English for the API layer; the
page shows `error.notFound` when `status === 404`, else the message). The
implementer adds any key the pages need that this table misses, in both
files, and lists it in the PR.

`pts`, `— : —`, `FR`, `EN`, the brand `Olympic Warriors`, the `OW` logo, the
title image and every piece of data (team, host and player names, years,
rule and photo URLs) are not translated.

## Helpers

`edition.js` keeps no English:

- `disciplineSubtitle(summary, discipline)` returns
  `{ rounds, games }` when the discipline has rounds, else
  `{ resultType }` with the raw `result_type`. The disciplines grid prints
  `t('discipline.rounds', {n}) · t('discipline.games', {n})`, or
  `discipline.points` / `discipline.time` / nothing for `NON`.
- `roundCount(round)` returns `{ left, total }`. The discipline page prints
  `discipline.toPlay` with `left` when `left > 0` (and gives it the `todo`
  class), else `discipline.games` with `total`.
- The `plural` helper is deleted.
- `formatDateRange(start, end, locale)` uses `toLocaleDateString(locale, …)`
  with the same three shapes: `19 – 20 septembre 2026`,
  `19 septembre 2026`, `30 septembre – 1er octobre 2026` (the first of a month is
  `1er` in French); English unchanged
  (`19 – 20 September 2026`).
- `ordinal(n, locale)`: French `1re` for 1 (the rank describes a team,
  feminine) and `{n}e` otherwise; English as today. `MedalRank` takes the
  locale from context and passes it on.
- `teamGames(summary, teamId)` returns, per discipline in database order,
  only the games where the team is `team1` or `team2` (a team listed as
  referee of its own game still counts as playing). Each game carries
  `id`, `round` (0-based order), `team1Id`, `team2Id`, `team1Name`,
  `team2Name`, `score1`, `score2`, `isPlayed`, `refereeName` (or `null`).
  `role`, `opponentId`, `opponentName`, `ownScore`, `theirScore`, `result`
  and `gameResult` are deleted. Disciplines without such a game are omitted.

## Game rows

`TeamGameRow.svelte` and its test are deleted. `GameRow.svelte` gains two
optional props:

- `roundLabel = null`: when set, a first `<span class="round label">` with
  the text, in a fixed narrow column (`min-width: 2.4rem`) left of the
  pairing.
- `highlightId = null` with `team1Id = null` and `team2Id = null`: the team
  whose id equals `highlightId` gets class `own`, accent colour, and is
  rendered as a `<span>` even when a href is given; the other team keeps its
  link. The winner/loser classes still apply on top.

The discipline page passes none of these, so its rows do not change. The
team page renders, under `t('team.games')`, one `<h3 class="label">` per
discipline with the translated name, then one `GameRow` per game with
`roundLabel={t('discipline.roundShort', {n: game.round + 1})}`,
`highlightId={data.team.id}`, both hrefs, the scores, `isPlayed` and
`refereeName`. The section is hidden when the team has no game.

Text shapes on the team page (English): `R1 Bisons 12 : 9 Aigles ref: Cerfs`
with `Aigles` carrying `own` and `loser`; an unplayed game `R1 Aigles — : —
Cerfs`; a played hidden score `R1 Aigles played Bisons`.

## Styles

The `.lang` form in the header follows the year select: transparent
background, accent border on the pair, buttons in the display face 1.1rem,
letter-spacing 0.08em, `--muted` text, the `aria-current` one `--accent` on
`--bg-raised`. `GameRow`'s `.round` column uses the `.label` utility in `--muted` (never
`--faint`, which is for large text only). `.team.own` is `var(--accent)`
and keeps `font-weight: 600` when it is also `winner`.

## Static fallback

`error.html` renders before any layout and cannot read the cookie. Its
heading and its link carry both languages, French first, on one line each:
`Quelque chose s'est mal passé · Something went wrong`,
`Retour aux Olympic Warriors · Back to the Olympic Warriors`.

## Tests

`front/src/lib/test-utils.js` exports
`renderWith(Component, props, locale = 'en')` which calls testing-library's
`render(Component, { props, context: new Map([[I18N, locale]]) })`. Every
existing page and component test switches to it and keeps its English
assertions. New coverage:

- `i18n/index.test.js`: `t` returns the message, fills placeholders, picks
  `one`/`other` in both locales, falls back to French for a missing English
  key and to the key for an unknown one; `translator`; `disciplineName`
  returns the French name, the database name in English, and the database
  name for an unmapped discipline.
- `i18n/parity.test.js`: `Object.keys(fr)` equals `Object.keys(en)` as sets,
  and every plural message has `one` and `other` in both.
- `icons.test.js` also asserts every name in
  `DISCIPLINE_NAMES` either is in the French map or is one of the four kept
  as is, so a new discipline fails until it is named.
- `edition.test.js`: `formatDateRange` and `ordinal` in `fr`;
  `disciplineSubtitle` and `roundCount` return objects; `teamGames` returns
  the new shape without referee rows (`teamGames(summary, 1)` gives Relay
  games 200 and 202 and Orienteering game 203; `teamGames(summary, 3)` gives
  Relay game 201 and 202 only).
- `locale.test.js`: `localeFrom` for `'en'`, `'fr'`, `'de'`, `undefined`.
- `lang/page.server.test.js`: the action sets the cookie and redirects to a
  local path; a `//evil` or absolute `redirectTo` goes to `/`.
- `Header.test.js` (new): the switch shows `FR` with `aria-current` under
  `fr`, `EN` under `en`, and the hidden `redirectTo` carries the path; tabs
  read `Classement`, `Équipes`, `Épreuves` under `fr`.
- `GameRow.test.js`: `roundLabel` renders first; `highlightId` marks the own
  team with `own` and no link while the other stays a link.
- `teams/[id]/page.test.js`: game rows rewritten to the shapes above, no
  referee row, plus one French render asserting `1re au général`, `Matchs`,
  `T1`.
- `ranking/page.test.js`: one French render asserting the `Classement`
  heading and `Épreuves` rail label.
- `EditionHub.test.js`: one French render asserting `Jours` and
  `Paris · 19 – 20 septembre 2026`.

`npm test` must stay green; CI gates on it.

## Docs

CLAUDE.md, presentation paragraph: every visible string goes through `t`
from `$lib/i18n`, French is the reference file, the parity test, the
discipline map with its coverage test, the cookie and the `/lang` action, the
`renderWith` helper, and the three migration conventions. The `TeamGameRow`
entry becomes the `GameRow` props. The scoreboard spec of 2026-09-22 gets a
note pointing here for `TeamGameRow`.

## Out of scope

Django admin and API messages, the organiser tools (they will use the same
dictionary), a language segment in the URL, `Accept-Language` detection.
