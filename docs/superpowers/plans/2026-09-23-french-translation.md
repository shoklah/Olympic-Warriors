# French Translation and Shared Game Rows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Implementers run ONE AT A TIME on this checkout (shared git index).

**Goal:** The public site renders in French by default and in English through a header switch stored in a cookie; the team page shows its own games with the discipline page's `GameRow`.

**Architecture:** A hand-rolled dictionary (`fr.js`, `en.js`) behind one `t(locale, key, params)` function; the locale is read from the `lang` cookie in the root server layout and handed to components through Svelte context; a `/lang` form action sets the cookie. Pure helpers in `edition.js` stop producing English and return counts the pages turn into text.

**Tech Stack:** SvelteKit 2 / Svelte 4 (plain JS), Vitest 2 + @testing-library/svelte 5 + jest-dom. Tests and builds run inside the compose front container.

**Spec:** `docs/superpowers/specs/2026-09-23-french-translation-design.md`. Where this plan and the spec disagree, the spec wins, except for the two deviations listed under "Deviations from the spec" below.

---

## Working environment

Main checkout `/Users/shoklah/Work/Playground/Olympic-Warriors`, branch `claude/i18n-french` (already created from `dev`, spec committed). `front/.env` exists. `node_modules` lives in the front container's anonymous volume, so run tests and builds INSIDE the container:

```bash
docker compose exec -T front npm test                      # whole suite
docker compose exec -T front npx vitest run src/lib/i18n   # one folder or file
docker compose exec -T front npm run build
```

The compose front on `http://localhost:5173` serves this checkout live for visual checks.

Commit prefixes `[FEAT]`/`[FIX]`/`[TEST]`/`[DOCS]`, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Never `git reset`, `git stash` or `git checkout`. Stage explicit paths, never `git add -A`, because other sessions may leave files in the tree.

Facts verified in the container before this plan was written:
- `render(Component, { props, context: new Map([['i18n', 'en']]) })` from `@testing-library/svelte` injects Svelte context; a component rendered with `render(Component, {})` gets none.
- `vi.mock('$app/stores', …)` and `vi.mock('$app/navigation', …)` work in a test that imports `Header.svelte`.
- `new Intl.PluralRules('fr').select(0)` is `'one'` (French says `0 match`); English gives `'other'` for 0.
- `new Date('2026-09-19T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })` is `19 septembre` in the container's Node.

## Deviations from the spec

1. `nameOf` in `edition.js` returns `null` for an unknown team instead of the English `Unknown`, and the components print `t('team.unknown')` when a name is null. The spec wants `edition.js` free of English; this is how.
2. One key is added, `error.generic` (the message when a non-404 error carries none). The login action's own server messages (`Login failed`) stay English: they come from the API layer. `ranking.disciplines` from the spec's table is used by no page and is not created.

---

## File structure

| File | Task | Change |
|---|---|---|
| `front/src/lib/i18n/locale.js` | 1 | `LOCALES`, `DEFAULT_LOCALE`, `localeFrom` |
| `front/src/lib/i18n/fr.js`, `en.js` | 1 | flat message objects |
| `front/src/lib/i18n/disciplines.js` | 1 | database name → French name |
| `front/src/lib/i18n/index.js` | 1 | `I18N`, `t`, `translator`, `useT`, `useLocale`, `disciplineName` |
| `front/src/lib/i18n/{locale,index,parity}.test.js` | 1 | unit tests |
| `front/src/lib/test-utils.js` | 1 | `renderWith` |
| `front/src/routes/+layout.server.js`, `+layout.svelte` | 2 | locale from cookie into context |
| `front/src/hooks.server.js`, `front/src/app.html` | 2 | `<html lang>` |
| `front/src/routes/lang/+page.server.js` (+ test) | 2 | the switch action |
| `front/src/lib/components/Header.svelte` (+ new test), `TabBar.svelte` (+ test) | 3 | switch, translated tabs |
| `front/src/lib/edition.js` (+ test) | 4 | locale-free subtitle/count, `formatDateRange`/`ordinal` with locale, `nameOf` null |
| `front/src/lib/components/MedalRank.svelte` (+ test), `EditionHub.svelte` (+ test) | 4 | locale-aware ordinal; hub dates and words |
| `front/src/routes/[year=year]/disciplines/+page.svelte`, `disciplines/[id]/+page.svelte` (+ tests) | 4 | translated, new helper shapes |
| `front/src/lib/components/{Breadcrumb,DisciplineRail,GameRow}.svelte` (+ tests) | 5 | translated |
| `front/src/routes/[year=year]/ranking/+page.svelte`, `teams/+page.svelte`, `+error.svelte`, `login/login.svelte` (+ tests) | 5 | translated |
| `front/src/lib/edition.js` `teamGames` (+ test), `GameRow.svelte` props (+ test), `teams/[id]/+page.svelte` (+ test), delete `TeamGameRow.svelte` (+ test) | 6 | team page games |
| `front/src/error.html`, `front/src/lib/icons.test.js`, `CLAUDE.md`, scoreboard spec | 7 | fallback, coverage, docs, smoke, PR |

---

## Task 1: i18n core (TDD)

**Files:**
- Create: `front/src/lib/i18n/locale.js`, `fr.js`, `en.js`, `disciplines.js`, `index.js`
- Create: `front/src/lib/i18n/locale.test.js`, `index.test.js`, `parity.test.js`
- Create: `front/src/lib/test-utils.js`

- [ ] **Step 1: Write the failing tests**

`front/src/lib/i18n/locale.test.js`:

```js
import { describe, expect, it } from 'vitest';
import { DEFAULT_LOCALE, LOCALES, localeFrom } from './locale.js';

describe('localeFrom', () => {
	it('keeps a known locale', () => {
		expect(localeFrom('en')).toBe('en');
		expect(localeFrom('fr')).toBe('fr');
	});

	it('falls back to French for anything else', () => {
		expect(localeFrom('de')).toBe('fr');
		expect(localeFrom(undefined)).toBe('fr');
		expect(localeFrom(null)).toBe('fr');
		expect(localeFrom('')).toBe('fr');
	});

	it('exposes the constants', () => {
		expect(LOCALES).toEqual(['fr', 'en']);
		expect(DEFAULT_LOCALE).toBe('fr');
	});
});
```

`front/src/lib/i18n/index.test.js`:

```js
import { describe, expect, it } from 'vitest';
import { I18N, disciplineName, t, translator } from './index.js';

describe('t', () => {
	it('returns the message of the locale', () => {
		expect(t('fr', 'nav.ranking')).toBe('Classement');
		expect(t('en', 'nav.ranking')).toBe('Ranking');
	});

	it('fills placeholders', () => {
		expect(t('en', 'game.referee', { name: 'Cerfs' })).toBe('ref: Cerfs');
		expect(t('fr', 'game.referee', { name: 'Cerfs' })).toBe('arbitre : Cerfs');
		expect(t('en', 'discipline.round', { n: 2 })).toBe('Round 2');
	});

	it('leaves an unknown placeholder in place', () => {
		expect(t('en', 'game.referee', {})).toBe('ref: {name}');
	});

	it('picks the plural form of the locale', () => {
		expect(t('en', 'discipline.games', { n: 1 })).toBe('1 game');
		expect(t('en', 'discipline.games', { n: 3 })).toBe('3 games');
		expect(t('en', 'discipline.games', { n: 0 })).toBe('0 games');
		expect(t('fr', 'discipline.games', { n: 1 })).toBe('1 match');
		expect(t('fr', 'discipline.games', { n: 3 })).toBe('3 matchs');
		expect(t('fr', 'discipline.games', { n: 0 })).toBe('0 match');
	});

	it('falls back to French for an unknown locale and to the key for an unknown key', () => {
		expect(t('de', 'nav.ranking')).toBe('Classement');
		expect(t('en', 'nope.nothing')).toBe('nope.nothing');
	});

	it('exposes the context key', () => {
		expect(I18N).toBe('i18n');
	});
});

describe('translator', () => {
	it('binds the locale', () => {
		const tr = translator('fr');
		expect(tr('nav.teams')).toBe('Équipes');
		expect(tr('discipline.round', { n: 1 })).toBe('Tour 1');
	});
});

describe('disciplineName', () => {
	it('translates a mapped discipline in French', () => {
		expect(disciplineName('fr', 'Relay')).toBe('Relais');
		expect(disciplineName('fr', 'Hide and Seek')).toBe('Cache-cache');
	});

	it('keeps the database name in English and for an unmapped discipline', () => {
		expect(disciplineName('en', 'Relay')).toBe('Relay');
		expect(disciplineName('fr', 'Rugby')).toBe('Rugby');
		expect(disciplineName('fr', 'Underwater Chess')).toBe('Underwater Chess');
	});
});
```

`front/src/lib/i18n/parity.test.js`:

```js
import { describe, expect, it } from 'vitest';
import fr from './fr.js';
import en from './en.js';

describe('dictionaries', () => {
	it('have the same keys', () => {
		expect(Object.keys(en).sort()).toEqual(Object.keys(fr).sort());
	});

	it('give every plural message a one and an other form in both languages', () => {
		for (const [key, message] of Object.entries(fr)) {
			if (typeof message === 'string') continue;
			expect(message, key).toEqual({ one: expect.any(String), other: expect.any(String) });
			expect(en[key], key).toEqual({ one: expect.any(String), other: expect.any(String) });
		}
	});

	it('use the same placeholders in both languages', () => {
		const names = (message) =>
			[...(typeof message === 'string' ? message : message.other).matchAll(/\{(\w+)\}/g)]
				.map((m) => m[1])
				.sort();
		for (const key of Object.keys(fr)) {
			expect(names(en[key]), key).toEqual(names(fr[key]));
		}
	});
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `docker compose exec -T front npx vitest run src/lib/i18n`
Expected: FAIL, "Failed to resolve import ./locale.js" (and the same for the other modules).

- [ ] **Step 3: Write the modules**

`front/src/lib/i18n/locale.js`:

```js
/** The two languages the site speaks. French is the default and the reference file. */
export const LOCALES = ['fr', 'en'];
export const DEFAULT_LOCALE = 'fr';

/** A known locale, or the default for anything else (a missing or foreign cookie). */
export const localeFrom = (value) => (LOCALES.includes(value) ? value : DEFAULT_LOCALE);
```

`front/src/lib/i18n/fr.js` (the reference file; keep keys sorted by area as below):

```js
/**
 * French messages, the reference dictionary: every key the site uses lives here,
 * and en.js mirrors it key for key (parity.test.js checks). Placeholders are {name};
 * a counting message is { one, other } picked with Intl.PluralRules.
 */
export default {
	'nav.ranking': 'Classement',
	'nav.teams': 'Équipes',
	'nav.disciplines': 'Épreuves',
	'nav.photos': 'Photos',
	'nav.sections': 'Rubriques',
	'header.edition': 'Édition',
	'header.language': 'Langue',
	'hub.days': 'Jours',
	'hub.hours': 'Heures',
	'hub.minutes': 'Minutes',
	'hub.seconds': 'Secondes',
	'hub.ranking': 'Classement',
	'hub.editions': 'Éditions',
	'ranking.title': 'Classement',
	'disciplines.title': 'Épreuves',
	'discipline.rounds': { one: '{n} tour', other: '{n} tours' },
	'discipline.games': { one: '{n} match', other: '{n} matchs' },
	'discipline.toPlay': { one: '{n} à jouer', other: '{n} à jouer' },
	'discipline.points': 'points',
	'discipline.time': 'temps',
	'discipline.results': 'Résultats',
	'discipline.schedule': 'Programme',
	'discipline.round': 'Tour {n}',
	'discipline.roundShort': 'T{n}',
	'discipline.notRevealed': 'Résultats non dévoilés',
	'game.played': 'joué',
	'game.referee': 'arbitre : {name}',
	'teams.title': 'Équipes',
	'team.overall': 'au général',
	'team.pts': 'pts',
	'team.results': 'Résultats',
	'team.games': 'Matchs',
	'team.notRevealed': 'non dévoilé',
	'team.unknown': 'Inconnue',
	'breadcrumb.label': "Fil d'Ariane",
	'error.back': 'Retour aux Olympic Warriors',
	'error.notFound': 'Page introuvable',
	'error.generic': 'Une erreur est survenue',
	'login.title': 'Connexion',
	'login.username': 'Identifiant',
	'login.password': 'Mot de passe',
	'login.missing': 'Champ obligatoire'
};
```

`front/src/lib/i18n/en.js`:

```js
/** English messages. Same keys as fr.js, which is the reference. */
export default {
	'nav.ranking': 'Ranking',
	'nav.teams': 'Teams',
	'nav.disciplines': 'Disciplines',
	'nav.photos': 'Photos',
	'nav.sections': 'Sections',
	'header.edition': 'Edition',
	'header.language': 'Language',
	'hub.days': 'Days',
	'hub.hours': 'Hours',
	'hub.minutes': 'Minutes',
	'hub.seconds': 'Seconds',
	'hub.ranking': 'Ranking',
	'hub.editions': 'Editions',
	'ranking.title': 'Ranking',
	'disciplines.title': 'Disciplines',
	'discipline.rounds': { one: '{n} round', other: '{n} rounds' },
	'discipline.games': { one: '{n} game', other: '{n} games' },
	'discipline.toPlay': { one: '{n} to play', other: '{n} to play' },
	'discipline.points': 'points',
	'discipline.time': 'time',
	'discipline.results': 'Results',
	'discipline.schedule': 'Schedule',
	'discipline.round': 'Round {n}',
	'discipline.roundShort': 'R{n}',
	'discipline.notRevealed': 'Results not revealed yet',
	'game.played': 'played',
	'game.referee': 'ref: {name}',
	'teams.title': 'Teams',
	'team.overall': 'overall',
	'team.pts': 'pts',
	'team.results': 'Results',
	'team.games': 'Games',
	'team.notRevealed': 'not revealed',
	'team.unknown': 'Unknown',
	'breadcrumb.label': 'Breadcrumb',
	'error.back': 'Back to the Olympic Warriors',
	'error.notFound': 'Page not found',
	'error.generic': 'Something went wrong',
	'login.title': 'Log In',
	'login.username': 'Username',
	'login.password': 'Password',
	'login.missing': 'Required'
};
```

`front/src/lib/i18n/disciplines.js`:

```js
/**
 * French name of a discipline by its database name (the `self.name` each model sets).
 * A discipline absent from here keeps its database name in French too (Rugby,
 * Basketball, Crossfit, Blindtest). icons.test.js checks every model is covered.
 */
export const FRENCH_NAMES = {
	Relay: 'Relais',
	Orienteering: "Course d'orientation",
	'Hide and Seek': 'Cache-cache',
	Fair: 'Fête foraine',
	Dodgeball: 'Balle au prisonnier',
	'Obstacle Course': "Parcours d'obstacles",
	'Geography Quizz': 'Quiz de géographie',
	'General Culture Quizz': 'Quiz de culture générale',
	Petanque: 'Pétanque',
	Darts: 'Fléchettes'
};

/** Disciplines whose database name is already the French one. */
export const SAME_IN_FRENCH = ['Rugby', 'Basketball', 'Crossfit', 'Blindtest'];
```

`front/src/lib/i18n/index.js`:

```js
import { getContext } from 'svelte';
import fr from './fr.js';
import en from './en.js';
import { FRENCH_NAMES } from './disciplines.js';
import { DEFAULT_LOCALE } from './locale.js';

/** Svelte context key under which the root layout stores the locale. */
export const I18N = 'i18n';

const MESSAGES = { fr, en };

const fill = (text, params) =>
	text.replace(/\{(\w+)\}/g, (match, name) => (name in params ? String(params[name]) : match));

/**
 * The message `key` in `locale`, placeholders filled from `params`. Falls back to the
 * French message, then to the key itself so a typo shows on the page. A counting
 * message ({ one, other }) is picked with the locale's plural rules on `params.n`.
 */
export function t(locale, key, params = {}) {
	const message = MESSAGES[locale]?.[key] ?? fr[key];
	if (message === undefined) return key;
	if (typeof message === 'string') return fill(message, params);
	const form = new Intl.PluralRules(locale in MESSAGES ? locale : DEFAULT_LOCALE).select(
		Number(params.n ?? 0)
	);
	return fill(message[form] ?? message.other, params);
}

/** `t` with the locale bound. */
export const translator = (locale) => (key, params) => t(locale, key, params);

/** The locale the root layout put in context; French outside any layout (tests). */
export const useLocale = () => getContext(I18N) ?? DEFAULT_LOCALE;

/** For a component's script: `const t = useT();` then `{t('nav.ranking')}`. */
export const useT = () => translator(useLocale());

/** French name of a discipline when the locale is French and the map knows it. */
export function disciplineName(locale, name) {
	return locale === 'fr' ? (FRENCH_NAMES[name] ?? name) : name;
}
```

`front/src/lib/test-utils.js`:

```js
import { render } from '@testing-library/svelte';
import { I18N } from '$lib/i18n';

/**
 * Render a component with the locale in context, as the root layout does at runtime.
 * Existing tests assert English text, so `en` is the default here; French is opt-in.
 */
export const renderWith = (Component, props = {}, locale = 'en') =>
	render(Component, { props, context: new Map([[I18N, locale]]) });
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose exec -T front npx vitest run src/lib/i18n`
Expected: 3 files, all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add front/src/lib/i18n front/src/lib/test-utils.js
git commit -m "[FEAT] front: i18n dictionary, lookup and locale helpers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 2: Locale plumbing and the `/lang` action

**Files:**
- Modify: `front/src/routes/+layout.server.js`, `front/src/routes/+layout.svelte`
- Create: `front/src/hooks.server.js`
- Modify: `front/src/app.html:2`
- Create: `front/src/routes/lang/+page.server.js`, `front/src/routes/lang/page.server.test.js`

- [ ] **Step 1: Write the failing action test**

`front/src/routes/lang/page.server.test.js`:

```js
import { describe, expect, it, vi } from 'vitest';
import { actions, load } from './+page.server.js';

const post = (fields) => {
	const body = new FormData();
	for (const [name, value] of Object.entries(fields)) body.append(name, value);
	return new Request('http://localhost/lang', { method: 'POST', body });
};

const call = (fields) => {
	const cookies = { set: vi.fn() };
	return { cookies, promise: actions.default({ cookies, request: post(fields) }) };
};

describe('lang action', () => {
	it('sets the cookie for a year and goes back where the form was', async () => {
		const { cookies, promise } = call({ lang: 'en', redirectTo: '/2026/ranking' });

		await expect(promise).rejects.toMatchObject({ status: 303, location: '/2026/ranking' });
		expect(cookies.set).toHaveBeenCalledWith('lang', 'en', {
			path: '/',
			maxAge: 60 * 60 * 24 * 365,
			sameSite: 'lax',
			httpOnly: false
		});
	});

	it('stores French for an unknown language', async () => {
		const { cookies, promise } = call({ lang: 'de', redirectTo: '/' });

		await expect(promise).rejects.toMatchObject({ status: 303, location: '/' });
		expect(cookies.set.mock.calls[0][1]).toBe('fr');
	});

	it('refuses a non-local redirect', async () => {
		await expect(call({ lang: 'en', redirectTo: '//evil.example' }).promise).rejects.toMatchObject({
			location: '/'
		});
		await expect(call({ lang: 'en', redirectTo: 'https://evil.example/' }).promise).rejects.toMatchObject({
			location: '/'
		});
		await expect(call({ lang: 'en' }).promise).rejects.toMatchObject({ location: '/' });
	});
});

describe('lang load', () => {
	it('sends a GET to the hub', () => {
		let thrown = null;
		try {
			load();
		} catch (e) {
			thrown = e;
		}
		expect(thrown).toMatchObject({ status: 303, location: '/' });
	});
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec -T front npx vitest run src/routes/lang`
Expected: FAIL, "Failed to resolve import ./+page.server.js".

- [ ] **Step 3: Write the action**

`front/src/routes/lang/+page.server.js`:

```js
import { redirect } from '@sveltejs/kit';
import { localeFrom } from '$lib/i18n/locale.js';

/** Only a path on this site: one leading slash, so `//host` and absolute URLs go home. */
const localPath = (value) => (typeof value === 'string' && /^\/(?!\/)/.test(value) ? value : '/');

/** Nothing to show here: a GET goes to the hub. */
export const load = () => {
	redirect(303, '/');
};

export const actions = {
	/** The header's FR | EN form: store the choice for a year, come back to the same page. */
	default: async ({ cookies, request }) => {
		const form = await request.formData();
		cookies.set('lang', localeFrom(form.get('lang')), {
			path: '/',
			maxAge: 60 * 60 * 24 * 365,
			sameSite: 'lax',
			httpOnly: false
		});
		redirect(303, localPath(form.get('redirectTo')));
	}
};
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose exec -T front npx vitest run src/routes/lang`
Expected: PASS (4 tests).

- [ ] **Step 5: Read the cookie in the root layout and put the locale in context**

`front/src/routes/+layout.server.js` becomes:

```js
import { apiGet } from '$lib/api';
import { api } from '$lib/server/urls';
import { localeFrom } from '$lib/i18n/locale.js';

/**
 * Every active edition, newest first, plus the year the bare URLs default to, and
 * the visitor's language from the `lang` cookie (French unless they switched).
 * Only the fields the nav and hub need, so nothing else rides along in the hydration data.
 */
export const load = async ({ fetch, cookies }) => {
	const editions = (await apiGet(fetch, api('/editions/')))
		.map(({ id, year, host, photos_url }) => ({ id, year, host, photos_url }))
		.sort((a, b) => b.year - a.year);
	return { editions, latestYear: editions[0]?.year ?? null, locale: localeFrom(cookies.get('lang')) };
};
```

In `front/src/routes/+layout.svelte`, add to the `<script>` after the existing imports:

```js
	import { setContext } from 'svelte';
	import { I18N } from '$lib/i18n';

	export let data;

	// The language is decided on the server per request; switching it is a full
	// page load (plain form POST + redirect), so init-time context is enough.
	setContext(I18N, data.locale);
```

- [ ] **Step 6: `<html lang>` from the same cookie**

`front/src/app.html` line 2: `<html lang="en">` becomes `<html lang="%lang%">`.

Create `front/src/hooks.server.js`:

```js
import { localeFrom } from '$lib/i18n/locale.js';

/** `<html lang>` follows the `lang` cookie; the root layout reads the same cookie for the pages. */
export const handle = async ({ event, resolve }) => {
	const locale = localeFrom(event.cookies.get('lang'));
	return resolve(event, { transformPageChunk: ({ html }) => html.replace('%lang%', locale) });
};
```

- [ ] **Step 7: Verify the whole suite and the build, then in the browser**

Run: `docker compose exec -T front npm test`
Expected: everything green (no component reads the context yet).

Run: `docker compose exec -T front npm run build`
Expected: `✓ built`.

Browser: `curl -s http://localhost:5173/ | grep -o '<html lang="[a-z]*"'` prints `<html lang="fr">`. Then
`curl -s -i -X POST -d 'lang=en&redirectTo=/2026/ranking' http://localhost:5173/lang | grep -i -E "^(HTTP|location|set-cookie)"` prints a 303, `location: /2026/ranking` and a `set-cookie` line containing `lang=en`, `Path=/`, `Max-Age=31536000` and `SameSite=Lax` (attribute order may differ). And `curl -s -b lang=en http://localhost:5173/ | grep -o '<html lang="[a-z]*"'` prints `en`.

- [ ] **Step 8: Commit**

```bash
git add front/src/routes/+layout.server.js front/src/routes/+layout.svelte front/src/hooks.server.js front/src/app.html front/src/routes/lang
git commit -m "[FEAT] front: locale from the lang cookie into context, /lang switch action

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 3: Header switch and translated tabs

**Files:**
- Modify: `front/src/lib/components/Header.svelte`
- Create: `front/src/lib/components/Header.test.js`
- Modify: `front/src/lib/components/TabBar.svelte`, `front/src/lib/components/TabBar.test.js`

- [ ] **Step 1: Write the failing Header test**

`front/src/lib/components/Header.test.js`:

```js
import { screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Header from './Header.svelte';

vi.mock('$app/stores', async () => {
	const { readable } = await import('svelte/store');
	return {
		page: readable({
			data: {
				editions: [{ id: 1, year: 2026, host: 'Paris', photos_url: 'https://photos.example' }],
				latestYear: 2026
			},
			params: { year: '2026' },
			url: new URL('http://localhost/2026/ranking'),
			error: null
		})
	};
});
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

describe('Header', () => {
	it('shows the language switch with the current language marked', () => {
		renderWith(Header, {}, 'en');

		const form = screen.getByRole('form', { name: 'Language' });
		expect(form).toHaveAttribute('action', '/lang');
		expect(form.querySelector('input[name="redirectTo"]')).toHaveValue('/2026/ranking');
		expect(screen.getByRole('button', { name: 'EN' })).toHaveAttribute('aria-current', 'true');
		expect(screen.getByRole('button', { name: 'FR' })).not.toHaveAttribute('aria-current');
		expect(screen.getByRole('button', { name: 'FR' })).toHaveValue('fr');
	});

	it('marks French and translates the tabs under fr', () => {
		renderWith(Header, {}, 'fr');

		expect(screen.getByRole('button', { name: 'FR' })).toHaveAttribute('aria-current', 'true');
		expect(screen.getByRole('link', { name: 'Classement' })).toHaveAttribute('aria-current', 'page');
		expect(screen.getByRole('link', { name: 'Équipes' })).toHaveAttribute('href', '/2026/teams');
		expect(screen.getByRole('link', { name: 'Épreuves' })).toHaveAttribute('href', '/2026/disciplines');
		expect(screen.getByRole('link', { name: 'Photos' })).toHaveAttribute('href', 'https://photos.example');
		expect(screen.getByRole('combobox', { name: 'Édition' })).toHaveValue('2026');
		expect(screen.getByRole('navigation', { name: 'Rubriques' })).toBeInTheDocument();
	});

	it('keeps English tabs under en', () => {
		renderWith(Header, {}, 'en');

		expect(screen.getByRole('link', { name: 'Ranking' })).toHaveAttribute('aria-current', 'page');
		expect(screen.getByRole('combobox', { name: 'Edition' })).toBeInTheDocument();
	});
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec -T front npx vitest run src/lib/components/Header`
Expected: FAIL, "Unable to find an accessible element with the role "form" and name "Language"".

- [ ] **Step 3: Rewrite the Header script and markup**

Replace the `<script>` and the markup of `front/src/lib/components/Header.svelte` (keep the `<style>` block, edited in step 4) with:

```svelte
<script>
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import logo from '$lib/img/logo.svg';
	import { switchYearPath } from '$lib/edition';
	import { useLocale, useT } from '$lib/i18n';

	const locale = useLocale();
	const t = useT();

	$: editions = $page.data.editions ?? [];
	// On an error page the year in the URL may be one with no edition, so fall back to the latest.
	$: year = Number(($page.error ? null : $page.params.year) ?? $page.data.latestYear);
	$: edition = editions.find((e) => e.year === year);
	$: tabs = year
		? [
				{ name: t('nav.ranking'), url: `/${year}/ranking` },
				{ name: t('nav.teams'), url: `/${year}/teams` },
				{ name: t('nav.disciplines'), url: `/${year}/disciplines` },
				...(edition?.photos_url
					? [{ name: t('nav.photos'), url: edition.photos_url, external: true }]
					: [])
			]
		: [];

	const switchYear = (event) => goto(switchYearPath($page.url.pathname, event.target.value));
</script>

<header>
	<div class="logo">
		<a href="/">
			<img src={logo} alt="OW" />
		</a>
		{#if editions.length > 0}
			<select aria-label={t('header.edition')} value={year} on:change={switchYear}>
				{#each editions as e}
					<!-- Svelte 4 SSR ignores `value` on the select, so mark the option itself. -->
					<option value={e.year} selected={e.year === year}>{e.year}</option>
				{/each}
			</select>
		{/if}
		<!-- A plain POST (no use:enhance): the redirect reloads the page in the new language. -->
		<form method="POST" action="/lang" class="lang" aria-label={t('header.language')}>
			<input type="hidden" name="redirectTo" value={$page.url.pathname} />
			<button name="lang" value="fr" aria-current={locale === 'fr' ? 'true' : undefined}>FR</button>
			<button name="lang" value="en" aria-current={locale === 'en' ? 'true' : undefined}>EN</button>
		</form>
	</div>

	<nav aria-label={t('nav.sections')}>
		<ul>
			{#if year}
				{#each tabs as tab}
					<li>
						{#if tab.external}
							<a href={tab.url} target="_blank" rel="noopener">{tab.name}</a>
						{:else}
							<a
								href={tab.url}
								aria-current={$page.url.pathname.startsWith(tab.url) ? 'page' : undefined}
							>
								{tab.name}
							</a>
						{/if}
					</li>
				{/each}
			{/if}
		</ul>
	</nav>
</header>
```

- [ ] **Step 4: Style the switch**

In the `<style>` of `Header.svelte`, after the `select option` rule, add:

```css
	.lang {
		display: flex;
		margin: 0;
		border: 1px solid var(--accent);
		border-radius: var(--radius-pill);
		overflow: hidden;
	}

	.lang button {
		background: transparent;
		border: 0;
		color: var(--muted);
		/* Same touch height as the year select beside it. */
		min-height: 44px;
		padding: 0 0.9em;
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.08em;
		cursor: pointer;
	}

	.lang button[aria-current='true'] {
		color: var(--accent);
		background: var(--bg-raised);
		cursor: default;
	}

	.lang button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -3px;
	}
```

- [ ] **Step 5: Run the Header test to verify it passes**

Run: `docker compose exec -T front npx vitest run src/lib/components/Header`
Expected: PASS (3 tests).

- [ ] **Step 6: Translate the TabBar and switch its test to `renderWith`**

In `front/src/lib/components/TabBar.svelte`, add to the script after the props: `import { useT } from '$lib/i18n';` at the top and `const t = useT();` after the last `export let`; then replace the four literal names with `t('nav.ranking')`, `t('nav.teams')`, `t('nav.disciplines')`, `t('nav.photos')`, and `aria-label="Sections"` with `aria-label={t('nav.sections')}`.

In `front/src/lib/components/TabBar.test.js`: add `import { renderWith } from '$lib/test-utils';` alongside the existing `import { render, screen } from '@testing-library/svelte';` (keep `render` imported — see below), and every existing `render(TabBar, X)` with `renderWith(TabBar, X)` (7 places; the default locale of the helper is `en`, so the assertions stay). Append two tests inside the describe:

```js
	it('speaks French under fr', () => {
		renderWith(TabBar, { year: 2026, pathname: '/2026/teams/1' }, 'fr');

		expect(screen.getByRole('navigation', { name: 'Rubriques' })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Équipes' })).toHaveAttribute('aria-current', 'page');
	});

	it('speaks French without any locale in context', () => {
		render(TabBar, { year: 2026, pathname: '/2026/ranking' });

		expect(screen.getByRole('link', { name: 'Classement' })).toBeInTheDocument();
	});
```

`render` from `@testing-library/svelte` therefore stays imported in that file: the last test calls it directly (with no `i18n` context) to check the component falls back to French, while every other test uses `renderWith` to opt into English.

- [ ] **Step 7: Run the suite and check the header in the browser**

Run: `docker compose exec -T front npm test`
Expected: green.

Browser (`http://localhost:5173/2026/ranking`): the top bar shows the logo, the year select, then `FR | EN` with FR marked; tabs read `CLASSEMENT ÉQUIPES ÉPREUVES`. Clicking `EN` reloads the page in English with EN marked; the cookie survives a navigation to `/2026/teams`. At 375 px the switch stays in the top bar next to the year select and nothing overflows horizontally.

- [ ] **Step 8: Commit**

```bash
git add front/src/lib/components/Header.svelte front/src/lib/components/Header.test.js front/src/lib/components/TabBar.svelte front/src/lib/components/TabBar.test.js
git commit -m "[FEAT] header: FR | EN switch, tabs and tab bar through the dictionary

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 4: Locale-free helpers, MedalRank, hub, disciplines grid and discipline page

**Files:**
- Modify: `front/src/lib/edition.js` (`nameOf`, `disciplineResults`, `formatDateRange`, `ordinal`, `plural`, `disciplineSubtitle`, `roundCount`), `front/src/lib/edition.test.js`
- Modify: `front/src/lib/components/MedalRank.svelte`, `MedalRank.test.js`
- Modify: `front/src/lib/components/EditionHub.svelte`, `EditionHub.test.js`
- Modify: `front/src/routes/[year=year]/disciplines/+page.svelte`, `page.test.js`
- Modify: `front/src/routes/[year=year]/disciplines/[id]/+page.svelte`, `page.test.js`

- [ ] **Step 1: Rewrite the helper tests**

In `front/src/lib/edition.test.js`:

Replace the whole `describe('formatDateRange', …)` block with:

```js
describe('formatDateRange', () => {
	it('prints one date for a single-day edition', () => {
		expect(formatDateRange('2026-09-19', '2026-09-19', 'en')).toBe('19 September 2026');
		expect(formatDateRange('2026-09-19', '2026-09-19', 'fr')).toBe('19 septembre 2026');
	});

	it('names the month once within a month', () => {
		expect(formatDateRange('2026-09-19', '2026-09-20', 'en')).toBe('19 – 20 September 2026');
		expect(formatDateRange('2026-09-19', '2026-09-20', 'fr')).toBe('19 – 20 septembre 2026');
	});

	it('names both months across a month boundary', () => {
		expect(formatDateRange('2026-09-30', '2026-10-01', 'en')).toBe('30 September – 1 October 2026');
		expect(formatDateRange('2026-09-30', '2026-10-01', 'fr')).toBe('30 septembre – 1er octobre 2026');
		expect(formatDateRange('2026-10-01', '2026-10-01', 'fr')).toBe('1er octobre 2026');
		expect(formatDateRange('2026-10-01', '2026-10-02', 'fr')).toBe('1er – 2 octobre 2026');
	});
});
```

Replace the whole `describe('ordinal', …)` block with:

```js
describe('ordinal', () => {
	it('suffixes the usual English ranks', () => {
		expect(ordinal(1, 'en')).toBe('1st');
		expect(ordinal(2, 'en')).toBe('2nd');
		expect(ordinal(3, 'en')).toBe('3rd');
		expect(ordinal(4, 'en')).toBe('4th');
	});

	it('keeps the English teens in th', () => {
		expect(ordinal(11, 'en')).toBe('11th');
		expect(ordinal(12, 'en')).toBe('12th');
		expect(ordinal(13, 'en')).toBe('13th');
	});

	it('suffixes above twenty and above a hundred in English', () => {
		expect(ordinal(21, 'en')).toBe('21st');
		expect(ordinal(22, 'en')).toBe('22nd');
		expect(ordinal(23, 'en')).toBe('23rd');
		expect(ordinal(101, 'en')).toBe('101st');
		expect(ordinal(111, 'en')).toBe('111th');
	});

	it('writes French ranks for a team: 1re then Ne', () => {
		expect(ordinal(1, 'fr')).toBe('1re');
		expect(ordinal(2, 'fr')).toBe('2e');
		expect(ordinal(3, 'fr')).toBe('3e');
		expect(ordinal(11, 'fr')).toBe('11e');
		expect(ordinal(21, 'fr')).toBe('21e');
	});
});
```

Replace the whole `describe('disciplineSubtitle', …)` block with:

```js
describe('disciplineSubtitle', () => {
	it('counts the rounds and the games of the discipline', () => {
		expect(disciplineSubtitle(summary, summary.disciplines[0])).toEqual({ rounds: 2, games: 3 });
		expect(disciplineSubtitle(summary, summary.disciplines[1])).toEqual({ rounds: 1, games: 1 });
	});

	it('counts the games even when the discipline has none yet', () => {
		const noGames = { ...summary, games: summary.games.filter((g) => g.discipline !== 10) };
		expect(disciplineSubtitle(noGames, summary.disciplines[0])).toEqual({ rounds: 2, games: 0 });
	});

	it('gives the result type when the discipline has no round', () => {
		const noRounds = { ...summary, rounds: [], games: [] };
		expect(disciplineSubtitle(noRounds, { id: 10, result_type: 'PTS' })).toEqual({ resultType: 'PTS' });
		expect(disciplineSubtitle(noRounds, { id: 10, result_type: 'TIM' })).toEqual({ resultType: 'TIM' });
		expect(disciplineSubtitle(noRounds, { id: 10, result_type: 'NON' })).toEqual({ resultType: 'NON' });
	});

	it('ignores reveal_score', () => {
		const hidden = { ...summary.disciplines[0], reveal_score: false };
		expect(disciplineSubtitle(summary, hidden)).toEqual({ rounds: 2, games: 3 });
	});
});
```

Replace the whole `describe('roundCount', …)` block with:

```js
describe('roundCount', () => {
	const round = (...played) => ({ games: played.map((isPlayed) => ({ isPlayed })) });

	it('counts the games and what is left to play', () => {
		expect(roundCount(round(true, true, true))).toEqual({ left: 0, total: 3 });
		expect(roundCount(round(true))).toEqual({ left: 0, total: 1 });
		expect(roundCount(round(true, false, false))).toEqual({ left: 2, total: 3 });
	});
});
```

In `describe('disciplineSchedule', …)`, the test `names an unknown team Unknown` becomes:

```js
	it('gives a null name to an unknown or missing referee', () => {
		const odd = { ...summary, games: [{ ...summary.games[0], referees: 42 }] };
		expect(disciplineSchedule(odd, 10)[0].games[0].refereeName).toBeNull();
		const none = { ...summary, games: [{ ...summary.games[0], referees: null }] };
		expect(disciplineSchedule(none, 10)[0].games[0].refereeName).toBeNull();
	});
```

(`GameRow` then omits its referee line for a null name, instead of printing `ref: Unknown`.) That is the only `Unknown` assertion in the file (`grep -n Unknown front/src/lib/edition.test.js`). The `teamGames` block is untouched here: `teamGames` still builds `opponentName` from `nameOf`, whose null now only matters for an unknown id, which its tests do not exercise. Task 6 rewrites it.

- [ ] **Step 2: Run the helper tests to verify the rewritten ones fail**

Run: `docker compose exec -T front npx vitest run src/lib/edition.test.js`
Expected: FAIL on formatDateRange (fr), ordinal (fr and the shape), disciplineSubtitle, roundCount, unknown team.

- [ ] **Step 3: Change the helpers**

In `front/src/lib/edition.js`:

Replace `.map((r) => ({ ...r, teamName: names.get(r.team) ?? 'Unknown' }))` in `disciplineResults` with `.map((r) => ({ ...r, teamName: names.get(r.team) ?? null }))` and its sort with `.sort((a, b) => rank(a) - rank(b) || (a.teamName ?? '').localeCompare(b.teamName ?? ''))`.

Replace `const nameOf = (names, id) => names.get(id) ?? 'Unknown';` with:

```js
/** A team's name, or null when the id matches no team: the page prints the "unknown" label. */
const nameOf = (names, id) => names.get(id) ?? null;
```

Replace the `dayMonth` function and `formatDateRange` with:

```js
/** BCP 47 tag behind each site locale, for Intl. */
const DATE_TAGS = { fr: 'fr-FR', en: 'en-GB' };

/** French writes the first of the month "1er"; Intl gives "1". */
function frenchFirst(text, date, locale) {
	return locale === 'fr' && date.getDate() === 1 ? text.replace(/^1\b/, '1er') : text;
}

function dayMonth(date, locale) {
	const text = date.toLocaleDateString(DATE_TAGS[locale], { day: 'numeric', month: 'long' });
	return frenchFirst(text, date, locale);
}

/**
 * The dates of an edition as one line in `locale`: "19 September 2026" for a single day,
 * "19 – 20 September 2026" within a month, "30 September – 1 October 2026" across two.
 */
export function formatDateRange(start, end, locale) {
	const to = parseDay(end);
	const year = to.getFullYear();
	if (start === end) return `${dayMonth(to, locale)} ${year}`;

	const from = parseDay(start);
	const sameMonth = from.getFullYear() === year && from.getMonth() === to.getMonth();
	const left = sameMonth
		? frenchFirst(from.toLocaleDateString(DATE_TAGS[locale], { day: 'numeric' }), from, locale)
		: dayMonth(from, locale);
	return `${left} – ${dayMonth(to, locale)} ${year}`;
}
```

Replace `ordinal` with:

```js
/**
 * Ordinal of a rank: 1st, 2nd, 3rd, 4th, 11th, 21st in English; 1re then 2e, 3e in French
 * (the rank always describes a team, feminine).
 */
export function ordinal(n, locale) {
	if (locale === 'fr') return n === 1 ? '1re' : `${n}e`;
	const mod100 = n % 100;
	if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
	const mod10 = n % 10;
	if (mod10 === 1) return `${n}st`;
	if (mod10 === 2) return `${n}nd`;
	if (mod10 === 3) return `${n}rd`;
	return `${n}th`;
}
```

Delete `const plural = …` and `const RESULT_TYPE_LABELS = …`. Replace `disciplineSubtitle` and `roundCount` with:

```js
/**
 * What goes under a discipline name: its round and game counts, or the kind of result
 * it produces when it has no round. `reveal_score` plays no part. The page words it.
 */
export function disciplineSubtitle(summary, discipline) {
	const rounds = summary.rounds.filter((r) => r.discipline === discipline.id).length;
	if (rounds === 0) return { resultType: discipline.result_type };

	const games = summary.games.filter((g) => g.discipline === discipline.id).length;
	return { rounds, games };
}

/** Beside a round heading: how many games it holds and how many are still to play. */
export function roundCount(round) {
	const left = round.games.filter((g) => !g.isPlayed).length;
	return { left, total: round.games.length };
}
```

- [ ] **Step 4: Run the helper tests to verify they pass**

Run: `docker compose exec -T front npx vitest run src/lib/edition.test.js`
Expected: PASS.

- [ ] **Step 5: MedalRank reads the locale**

`front/src/lib/components/MedalRank.svelte` script becomes:

```svelte
<script>
	import { ordinal as toOrdinal } from '$lib/edition';
	import { useLocale } from '$lib/i18n';

	/**
	 * Rank of a team; null or 0 (the API's unrevealed value) renders as a dash.
	 * @type {number | null}
	 */
	export let rank = null;
	/** Render `2nd` (`2e` in French) instead of `2`. */
	export let ordinal = false;

	const locale = useLocale();
	const MEDALS = { 1: 'gold', 2: 'silver', 3: 'bronze' };

	$: unranked = rank === null || rank === 0;
	$: medal = MEDALS[rank] ?? 'none';
	$: text = unranked ? '—' : ordinal ? toOrdinal(rank, locale) : `${rank}`;
</script>
```

In `front/src/lib/components/MedalRank.test.js`: replace the `render` import with `import { screen } from '@testing-library/svelte';` plus `import { renderWith } from '$lib/test-utils';` (`screen` is used once in the file), replace every `render(MedalRank, X)` with `renderWith(MedalRank, X)` (10 places), and add:

```js
	it('writes the French ordinal under fr', () => {
		expect(renderWith(MedalRank, { rank: 1, ordinal: true }, 'fr').container.querySelector('.gold')).toHaveTextContent('1re');
		expect(renderWith(MedalRank, { rank: 4, ordinal: true }, 'fr').container.querySelector('.none')).toHaveTextContent('4e');
	});
```

Also in `front/src/routes/[year=year]/teams/[id]/page.test.js` (rewritten fully in Task 6, but its `2nd` assertions would turn into `2e` now): replace the import line with `import { screen } from '@testing-library/svelte';` plus `import { renderWith } from '$lib/test-utils';` and every `render(Page, X)` with `renderWith(Page, X)` (5 places).

Run: `docker compose exec -T front npx vitest run src/lib/components/MedalRank "src/routes/\[year=year\]/teams/\[id\]"`
Expected: PASS.

- [ ] **Step 6: EditionHub (it is the only caller of `formatDateRange`, whose signature just changed)**

In `front/src/lib/components/EditionHub.svelte` script add `import { disciplineName, useLocale, useT } from '$lib/i18n';`, `const locale = useLocale();`, `const t = useT();`. In the markup: `alt={discipline.name}` becomes `alt={disciplineName(locale, discipline.name)}`; the `.where` line becomes `{edition.host} · {formatDateRange(edition.start_date, edition.end_date, locale)}`; the four countdown words become `{t('hub.days')}`, `{t('hub.hours')}`, `{t('hub.minutes')}`, `{t('hub.seconds')}`; the button text becomes `{t('hub.ranking')}`; `aria-label="Editions"` becomes `aria-label={t('hub.editions')}`.

In `EditionHub.test.js`: the first line becomes `import { screen, within } from '@testing-library/svelte';` plus `import { renderWith } from '$lib/test-utils';`, every `render(EditionHub, …)` becomes `renderWith(EditionHub, …)` (6 places), and add:

```js
	it('speaks French under fr', () => {
		vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
		renderWith(EditionHub, { summary, editions }, 'fr');

		expect(screen.getByText('Paris · 19 – 20 septembre 2026')).toBeInTheDocument();
		expect(screen.getByText('Jours').querySelector('span')).toHaveTextContent(/^2$/);
		expect(screen.getByAltText('Relais')).toBeInTheDocument();
		expect(screen.getByRole('navigation', { name: 'Éditions' })).toBeInTheDocument();
	});
```

- [ ] **Step 7: Disciplines grid**

`front/src/routes/[year=year]/disciplines/+page.svelte` script and markup become (keep the style):

```svelte
<script>
	import { iconFor } from '$lib/icons';
	import { disciplineSubtitle } from '$lib/edition';
	import { disciplineName, useLocale, useT } from '$lib/i18n';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: year = data.summary.edition.year;
	$: disciplines = data.summary.disciplines;

	/** "2 rounds · 3 games", or "points" / "time" / nothing for a discipline without rounds. */
	const subtitle = (sub) => {
		if ('rounds' in sub) {
			return `${t('discipline.rounds', { n: sub.rounds })} · ${t('discipline.games', { n: sub.games })}`;
		}
		if (sub.resultType === 'PTS') return t('discipline.points');
		if (sub.resultType === 'TIM') return t('discipline.time');
		return '';
	};
</script>

<div class="page">
	<Breadcrumb items={[{ label: String(year), href: `/${year}` }, { label: t('nav.disciplines') }]} />
	<h1>{t('disciplines.title')}</h1>

	<div class="grid">
		{#each disciplines as discipline}
			{@const name = disciplineName(locale, discipline.name)}
			<!-- The whole card is the link, so its name is pinned to the bare discipline name.
			     An unrevealed discipline stays reachable: its page still shows the pairings. -->
			<a
				class="card"
				class:unrevealed={!discipline.reveal_score}
				href="/{year}/disciplines/{discipline.id}"
				aria-label={name}
			>
				<span class="icon">
					<img src={iconFor(discipline.name)} alt="" />
				</span>
				<span class="text">
					<span class="name">{name}</span>
					<span class="label subtitle">{subtitle(disciplineSubtitle(data.summary, discipline))}</span>
				</span>
			</a>
		{/each}
	</div>
</div>
```

In `front/src/routes/[year=year]/disciplines/page.test.js`: switch the import to `import { screen } from '@testing-library/svelte';` + `import { renderWith } from '$lib/test-utils';`, replace the three `render(Page, { data: { summary } })` with `renderWith(Page, { data: { summary } })`, and add:

```js
	it('names and subtitles the cards in French under fr', () => {
		renderWith(Page, { data: { summary } }, 'fr');

		expect(screen.getByRole('heading', { name: 'Épreuves' })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Relais' })).toHaveTextContent('2 tours · 3 matchs');
		expect(screen.getByRole('link', { name: "Course d'orientation" })).toHaveTextContent('1 tour · 1 match');
	});
```

- [ ] **Step 8: Discipline page**

`front/src/routes/[year=year]/disciplines/[id]/+page.svelte` script and markup become (keep the style):

```svelte
<script>
	import { formatDifference, roundCount } from '$lib/edition';
	import { iconFor } from '$lib/icons';
	import { disciplineName, useLocale, useT } from '$lib/i18n';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import DisciplineRail from '$lib/components/DisciplineRail.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import GameRow from '$lib/components/GameRow.svelte';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: year = data.summary.edition.year;
	$: name = disciplineName(locale, data.discipline.name);
	$: rounds = (data.schedule ?? []).filter((round) => round.games.length > 0);
	// The difference is summed from game scores, so a discipline without rounds
	// has nothing but zeroes to show.
	$: showDifference = data.schedule !== null;
</script>

<div class="page">
	<Breadcrumb
		items={[
			{ label: String(year), href: `/${year}` },
			{ label: t('nav.disciplines'), href: `/${year}/disciplines` },
			{ label: name }
		]}
	/>

	<h1>
		<img src={iconFor(data.discipline.name)} alt="" />
		{name}
	</h1>

	<div class="rail">
		<DisciplineRail {year} disciplines={data.summary.disciplines} currentId={data.discipline.id} />
	</div>

	{#if data.results === null}
		<p class="not-revealed">{t('discipline.notRevealed')}</p>
	{:else}
		<div id="results">
			{#each data.results as result}
				{@const difference =
					showDifference && result.result_type === 'PTS' && result.points_difference !== null
						? formatDifference(result.points_difference)
						: null}
				<a
					class="result-row"
					class:no-diff={difference === null}
					class:gold={result.ranking === 1}
					class:silver={result.ranking === 2}
					class:bronze={result.ranking === 3}
					data-testid="result-row"
					href="/{year}/teams/{result.team}"
				>
					<MedalRank rank={result.ranking} />
					<span class="name">{result.teamName ?? t('team.unknown')}</span>
					{#if difference !== null}
						<span class="diff">{difference}</span>
					{/if}
					<span class="num value">
						{#if result.ranking === null}
							—
						{:else if result.result_type === 'TIM'}
							{result.time}
						{:else}
							{result.points} {t('team.pts')}
						{/if}
					</span>
				</a>
			{/each}
		</div>
	{/if}

	{#if rounds.length > 0}
		<section class="schedule">
			<h2>{t('discipline.schedule')}</h2>
			{#each rounds as round}
				{@const count = roundCount(round)}
				<div class="round-header">
					<h3>{t('discipline.round', { n: round.order + 1 })}</h3>
					<span class="label" class:todo={count.left > 0}>
						{count.left > 0
							? t('discipline.toPlay', { n: count.left })
							: t('discipline.games', { n: count.total })}
					</span>
				</div>
				{#each round.games as game}
					<GameRow
						team1Name={game.team1Name}
						team2Name={game.team2Name}
						team1Href="/{year}/teams/{game.team1Id}"
						team2Href="/{year}/teams/{game.team2Id}"
						score1={game.score1}
						score2={game.score2}
						isPlayed={game.isPlayed}
						refereeName={game.refereeName}
					/>
				{/each}
			{/each}
		</section>
	{/if}
</div>
```

`GameRow` still prints its own English (`played`, `ref:`) until Task 5; the English tests below keep passing because the helper defaults to `en`, and `GameRow` prints its literals regardless of locale for now.

In `front/src/routes/[year=year]/disciplines/[id]/page.test.js`: switch to `import { screen, within } from '@testing-library/svelte';` + `import { renderWith } from '$lib/test-utils';`, replace every `render(Page, …)` / `render(\n\t\t\tPage, …` with `renderWith(Page, …)` (10 places), and add inside the page describe:

```js
	it('speaks French under fr', () => {
		renderWith(Page, { data: dataFor(summary, 10) }, 'fr');

		expect(screen.getByRole('heading', { level: 1, name: 'Relais' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Programme' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Tour 1' }).parentElement).toHaveTextContent('1 à jouer');
		expect(screen.getByRole('heading', { name: 'Tour 2' }).parentElement).toHaveTextContent('1 match');
	});
```

(If the existing `h1` assertion uses `getByRole('heading', { name: 'Relay' })` with the icon inside, keep it as is; it renders under `en`.)

- [ ] **Step 9: Run the suite and the build**

Run: `docker compose exec -T front npm test`
Expected: green. If a page test asserts `'Unknown'` anywhere, that page must print `t('team.unknown')`; grep `Unknown` under `front/src` to check nothing else relied on the helper string.

Browser: `http://localhost:5173/2026/disciplines` in French shows `ÉPREUVES`, `Relais`, `2 tours · 3 matchs` (with the live data: the real counts); a discipline page shows `PROGRAMME`, `TOUR 1`.

- [ ] **Step 10: Commit**

```bash
git add front/src/lib/edition.js front/src/lib/edition.test.js front/src/lib/components/MedalRank.svelte front/src/lib/components/MedalRank.test.js front/src/lib/components/EditionHub.svelte front/src/lib/components/EditionHub.test.js "front/src/routes/[year=year]/disciplines" "front/src/routes/[year=year]/teams/[id]/page.test.js"
git commit -m "[FEAT] front: locale-free helpers, French ordinals and dates, hub and disciplines pages translated

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 5: Remaining components and pages

**Files:**
- Modify: `front/src/lib/components/Breadcrumb.svelte` (+ test), `DisciplineRail.svelte` (+ test), `GameRow.svelte` (+ test)
- Modify: `front/src/routes/[year=year]/ranking/+page.svelte` (+ test), `teams/+page.svelte` (+ test), `front/src/routes/+error.svelte`, `front/src/routes/login/login.svelte`

- [ ] **Step 1: Breadcrumb**

In `front/src/lib/components/Breadcrumb.svelte` script add `import { useT } from '$lib/i18n';` and `const t = useT();`; change `aria-label="Breadcrumb"` to `aria-label={t('breadcrumb.label')}`.

In `Breadcrumb.test.js`: switch to `renderWith` (4 places, `import { screen } from '@testing-library/svelte'` stays if used). If a test queries `getByRole('navigation', { name: 'Breadcrumb' })` it keeps passing under `en`. Add:

```js
	it('labels the landmark in French under fr', () => {
		renderWith(Breadcrumb, { items: [{ label: '2026', href: '/2026' }, { label: 'Classement' }] }, 'fr');
		expect(screen.getByRole('navigation', { name: "Fil d'Ariane" })).toBeInTheDocument();
	});
```

- [ ] **Step 2: DisciplineRail**

In `front/src/lib/components/DisciplineRail.svelte` script add `import { disciplineName, useLocale, useT } from '$lib/i18n';`, `const locale = useLocale();`, `const t = useT();`; change `<nav aria-label="Disciplines">` to `<nav aria-label={t('nav.disciplines')}>` and `aria-label={discipline.name}` to `aria-label={disciplineName(locale, discipline.name)}`.

In `DisciplineRail.test.js`: switch to `renderWith` (3 places) and add:

```js
	it('names the tiles in French under fr', () => {
		renderWith(DisciplineRail, { year: 2026, disciplines: summary.disciplines, currentId: null }, 'fr');

		expect(screen.getByRole('navigation', { name: 'Épreuves' })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Relais' })).toHaveAttribute('href', '/2026/disciplines/10');
	});
```

- [ ] **Step 3: GameRow words**

In `front/src/lib/components/GameRow.svelte` script add `import { useT } from '$lib/i18n';` and `const t = useT();` after the props. Replace `<span class="score pending">played</span>` with `<span class="score pending">{t('game.played')}</span>`, `<p class="referee">ref: {refereeName}</p>` with `<p class="referee">{t('game.referee', { name: refereeName })}</p>`, and both `{team1Name}` / `{team2Name}` text nodes (four places, in the `<a>` and `<span>` branches) with `{team1Name ?? t('team.unknown')}` / `{team2Name ?? t('team.unknown')}`.

In `GameRow.test.js`: switch to `renderWith` (9 places; `render(GameRow, played)` becomes `renderWith(GameRow, played)`) and add:

```js
	it('speaks French under fr', () => {
		renderWith(GameRow, { ...played, score1: null, score2: null }, 'fr');

		expect(screen.getByTestId('game-row')).toHaveTextContent(/Bisons\s*joué\s*Aigles/);
		expect(screen.getByTestId('game-row')).toHaveTextContent('arbitre : Cerfs');
	});

	it('names an unknown team', () => {
		renderWith(GameRow, { ...played, team2Name: null }, 'en');

		expect(screen.getByTestId('game-row')).toHaveTextContent(/Bisons\s*12 : 9\s*Unknown/);
	});
```

- [ ] **Step 4: Ranking page**

In `front/src/routes/[year=year]/ranking/+page.svelte` script add `import { useT } from '$lib/i18n';` and `const t = useT();`; the breadcrumb's last label becomes `t('nav.ranking')`, the `h1` becomes `{t('ranking.title')}`, and `{team.total_points} pts` becomes `{team.total_points} {t('team.pts')}`.

In `ranking/page.test.js`: switch to `renderWith` (3 places) and add:

```js
	it('speaks French under fr', () => {
		renderWith(Page, { data: { summary } }, 'fr');

		expect(screen.getByRole('heading', { name: 'Classement' })).toBeInTheDocument();
		expect(screen.getByRole('navigation', { name: 'Épreuves' })).toBeInTheDocument();
		expect(screen.getAllByTestId('team-row')[0]).toHaveTextContent(/1\s*Bisons\s*5 pts/);
	});
```

- [ ] **Step 5: Teams grid**

In `front/src/routes/[year=year]/teams/+page.svelte` script add `import { useT } from '$lib/i18n';` and `const t = useT();`; the breadcrumb's last label becomes `t('nav.teams')`, the `h1` `{t('teams.title')}`, and `{team.total_points} pts` becomes `{team.total_points} {t('team.pts')}`.

In `teams/page.test.js`: switch to `renderWith` (1 place) and add:

```js
	it('speaks French under fr', () => {
		renderWith(Page, { data: { summary } }, 'fr');
		expect(screen.getByRole('heading', { name: 'Équipes' })).toBeInTheDocument();
	});
```

- [ ] **Step 6: Error page and login form**

`front/src/routes/+error.svelte` script and markup become (keep the style):

```svelte
<script>
	import { page } from '$app/stores';
	import { useT } from '$lib/i18n';

	const t = useT();

	// The loaders throw their 404s with an English message; the page words it.
	$: message =
		$page.status === 404 ? t('error.notFound') : ($page.error?.message ?? t('error.generic'));
</script>

<section>
	<h1>{$page.status}</h1>
	<p>{message}</p>
	<a href="/">{t('error.back')}</a>
</section>
```

In `front/src/routes/login/login.svelte`: add `import { useT } from '$lib/i18n';` and `const t = useT();` to the script; replace `The username field is required` and `You forgot the password...` with `{t('login.missing')}`, `placeholder="Username"` with `placeholder={t('login.username')}`, `placeholder="Password"` with `placeholder={t('login.password')}`, and `<button>Log In</button>` with `<button>{t('login.title')}</button>`. Leave the rest of the file untouched (its formatting is legacy).

- [ ] **Step 7: Grep for leftovers, run the suite and build**

Run: `grep -rn -E ">(Ranking|Teams|Disciplines|Results|Schedule|Games|Days|Hours|Minutes|Seconds|Log In|played|overall|referee|to play)<|aria-label=\"[A-Z]" front/src/lib/components front/src/routes --include=*.svelte`
Expected: no output except hits in `TeamGameRow.svelte` and `teams/[id]/+page.svelte` (Task 6).

Run: `docker compose exec -T front npm test` → green. `docker compose exec -T front npm run build` → `✓ built`.

Browser: `http://localhost:5173/` shows `Paris · 19 – 20 septembre 2026`-style French date and `JOURS` or `CLASSEMENT`; `/2026/ranking` and `/2026/teams` in French; `/1999` shows `Page introuvable` and `RETOUR AUX OLYMPIC WARRIORS`; switch to EN and reload each.

- [ ] **Step 8: Commit**

```bash
git add front/src/lib/components/Breadcrumb.svelte front/src/lib/components/Breadcrumb.test.js front/src/lib/components/DisciplineRail.svelte front/src/lib/components/DisciplineRail.test.js front/src/lib/components/GameRow.svelte front/src/lib/components/GameRow.test.js "front/src/routes/[year=year]/ranking" "front/src/routes/[year=year]/teams/+page.svelte" "front/src/routes/[year=year]/teams/page.test.js" front/src/routes/+error.svelte front/src/routes/login/login.svelte
git commit -m "[FEAT] front: ranking, teams, rail, breadcrumb, game row, error and login through the dictionary

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 6: Team page games on `GameRow`

**Files:**
- Modify: `front/src/lib/edition.js` (`teamGames`, delete `gameResult`), `front/src/lib/edition.test.js`
- Modify: `front/src/lib/components/GameRow.svelte`, `GameRow.test.js`
- Modify: `front/src/routes/[year=year]/teams/[id]/+page.svelte`, `page.test.js`
- Delete: `front/src/lib/components/TeamGameRow.svelte`, `TeamGameRow.test.js`

- [ ] **Step 1: Rewrite the `teamGames` tests**

Replace the whole `describe('teamGames', …)` block in `front/src/lib/edition.test.js` with:

```js
describe('teamGames', () => {
	it('lists the games the team played per discipline, in round order, referee named', () => {
		const [relay, orienteering] = teamGames(summary, 1);
		expect(relay.disciplineName).toBe('Relay');
		expect(relay.games).toEqual([
			{ id: 200, round: 0, team1Id: 2, team2Id: 1, team1Name: 'Bisons', team2Name: 'Aigles', refereeName: 'Cerfs', isPlayed: true, score1: 12, score2: 9 },
			{ id: 202, round: 1, team1Id: 1, team2Id: 3, team1Name: 'Aigles', team2Name: 'Cerfs', refereeName: 'Bisons', isPlayed: true, score1: 7, score2: 7 }
		]);
		expect(orienteering.games).toEqual([
			{ id: 203, round: 0, team1Id: 1, team2Id: 2, team1Name: 'Aigles', team2Name: 'Bisons', refereeName: 'Cerfs', isPlayed: true, score1: null, score2: null }
		]);
	});

	it('leaves out the games the team only referees', () => {
		expect(teamGames(summary, 1).flatMap((d) => d.games.map((g) => g.id))).not.toContain(201);
		const [relay] = teamGames(summary, 3);
		expect(relay.games.map((g) => g.id)).toEqual([201, 202]);
	});

	it('omits disciplines where the team has no game', () => {
		// Cerfs only referee the Orienteering game, so that discipline is not listed for them.
		expect(teamGames(summary, 3).map((d) => d.disciplineName)).toEqual(['Relay']);
		const none = { ...summary, games: summary.games.filter((g) => g.discipline !== 11) };
		expect(teamGames(none, 1).map((d) => d.disciplineName)).toEqual(['Relay']);
	});

	it('returns an empty array for an unknown team', () => {
		expect(teamGames(summary, 999)).toEqual([]);
	});

	it('keeps a game whose referee is unknown, with a null name', () => {
		const odd = { ...summary, games: [{ ...summary.games[0], referees: 42 }] };
		expect(teamGames(odd, 2)[0].games[0].refereeName).toBeNull();
	});
});
```

Run: `docker compose exec -T front npx vitest run src/lib/edition.test.js`
Expected: the `teamGames` tests FAIL (old shape).

- [ ] **Step 2: Rewrite `teamGames`**

In `front/src/lib/edition.js`, delete the `gameResult` function and replace `teamGames` with:

```js
/**
 * The games a team played (as team1 or team2), grouped by discipline in id order and
 * sorted by round, with team and referee names joined. Games the team only referees
 * are left out. Disciplines without such a game are omitted.
 */
export function teamGames(summary, teamId) {
	const names = teamNames(summary);
	const roundOrder = new Map(summary.rounds.map((r) => [r.id, r.order]));
	return summary.disciplines
		.map((discipline) => ({
			disciplineId: discipline.id,
			disciplineName: discipline.name,
			games: summary.games
				.filter(
					(g) => g.discipline === discipline.id && (g.team1 === teamId || g.team2 === teamId)
				)
				.map((g) => ({
					id: g.id,
					round: roundOrder.get(g.round) ?? 0,
					team1Id: g.team1,
					team2Id: g.team2,
					team1Name: nameOf(names, g.team1),
					team2Name: nameOf(names, g.team2),
					refereeName: g.referees == null ? null : nameOf(names, g.referees),
					isPlayed: g.is_played,
					score1: g.score1,
					score2: g.score2
				}))
				.sort((a, b) => a.round - b.round || a.id - b.id)
		}))
		.filter((d) => d.games.length > 0);
}
```

Run: `docker compose exec -T front npx vitest run src/lib/edition.test.js` → PASS.

- [ ] **Step 3: Write the failing `GameRow` prop tests**

Append to the describe in `front/src/lib/components/GameRow.test.js`:

```js
	it('puts the round label first when given', () => {
		renderWith(GameRow, { ...played, roundLabel: 'R1' });

		expect(screen.getByTestId('game-row')).toHaveTextContent(/^\s*R1\s*Bisons\s*12 : 9\s*Aigles/);
		expect(screen.getByText('R1')).toHaveClass('round');
	});

	it('highlights the own team as plain text and keeps the other one a link', () => {
		renderWith(GameRow, {
			...played,
			team1Id: 2,
			team2Id: 1,
			highlightId: 1,
			team1Href: '/2026/teams/2',
			team2Href: '/2026/teams/1'
		});

		expect(screen.queryByRole('link', { name: 'Aigles' })).toBeNull();
		expect(screen.getByText('Aigles')).toHaveClass('own');
		expect(screen.getByText('Aigles')).toHaveClass('loser');
		expect(screen.getByRole('link', { name: 'Bisons' })).toHaveAttribute('href', '/2026/teams/2');
		expect(screen.getByRole('link', { name: 'Bisons' })).not.toHaveClass('own');
	});

	it('highlights nothing without a highlightId', () => {
		const { container } = renderWith(GameRow, { ...played, team1Id: 2, team2Id: 1 });
		expect(container.querySelector('.own')).toBeNull();
	});
```

Run: `docker compose exec -T front npx vitest run src/lib/components/GameRow`
Expected: the three new tests FAIL.

- [ ] **Step 4: Add the props to `GameRow`**

In `front/src/lib/components/GameRow.svelte`, add after `export let team2Href = null;`:

```js
	/** Short round label ("R1") rendered in a narrow column before the pairing, or null. */
	export let roundLabel = null;
	/** Ids of the two teams, needed only with `highlightId`. */
	export let team1Id = null;
	export let team2Id = null;
	/** The team whose page this row is on: accent colour, plain text instead of a link. */
	export let highlightId = null;

	$: own1 = highlightId !== null && team1Id === highlightId;
	$: own2 = highlightId !== null && team2Id === highlightId;
```

Replace the `<p class="teams">` block with:

```svelte
	<p class="teams">
		{#if roundLabel !== null}
			<span class="round label">{roundLabel}</span>
		{/if}

		{#if team1Href && !own1}
			<a class="team {team1Class}" href={team1Href}>{team1Name ?? t('team.unknown')}</a>
		{:else}
			<span class="team {team1Class}" class:own={own1}>{team1Name ?? t('team.unknown')}</span>
		{/if}

		{#if hasScore}
			<span class="score num">{score1} : {score2}</span>
		{:else if !isPlayed}
			<span class="score num unplayed">— : —</span>
		{:else}
			<span class="score pending">{t('game.played')}</span>
		{/if}

		{#if team2Href && !own2}
			<a class="team right {team2Class}" href={team2Href}>{team2Name ?? t('team.unknown')}</a>
		{:else}
			<span class="team right {team2Class}" class:own={own2}>{team2Name ?? t('team.unknown')}</span>
		{/if}
	</p>
```

Add to the style, after `.team.right`:

```css
	.round {
		flex: none;
		min-width: 2.4rem;
		color: var(--muted);
	}

	.team.own {
		color: var(--accent);
	}

	.team.own.winner {
		font-weight: 600;
	}
```

Run: `docker compose exec -T front npx vitest run src/lib/components/GameRow` → PASS (all, including the earlier ones).

- [ ] **Step 5: Rewrite the team page tests**

`front/src/routes/[year=year]/teams/[id]/page.test.js` becomes:

```js
import { screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { load } from './+page.js';
import { findTeam, teamGames, teamResults } from '$lib/edition';
import { summary } from '$lib/fixtures/summary.js';

const dataFor = (id) => ({
	summary,
	team: findTeam(summary, id),
	results: teamResults(summary, id),
	games: teamGames(summary, id)
});

describe('team page', () => {
	it('shows the name, global rank, total points and the full roster', () => {
		renderWith(Page, { data: dataFor(1) });

		expect(screen.getByRole('heading', { name: 'Aigles' })).toBeInTheDocument();
		expect(screen.getByTestId('standing')).toHaveTextContent(/2nd\s*overall\s*3\s*pts/);
		expect(screen.getByText('Ana Lopez')).toBeInTheDocument();
		expect(screen.getByText('Bob Martin')).toBeInTheDocument();
	});

	it('shows one tile per discipline with a dash when not revealed', () => {
		renderWith(Page, { data: dataFor(1) });

		const rows = screen.getAllByTestId('discipline-row');
		expect(rows).toHaveLength(2);
		expect(rows[0]).toHaveTextContent(/Relay\s*2nd\s*5 pts/);
		expect(rows[1]).toHaveTextContent(/Orienteering\s*—/);
	});

	it('lists the games the team played as discipline-page rows with the own team highlighted', () => {
		renderWith(Page, { data: dataFor(1) });

		expect(screen.getByRole('heading', { name: 'Games' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('game-row');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveTextContent(/R1\s*Bisons\s*12 : 9\s*Aigles/);
		expect(rows[0]).toHaveTextContent('ref: Cerfs');
		expect(rows[1]).toHaveTextContent(/R2\s*Aigles\s*7 : 7\s*Cerfs/);
		expect(rows[2]).toHaveTextContent(/R1\s*Aigles\s*played\s*Bisons/);

		expect(within(rows[0]).getByText('Aigles')).toHaveClass('own');
		expect(within(rows[0]).getByText('Aigles')).toHaveClass('loser');
		expect(within(rows[0]).queryByRole('link', { name: 'Aigles' })).toBeNull();
		expect(within(rows[0]).getByRole('link', { name: 'Bisons' })).toHaveAttribute('href', '/2026/teams/2');
	});

	it('dashes an unplayed game and lists no refereed game', () => {
		renderWith(Page, { data: dataFor(2) });

		const rows = screen.getAllByTestId('game-row');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveTextContent(/R1\s*Bisons\s*12 : 9\s*Aigles/);
		expect(rows[1]).toHaveTextContent(/R1\s*Cerfs\s*— : —\s*Bisons/);
		// Game 203 (Orienteering) is the third row; the refereed Relay game of Aigles never shows for Bisons.
		expect(rows[2]).toHaveTextContent(/R1\s*Aigles\s*played\s*Bisons/);
	});

	it('has no games section when the team has no games', () => {
		renderWith(Page, { data: { ...dataFor(1), games: [] } });
		expect(screen.queryByRole('heading', { name: 'Games' })).toBeNull();
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data: dataFor(2) }, 'fr');

		expect(screen.getByTestId('standing')).toHaveTextContent(/1re\s*au général\s*5\s*pts/);
		expect(screen.getByRole('heading', { name: 'Matchs' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Relais' })).toBeInTheDocument();
		expect(screen.getAllByTestId('game-row')[0]).toHaveTextContent(/T1\s*Bisons\s*12 : 9\s*Aigles/);
		expect(screen.getAllByTestId('discipline-row')[1]).toHaveTextContent(/Course d'orientation\s*—\s*non dévoilé/);
	});
});

describe('team page load', () => {
	it('404s on an id that matches no team', async () => {
		await expect(
			load({ params: { id: 'abc' }, parent: async () => ({ summary }) })
		).rejects.toMatchObject({ status: 404 });
	});
});
```

Run: `docker compose exec -T front npx vitest run "src/routes/\[year=year\]/teams/\[id\]"`
Expected: the game and French tests FAIL.

- [ ] **Step 6: Rewrite the team page**

`front/src/routes/[year=year]/teams/[id]/+page.svelte` script and markup become (keep the style; then edit it as noted below):

```svelte
<script>
	import { iconFor } from '$lib/icons';
	import { disciplineName, useLocale, useT } from '$lib/i18n';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import GameRow from '$lib/components/GameRow.svelte';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: year = data.summary.edition.year;
</script>

<div class="page">
	<Breadcrumb
		items={[
			{ label: String(year), href: `/${year}` },
			{ label: t('nav.teams'), href: `/${year}/teams` },
			{ label: data.team.name }
		]}
	/>

	<h1>{data.team.name}</h1>

	<p class="standing" data-testid="standing">
		<MedalRank rank={data.team.ranking} ordinal />
		<span class="label">{t('team.overall')}</span>
		<span class="num points">{data.team.total_points}</span>
		<span class="label">{t('team.pts')}</span>
	</p>

	<div class="roster">
		{#each data.team.players as player}
			<span class="chip">{player.first_name} {player.last_name}</span>
		{/each}
	</div>

	<h2>{t('team.results')}</h2>
	<div class="tiles">
		{#each data.results as row}
			<div
				class="tile"
				class:gold={row.ranking === 1}
				class:silver={row.ranking === 2}
				class:bronze={row.ranking === 3}
				data-testid="discipline-row"
			>
				<span class="discipline">
					<img src={iconFor(row.disciplineName)} alt="" />
					<span class="label name">{disciplineName(locale, row.disciplineName)}</span>
				</span>
				<MedalRank rank={row.ranking} ordinal />
				<!-- `.num` on the revealed value only: the status is words, not a number. -->
				<span class="value" class:num={row.revealed} class:muted={!row.revealed}>
					{#if !row.revealed}
						{t('team.notRevealed')}
					{:else if row.result_type === 'TIM'}
						{row.time}
					{:else}
						{row.points} {t('team.pts')}
					{/if}
				</span>
			</div>
		{/each}
	</div>

	{#if data.games.length > 0}
		<section class="games">
			<h2>{t('team.games')}</h2>
			{#each data.games as discipline}
				<h3 class="label">{disciplineName(locale, discipline.disciplineName)}</h3>
				{#each discipline.games as game}
					<GameRow
						roundLabel={t('discipline.roundShort', { n: game.round + 1 })}
						highlightId={data.team.id}
						team1Id={game.team1Id}
						team2Id={game.team2Id}
						team1Name={game.team1Name}
						team2Name={game.team2Name}
						team1Href="/{year}/teams/{game.team1Id}"
						team2Href="/{year}/teams/{game.team2Id}"
						score1={game.score1}
						score2={game.score2}
						isPlayed={game.isPlayed}
						refereeName={game.refereeName}
					/>
				{/each}
			{/each}
		</section>
	{/if}
</div>
```

In the style block, the `.games` and `.games h3` rules stay. Nothing else changes.

Run: `docker compose exec -T front npx vitest run "src/routes/\[year=year\]/teams/\[id\]"` → PASS.

- [ ] **Step 7: Delete `TeamGameRow`, run everything**

```bash
git rm -q front/src/lib/components/TeamGameRow.svelte front/src/lib/components/TeamGameRow.test.js
grep -rn "TeamGameRow\|gameResult\|opponentName\|ownScore" front/src docs/superpowers/specs/2026-09-22-scoreboard-ui-design.md CLAUDE.md
```

Expected grep hits: only the scoreboard spec and CLAUDE.md (Task 7 handles those).

Run: `docker compose exec -T front npm test` → green. `docker compose exec -T front npm run build` → `✓ built`.

Browser: `http://localhost:5173/2026/teams/<id of a team with games>` shows under `MATCHS` a discipline label, then rows `T1  Team A  12 : 9  Team B` with the own team in accent, opponents as links, `arbitre : X` below; no row for a refereed game. Switch to EN: `R1`, `ref: X`.

- [ ] **Step 8: Commit**

```bash
git add front/src/lib/edition.js front/src/lib/edition.test.js front/src/lib/components/GameRow.svelte front/src/lib/components/GameRow.test.js "front/src/routes/[year=year]/teams/[id]"
git commit -m "[FEAT] team page: played games as discipline-page rows, own team highlighted, no referee rows

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 7: Static fallback, coverage test, docs, smoke, PR

**Files:**
- Modify: `front/src/error.html`, `front/src/lib/icons.test.js`, `CLAUDE.md`, `docs/superpowers/specs/2026-09-22-scoreboard-ui-design.md`

- [ ] **Step 1: `error.html` in both languages**

In `front/src/error.html`: `<html lang="en">` becomes `<html lang="fr">`; the body becomes:

```html
	<body>
		<h1>%sveltekit.status%</h1>
		<p>Quelque chose s'est mal passé · Something went wrong</p>
		<a href="/">Retour aux Olympic Warriors · Back to the Olympic Warriors</a>
	</body>
```

(`%sveltekit.error.message%` goes: it is English from the framework and the line above says it in both languages.)

- [ ] **Step 2: French name coverage next to the icon coverage**

In `front/src/lib/icons.test.js`, add the import `import { FRENCH_NAMES, SAME_IN_FRENCH } from './i18n/disciplines.js';` and append:

```js
describe('every discipline model has a French name', () => {
	it.each(DISCIPLINE_NAMES)('%s', (name) => {
		expect(name in FRENCH_NAMES || SAME_IN_FRENCH.includes(name)).toBe(true);
	});

	it('lists no discipline twice', () => {
		for (const name of Object.keys(FRENCH_NAMES)) expect(SAME_IN_FRENCH).not.toContain(name);
	});
});
```

Run: `docker compose exec -T front npx vitest run src/lib/icons.test.js` → PASS.

- [ ] **Step 3: CLAUDE.md**

In the "Presentation" area of `CLAUDE.md`:

Replace, in the Shared pieces paragraph, `` `GameRow` (a discipline's schedule line), `TeamGameRow` (a team's game line) `` with `` `GameRow` (a game line: two teams, score, referee; with `roundLabel` and `highlightId` + `team1Id`/`team2Id` the team page reuses it, the own team in accent as plain text, refereed games left out) ``.

Replace the "Page tests assert on text shapes" paragraph's example `` `Round 1 · vs Bisons · 9 : 12 · lost` for a team game row `` with `` `R1 Bisons 12 : 9 Aigles` for a team game row ``.

Add a new paragraph after the "Shared pieces" one:

```markdown
**Two languages, French first.** Every visible string goes through `t` from `front/src/lib/i18n/`: `fr.js` is the reference dictionary, `en.js` mirrors it key for key (`parity.test.js` fails otherwise), counting messages are `{ one, other }` picked with `Intl.PluralRules`, and `disciplines.js` maps database discipline names to French (`icons.test.js` fails when a model is in neither the map nor `SAME_IN_FRENCH`). The locale comes from the `lang` cookie: the root `+layout.server.js` reads it through `localeFrom` (anything but `en` is `fr`), `+layout.svelte` puts it in Svelte context under `I18N`, and components call `useT()` / `useLocale()` at init. `hooks.server.js` sets `<html lang>` from the same cookie. The header's `FR | EN` form posts to `/lang`, whose action stores the cookie for a year and redirects to the local path it was given, so the page reloads fully in the new language and no client code decides it. Helpers in `edition.js` carry no language: `formatDateRange` and `ordinal` take the locale as last argument (`1re`, `2e` in French), `disciplineSubtitle`/`roundCount` return counts the pages word, and an unknown team name is `null` (pages print `team.unknown`). Tests render through `renderWith(Component, props, locale = 'en')` from `src/lib/test-utils.js`, so existing English assertions hold and French has targeted tests. To move to Paraglide or svelte-i18n later: the flat key files convert directly, every call site is a `t(key, params)` and the locale is resolved in one place.
```

- [ ] **Step 4: Scoreboard spec note**

In `docs/superpowers/specs/2026-09-22-scoreboard-ui-design.md`, find the `TeamGameRow.svelte` component entry (grep `TeamGameRow`) and prepend to it: `*(Superseded on 2026-09-23 by the French translation spec: the team page now reuses `GameRow` with `roundLabel` and `highlightId`; `TeamGameRow` is deleted.)*`. Leave the rest as history.

- [ ] **Step 5: Full suite, build, and browser smoke**

Run: `docker compose exec -T front npm test` → green (report the count). `docker compose exec -T front npm run build` → `✓ built`.

Browser smoke on `http://localhost:5173`, desktop then 375 px, French then English (switch via the header, confirm the cookie holds across pages):
- `/`: French date line, `CLASSEMENT` button or `JOURS…`, edition pills.
- `/2026/ranking`: `CLASSEMENT`, rail `Épreuves`, rows `… pts`.
- `/2026/disciplines`: French names (`Quiz de géographie` if present) and subtitles, accented capitals render in Bebas Neue (`ÉPREUVES`).
- a discipline page: `RÉSULTATS`/`Résultats non dévoilés`, `PROGRAMME`, `TOUR 1`, `arbitre : …`.
- `/2026/teams` and a team page: `ÉQUIPES`, `1re AU GÉNÉRAL` shape, `MATCHS`, `T1` rows, own team in accent, no refereed row.
- `/1999`: `Page introuvable`, `RETOUR AUX OLYMPIC WARRIORS`.
- `/login`: `Identifiant`, `Mot de passe`, `CONNEXION`.
- `curl -s http://localhost:5173/ | grep -o '<html lang="[a-z]*"'` → `fr`; with `-b lang=en` → `en`.

- [ ] **Step 6: Commit and open the PR**

```bash
git add front/src/error.html front/src/lib/icons.test.js CLAUDE.md docs/superpowers/specs/2026-09-22-scoreboard-ui-design.md
git commit -m "[DOCS] front: bilingual static fallback, French name coverage, CLAUDE.md on i18n

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin claude/i18n-french
gh pr create --base dev --title "[FEAT] French by default, English switch in the header; team page games on GameRow" --body-file - <<'EOF'
## Summary

- French is the site's default language; a `FR | EN` switch in the header stores the choice in a `lang` cookie for a year (plain form POST to `/lang`, redirect back, full render in the new language, no flash).
- Hand-rolled dictionary (`fr.js` reference, `en.js` mirror, parity-tested), one `t()` lookup with `{name}` placeholders and `Intl.PluralRules` plurals, discipline names mapped to French with a coverage test next to the icon one, French dates and ordinals (`1re`, `2e`).
- The team page shows only the games the team played, with the discipline page's `GameRow` (round label on the left, own team in accent, opponents linked, referee line); `TeamGameRow` is gone.
- `<html lang>` follows the cookie; `error.html` is bilingual.

Spec: `docs/superpowers/specs/2026-09-23-french-translation-design.md`.

## Test plan

- [x] `npm test` green in the front container; `npm run build` ok.
- [x] Browser smoke in both languages at desktop and phone width: hub, ranking, disciplines, a discipline, teams, a team, `/1999`, `/login`.
- [ ] After deploy: switch once on prod and confirm the cookie holds across pages.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
```

---

## Self-review notes

- Spec coverage: locale resolution (T2), switch (T3), dictionary and lookup (T1), keys (T1, all pages T3–T6), discipline names (T1, used T4–T6, coverage T7), helpers (T4, T6), game rows (T6), styles (T3, T6), static fallback (T7), tests (T1–T7), docs (T7). `<html lang>` (T2).
- Deviations from the spec are listed at the top and in the commit bodies.
- Names used across tasks: `I18N`, `t`, `translator`, `useT`, `useLocale`, `disciplineName`, `localeFrom`, `DEFAULT_LOCALE`, `LOCALES`, `FRENCH_NAMES`, `SAME_IN_FRENCH`, `renderWith`; `GameRow` props `roundLabel`, `team1Id`, `team2Id`, `highlightId`; `teamGames` fields `team1Id`, `team2Id`, `team1Name`, `team2Name`, `refereeName`, `isPlayed`, `score1`, `score2`, `round`, `id`.
