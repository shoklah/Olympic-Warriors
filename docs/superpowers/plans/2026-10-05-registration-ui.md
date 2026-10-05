# In-app registration, slice 3: the SvelteKit pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Never touch the development database or the server code**: this slice changes `front/` and docs only; the API is mocked in every test.

**Goal:** The player-facing half of the in-app registration (spec: `docs/superpowers/specs/2026-10-04-in-app-registration-design.md`, "Front"): a login-gated `/register` form, a header link and hub call to action, the claim redirect and the account page for invited newcomers.

**Architecture:** One pure module (`$lib/registration.js`: the form model, its conversion to the API body, the registration-link rule), the `/register` route (server load and two plain-POST actions, a page and one form component), small edits to the layout, `Header`, `EditionHub`, the account page and the claim action. The hub and account links need no API call: they come from the layout data (`me.can_register`, the editions' public window), so no page gains a server load. Everything user-visible goes through `t` with a French and an English dictionary.

**Tech Stack:** SvelteKit 2 / Svelte 4 (plain JS, tabs), Vitest + `@testing-library/svelte` (`renderWith`), adapter-node.

**Prerequisite:** slice 2's API (PR #119: `GET`/`PUT`/`DELETE /registration/`, `can_register` on `/me/`) is the contract. Contract summary, so no implementer needs the server code:
- `GET /registration/` → `{edition: {year, opens, closes, start_date, dates_confirmed}, state: {is_open, reason}, intro: {fr, en}, skills_month: {fr, en}, skills: [{identifier, name_fr, name_en}], disciplines: [name], choices: {frequency|level|practice: [{value, label}]}, email: {value, editable}, registration: null | {registered, removed_by_organiser, ratings: {id: n}, global_level, sport_frequency, sports: [{sport, level, practice, duration_months, notes}], team_wishes, dietary_restrictions, attendance_confirmed}, suggested: null | {year, sport_frequency, dietary_restrictions, sports}}`. `state.reason` is `""`, `late_pass`, `not_configured`, `not_yet_open` or `closed`. A 404 body `{"error": "not_a_person"}` (cannot register) or `{"error": "no_edition"}`.
- `PUT /registration/` takes `{ratings: {id: 1-10}, global_level, sport_frequency, sports: [{sport, level, practice, duration_months, notes}], team_wishes, dietary_restrictions, attendance_confirmed, email?}`; 200 answers the same body as GET; 400 `{"errors": [code, ...]}` with codes `missing_rating invalid_rating invalid_global_level missing_frequency invalid_frequency invalid_sport too_many_sports too_long invalid_text attendance_required no_email invalid_email email_taken`; 409 `{"error": "closed" | "not_yet_open" | "not_configured" | "removed_by_organiser"}`; 429 when throttled.
- `DELETE /registration/` → 204, or 409 `{"error": "has_team"}` (or the closed reasons).
- `/me/` carries `can_register` (a person or an invited newcomer).

**Voice:** the site's strings address the reader as « vous » (« Votre identifiant »), so this slice does too, even where the spec's examples said « ton ». The wording is Hugo's to adjust in `fr.js`.

**Conventions for every task:**
- Tabs for indentation. Component and page tests render through `renderWith(Component, props, locale, organiser)` (English by default, `'fr'` for the French test every translated surface keeps); `use:enhance` is stubbed with `vi.mock('$app/forms', () => ({ enhance: () => ({ destroy() {} }) }))` where a component uses it (this slice's forms are plain POSTs and need no stub). Server tests start with `// @vitest-environment node`, mock `$lib/server/urls` as `vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }))`, and build responses with the `json(status, body)` helper seen in `src/routes/account/page.server.test.js`.
- Run the front suite from `front/`: `npm test` (all) or `npx vitest run <path>`; the build is `npm run build`. If `node_modules` is missing on the host use `docker compose exec -T front npm test`; never `npm install` on the host.
- Where a plan test fails for a mechanic (a role name, an accessible-name detail) fix the test minimally and list the adjustment; where behaviour contradicts the contract above, STOP and report.

---

## File Structure

| File | Responsibility |
|---|---|
| `front/src/lib/registration.js` (create) + `.test.js` | Pure: the form model (`initialValues`, `valuesFromForm`, `bodyFromValues`), API error codes to dictionary keys, the registration-link rule (`registrationLink`), small formatters. |
| `front/src/lib/fixtures/registration.js` (create) | The `GET /registration/` payload for tests. |
| `front/src/lib/i18n/fr.js`, `en.js` (modify) | `register.*`, `nav.register`, `hub.register`, `hub.registration`, `account.registrationLink`. |
| `front/src/routes/+layout.server.js` (+ test) (modify) | `me.can_register`; the registration fields of `editions`. |
| `front/src/lib/components/Header.svelte` (+ test) (modify) | The register link; the account link for an invited newcomer. |
| `front/src/routes/register/+page.server.js`, `+page.svelte` (create) + tests | The `/register` route. |
| `front/src/lib/components/RegistrationForm.svelte` (create) + `.test.js` | The form, its notices and the sports rows; a read-only summary of the saved answers once registration is closed. |
| `front/src/routes/+layout.svelte` (modify) | `/register` has no tab bar. |
| `front/src/lib/components/EditionHub.svelte` (+ test), `routes/+page.svelte`, `routes/[year=year]/+page.svelte`, `routes/login/login.svelte` (+ test) (modify) | The hub link, from the layout data; the login page's invitation note. |
| `front/src/routes/account/+page.server.js`, `+page.svelte` (+ tests) (modify) | An invited newcomer's account page; the registration link. |
| `front/src/lib/server/password-link.js` (+ test), `routes/claim/[uid]/[token]/+page.server.js` (+ test) (modify) | The claim lands on `/register` for an invited newcomer. |
| `CLAUDE.md` (modify) | Document it. |

---

### Task 0: Branch and baseline

- [ ] **Step 1: Branch.** If PR #119 has merged into `dev`: `git fetch origin && git switch -c feat/registration-ui origin/dev`. Otherwise (the API branch is the base for now): `git switch feat/registration-api && git switch -c feat/registration-ui`.

- [ ] **Step 2: Baseline**

```bash
cd front && npm test
```

Expected: all test files pass (about 70 files).

---

### Task 1: `can_register` in the layout, the header links

**Files:**
- Modify: `front/src/routes/+layout.server.js`, `front/src/lib/components/Header.svelte`
- Test: `front/src/routes/layout.server.test.js`, `front/src/lib/components/Header.test.js`

`resolveViewer` keeps only a few `/me/` fields in `me`; `can_register` joins them (an older server sends none and has no `/registration/` either: it reads as false, so no link leads to a page that cannot work). `loadEditions` also keeps the public fields a visitor's call to action needs (`start_date`, `registration_opens`, `registration_closes`).

- [ ] **Step 1: Write the failing tests.** In `routes/layout.server.test.js`, `meBody` gains `can_register: true`; add inside `describe('root layout load', ...)`:

```js
	it('keeps can_register, reading its absence (an older server) as false', async () => {
		const invited = await run({
			token: 'abc',
			user: json(200, meBody({ is_person: false, can_register: true }))
		});
		expect(invited.data.me).toMatchObject({ is_person: false, can_register: true });

		const plain = await run({
			token: 'abc',
			user: json(200, meBody({ is_person: false, can_register: false }))
		});
		expect(plain.data.me.can_register).toBe(false);

		const body = meBody({ is_person: true });
		delete body.can_register;
		const old = await run({ token: 'abc', user: json(200, body) });
		expect(old.data.me.can_register).toBe(false); // no link to a page that server cannot serve
	});

	it('keeps the registration window of each edition for the visitor call to action', async () => {
		const { data } = await run({ token: undefined });

		expect(data.editions[0]).toEqual({
			id: 1, year: 2026, host: 'Paris', photos_url: null,
			start_date: '2026-09-19', registration_opens: '2026-01-01', registration_closes: null
		});
	});
```

Update the module's `editions` fixture to `[{ id: 1, year: 2026, host: 'Paris', photos_url: null, start_date: '2026-09-19', registration_opens: '2026-01-01', registration_closes: null }]` and every existing `me` expectation in the file to include `can_register` (add, never loosen).

In `Header.test.js`, inside `describe('for a logged-in player', ...)` add (look at how that block builds `me` and renders; reuse its helper):

```js
		it('links the registration page for anyone who can register', () => {
			renderWith(Header, { me: { ...player, can_register: true } }, 'en');

			expect(screen.getByRole('link', { name: 'Register' })).toHaveAttribute('href', '/register');
		});

		it('shows no registration link to someone who cannot register', () => {
			renderWith(Header, { me: { ...player, can_register: false } }, 'en');

			expect(screen.queryByRole('link', { name: 'Register' })).toBeNull();
		});

		it('links the account of an invited newcomer, who has no profile page yet', () => {
			renderWith(Header, { me: { ...player, is_person: false, can_register: true } }, 'en');

			expect(screen.getByRole('link', { name: /My account/ })).toHaveAttribute('href', '/account');
			expect(screen.getByRole('link', { name: 'Register' })).toHaveAttribute('href', '/register');
		});

		it('words the registration link in French', () => {
			renderWith(Header, { me: { ...player, can_register: true } }, 'fr');

			expect(screen.getByRole('link', { name: "S'inscrire" })).toHaveAttribute('href', '/register');
		});
```

(`player` stands for the `me` object that block already defines; use its real name. The account link's accessible name is `<first name> · My account`, from `account.title`.) Inside `describe('for an organiser', ...)` add one test: an organiser who plays and `can_register` sees the `Register` link beside the ORGA pill, and one who never played (`can_register: false`) sees none.

- [ ] **Step 2: Run to verify it fails**

Run: `cd front && npx vitest run src/routes/layout.server.test.js src/lib/components/Header.test.js`
Expected: the new tests fail (`can_register` undefined, no Register link).

- [ ] **Step 3: Implement the layout.** In `routes/+layout.server.js`, change the destructuring and the returned `me`:

```js
		const { id, first_name, last_name, photo, is_person, can_register, photo_locked } = user;
		return {
			organiser: Boolean(user.is_staff),
			me: {
				id,
				first_name: first_name ?? '',
				last_name: last_name ?? '',
				photo: photo ?? null,
				is_person: Boolean(is_person),
				// A person, or invited. An older server sends none and cannot serve /registration/.
				can_register: can_register === true,
				photo_locked: Boolean(photo_locked)
			}
		};
```

update `resolveViewer`'s doc comment (« `can_register` for the registration link »), and `loadEditions`:

```js
async function loadEditions(fetch) {
	return (await apiGet(fetch, api('/editions/')))
		.map(({ id, year, host, photos_url, start_date, registration_opens, registration_closes }) => ({
			id, year, host, photos_url,
			// Public, for a visitor's registration call to action (the hub, lib/registration.js).
			start_date: start_date ?? null,
			registration_opens: registration_opens ?? null,
			registration_closes: registration_closes ?? null
		}))
		.sort((a, b) => b.year - a.year);
}
```

- [ ] **Step 4: Implement the header.** In `Header.svelte`'s script add `$: canRegister = Boolean(me?.can_register);` and `$: hasAccount = Boolean(me?.is_person || me?.can_register);`. In the organiser branch change `{#if me?.is_person}` to `{#if hasAccount}`, and add before the account link, inside the same `.account` div, `{#if canRegister}<a class="register" href="/register">{t('nav.register')}</a>{/if}`. In the logged-in-player branch change `{#if me.is_person}` to `{#if hasAccount}` and put the same `{#if canRegister}` link first inside `<div class="account">`. For an organiser with `canRegister` but no account link the `.account` div cannot be empty: because `hasAccount` is true whenever `canRegister` is, no extra case exists. Style the link like the account link (add `.account a.register` next to `.account a.who`: the same quiet look, a visible keyboard focus ring, `white-space: nowrap`). Add `nav.register` to both dictionaries now (`fr.js`: `'nav.register': "S'inscrire"`; `en.js`: `'nav.register': 'Register'`), beside `nav.players`.

- [ ] **Step 5: Run the tests**

Run: `cd front && npx vitest run src/routes src/lib/components/Header.test.js src/lib/i18n`
Expected: all pass (the parity test checks the new key).

- [ ] **Step 6: Commit**

```bash
git add front/src/routes/+layout.server.js front/src/routes/layout.server.test.js front/src/lib/components/Header.svelte front/src/lib/components/Header.test.js front/src/lib/i18n/fr.js front/src/lib/i18n/en.js
git commit -m "[FEAT] header: register link, account link for invited newcomers; can_register in the layout

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The pure registration module

**Files:**
- Create: `front/src/lib/registration.js`, `front/src/lib/registration.test.js`, `front/src/lib/fixtures/registration.js`

- [ ] **Step 1: The fixture.** Create `lib/fixtures/registration.js`:

```js
/** `GET /registration/` for the 2027 edition, open, nothing saved yet. */
export const registrationPayload = {
	edition: {
		year: 2027,
		opens: '2027-01-01',
		closes: '2027-09-17',
		start_date: '2027-09-18',
		dates_confirmed: true
	},
	state: { is_open: true, reason: '' },
	intro: { fr: 'Bienvenue aux inscriptions', en: 'Welcome to registration' },
	skills_month: { fr: 'août', en: 'August' },
	skills: [
		{ identifier: 'CARD', name_fr: 'Cardio', name_en: 'Cardio' },
		{ identifier: 'STR', name_fr: 'Force', name_en: 'Strength' }
	],
	disciplines: ['Relay', 'Darts'],
	choices: {
		frequency: [
			{ value: 'rare', label: "Moins d'une fois par mois" },
			{ value: 'monthly', label: 'Moins d’une fois par semaine mais plusieurs fois par mois' },
			{ value: 'hour', label: 'Environ une heure par semaine' },
			{ value: 'two_hours', label: 'Au moins deux heures par semaine' },
			{ value: 'four_hours', label: 'Au moins quatre heures par semaine' }
		],
		level: [
			{ value: 'beginner', label: 'Débutant' },
			{ value: 'amateur', label: 'Amateur' },
			{ value: 'club', label: 'Club' },
			{ value: 'competition', label: 'Compétition' }
		],
		practice: [
			{ value: 'no_longer', label: 'Ne pratique plus' },
			{ value: 'occasionally', label: 'Pratique occasionnelle' },
			{ value: 'regularly', label: 'Pratique régulière' }
		]
	},
	email: { value: 'lea@example.com', editable: false },
	registration: null,
	suggested: null
};

/** What a registered player's `registration` holds. */
export const savedAnswers = {
	registered: true,
	removed_by_organiser: false,
	ratings: { CARD: 6, STR: 7 },
	global_level: 8,
	sport_frequency: 'two_hours',
	sports: [
		{ sport: 'Judo', level: 'amateur', practice: 'no_longer', duration_months: 30, notes: 'Ceinture orange' }
	],
	team_wishes: 'Avec Bob',
	dietary_restrictions: 'Végane',
	attendance_confirmed: true
};
```

- [ ] **Step 2: Write the failing tests.** Create `lib/registration.test.js`:

```js
import { describe, expect, it } from 'vitest';
import {
	bodyFromValues,
	choiceLabel,
	durationParts,
	emptySport,
	errorKeys,
	initialValues,
	listNames,
	monthsOf,
	parisToday,
	registrationLink,
	valuesFromForm,
	visitorCta
} from './registration.js';
import { registrationPayload, savedAnswers } from './fixtures/registration.js';

const formOf = (entries) => {
	const form = new FormData();
	for (const [name, value] of entries) form.append(name, value);
	return form;
};

describe('durations', () => {
	it('splits months into years and months', () => {
		expect(durationParts(30)).toEqual({ years: '2', months: '6' });
		expect(durationParts(0)).toEqual({ years: '0', months: '0' });
		expect(durationParts(null)).toEqual({ years: '', months: '' });
	});

	it('joins years and months, null when both are blank', () => {
		expect(monthsOf('2', '6')).toBe(30);
		expect(monthsOf('', '8')).toBe(8);
		expect(monthsOf('3', '')).toBe(36);
		expect(monthsOf('', '')).toBeNull();
	});

	it('hands the API a value it refuses rather than hiding a bad one', () => {
		expect(monthsOf('-1', '')).toBeLessThan(0);
		expect(monthsOf('1.5', '')).toBeLessThan(0);
		expect(monthsOf('abc', '')).toBeLessThan(0);
	});
});

describe('initialValues', () => {
	it('starts blank, with one empty sports row', () => {
		const values = initialValues(registrationPayload);

		expect(values.ratings).toEqual({ CARD: '', STR: '' });
		expect(values.global_level).toBe('');
		expect(values.sports).toEqual([emptySport()]);
		expect(values.attendance_confirmed).toBe(false);
		expect(values.email).toBe('');
	});

	it('fills from the saved answers', () => {
		const values = initialValues({ ...registrationPayload, registration: savedAnswers });

		expect(values.ratings).toEqual({ CARD: '6', STR: '7' });
		expect(values.global_level).toBe('8');
		expect(values.sport_frequency).toBe('two_hours');
		expect(values.sports).toEqual([
			{ sport: 'Judo', level: 'amateur', practice: 'no_longer', years: '2', months: '6', notes: 'Ceinture orange' }
		]);
		expect(values.team_wishes).toBe('Avec Bob');
		expect(values.attendance_confirmed).toBe(true);
	});

	it('offers only the stable suggested answers to someone who has not registered', () => {
		const payload = {
			...registrationPayload,
			suggested: {
				year: 2026,
				sport_frequency: 'hour',
				dietary_restrictions: 'Sans gluten',
				sports: [{ sport: 'Tennis', level: '', practice: '', duration_months: null, notes: '30/1' }]
			}
		};

		const values = initialValues(payload);

		expect(values.sport_frequency).toBe('hour');
		expect(values.dietary_restrictions).toBe('Sans gluten');
		expect(values.sports[0]).toMatchObject({ sport: 'Tennis', notes: '30/1', years: '', months: '' });
		expect(values.ratings).toEqual({ CARD: '', STR: '' });
		expect(values.team_wishes).toBe('');
		expect(values.attendance_confirmed).toBe(false);
	});

	it('keeps one blank sports row after a refusal that posted none', () => {
		const posted = { ...initialValues(registrationPayload), sports: [] };

		expect(initialValues(registrationPayload, posted).sports).toEqual([emptySport()]);
	});

	it('prefers what was posted (a refused save) over everything', () => {
		const posted = { ...initialValues(registrationPayload), global_level: '99', team_wishes: 'typed' };

		const values = initialValues({ ...registrationPayload, registration: savedAnswers }, posted);

		expect(values.global_level).toBe('99');
		expect(values.team_wishes).toBe('typed');
	});
});

describe('valuesFromForm and bodyFromValues', () => {
	const entries = [
		['skill', 'CARD'],
		['skill', 'STR'],
		['rating.CARD', '6'],
		['rating.STR', '7'],
		['global_level', '8'],
		['sport_frequency', 'two_hours'],
		['sport.0.sport', ' Judo '],
		['sport.0.level', 'amateur'],
		['sport.0.practice', 'no_longer'],
		['sport.0.years', '2'],
		['sport.0.months', '6'],
		['sport.0.notes', 'Ceinture orange'],
		['sport.1.sport', ''],
		['sport.1.level', ''],
		['sport.1.practice', ''],
		['sport.1.years', ''],
		['sport.1.months', ''],
		['sport.1.notes', ''],
		['team_wishes', 'Avec Bob'],
		['dietary_restrictions', ''],
		['attendance_confirmed', 'on']
	];

	it('reads the posted form back into the form model, dropping blank sports rows', () => {
		const values = valuesFromForm(formOf(entries));

		expect(values.ratings).toEqual({ CARD: '6', STR: '7' });
		expect(values.sports).toEqual([
			{ sport: ' Judo ', level: 'amateur', practice: 'no_longer', years: '2', months: '6', notes: 'Ceinture orange' }
		]);
		expect(values.attendance_confirmed).toBe(true);
		expect(values.email).toBe('');
	});

	it('orders sports rows by their index, whatever the order they were posted in', () => {
		const values = valuesFromForm(
			formOf([['sport.10.sport', 'B'], ['sport.2.sport', 'A'], ['skill', 'CARD']])
		);

		expect(values.sports.map((s) => s.sport)).toEqual(['A', 'B']);
	});

	it('builds the API body', () => {
		const body = bodyFromValues(valuesFromForm(formOf(entries)), false);

		expect(body).toEqual({
			ratings: { CARD: 6, STR: 7 },
			global_level: 8,
			sport_frequency: 'two_hours',
			sports: [
				{ sport: 'Judo', level: 'amateur', practice: 'no_longer', duration_months: 30, notes: 'Ceinture orange' }
			],
			team_wishes: 'Avec Bob',
			dietary_restrictions: '',
			attendance_confirmed: true
		});
	});

	it('sends the email only when the form asked for one', () => {
		const values = { ...valuesFromForm(formOf(entries)), email: ' New@Example.com ' };

		expect(bodyFromValues(values, false)).not.toHaveProperty('email');
		expect(bodyFromValues(values, true).email).toBe('New@Example.com');
	});

	it('leaves a blank rating out and passes a bad one on for the API to refuse', () => {
		const values = valuesFromForm(formOf([['skill', 'CARD'], ['skill', 'STR'], ['rating.CARD', ''], ['rating.STR', 'x'], ['global_level', '']]));

		const body = bodyFromValues(values, false);

		expect(body.ratings).toEqual({ STR: 'x' });
		expect(body.global_level).toBeNull();
	});
});

describe('errorKeys', () => {
	it('words the API codes, once each, in order', () => {
		expect(errorKeys(['missing_rating', 'attendance_required', 'missing_rating'])).toEqual([
			'register.error.missing_rating',
			'register.error.attendance_required'
		]);
	});

	it('reads a code it does not know as one generic refusal', () => {
		expect(errorKeys(['brand_new'])).toEqual(['register.error.invalid']);
		expect(errorKeys([])).toEqual(['register.error.invalid']);
	});
});

describe('choiceLabel', () => {
	const t = (key) => ({ 'register.level.club': 'Club (club)' })[key] ?? key;

	it('uses the dictionary, then the API label for a value the front does not know', () => {
		expect(choiceLabel(t, 'level', { value: 'club', label: 'Club' })).toBe('Club (club)');
		expect(choiceLabel(t, 'level', { value: 'olympic', label: 'Olympique' })).toBe('Olympique');
	});
});

describe('listNames', () => {
	it('joins names with the locale conjunction', () => {
		expect(listNames('en', ['Relay', 'Darts', 'Hide and Seek'])).toBe('Relay, Darts, and Hide and Seek');
		expect(listNames('fr', ['Relais', 'Fléchettes'])).toBe('Relais et Fléchettes');
		expect(listNames('en', [])).toBe('');
	});
});

describe('the registration link', () => {
	const editions = [
		{ year: 2027, start_date: '2027-09-18', registration_opens: '2027-05-01', registration_closes: null },
		{ year: 2026, start_date: '2026-09-19', registration_opens: '2026-01-01', registration_closes: null }
	];

	it('sends a visitor through the login while the public window is open', () => {
		expect(registrationLink({ me: null, editions, today: '2027-06-01' })).toEqual({
			href: '/login?next=/register', year: 2027, visitor: true
		});
	});

	it('links someone who can register straight to the form', () => {
		const me = { id: 1, can_register: true };

		expect(registrationLink({ me, editions, today: '2027-06-01' })).toEqual({
			href: '/register', year: 2027, visitor: false
		});
	});

	it('is nothing for someone who cannot register, outside the window, or with no edition', () => {
		expect(registrationLink({ me: { id: 1, can_register: false }, editions, today: '2027-06-01' })).toBeNull();
		expect(registrationLink({ me: null, editions, today: '2027-04-01' })).toBeNull();
		expect(registrationLink({ me: null, editions: [], today: '2027-06-01' })).toBeNull();
		expect(registrationLink({ me: null, editions: undefined, today: '2027-06-01' })).toBeNull();
	});

	it('only ever concerns the latest edition', () => {
		const old = [{ year: 2026, start_date: '2026-09-19', registration_opens: '2026-01-01', registration_closes: null }];

		expect(registrationLink({ me: null, editions: old, today: '2026-06-01' }).year).toBe(2026);
		expect(registrationLink({ me: null, editions: [...editions].reverse(), today: '2027-06-01' })).toBeNull();
	});
});

describe('visitorCta', () => {
	it('is the public window: opening day reached, closing day (or the day before the start) not passed', () => {
		const edition = { start_date: '2027-09-18', registration_opens: '2027-05-01', registration_closes: null };

		expect(visitorCta(edition, '2027-04-30')).toBe(false);
		expect(visitorCta(edition, '2027-05-01')).toBe(true);
		expect(visitorCta(edition, '2027-09-17')).toBe(true); // the day before the start
		expect(visitorCta(edition, '2027-09-18')).toBe(false);
		expect(visitorCta({ ...edition, registration_closes: '2027-06-30' }, '2027-06-30')).toBe(true);
		expect(visitorCta({ ...edition, registration_closes: '2027-06-30' }, '2027-07-01')).toBe(false);
		expect(visitorCta({ ...edition, registration_opens: null }, '2027-06-01')).toBe(false);
		expect(visitorCta(undefined, '2027-06-01')).toBe(false);
	});
});

describe('parisToday', () => {
	it('reads today in Paris', () => {
		expect(parisToday(new Date('2027-06-01T22:30:00Z'))).toBe('2027-06-02'); // already tomorrow there
		expect(parisToday(new Date('2027-01-15T10:00:00Z'))).toBe('2027-01-15');
	});
});
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd front && npx vitest run src/lib/registration.test.js`
Expected: FAIL (module not found).

- [ ] **Step 4: Implement `lib/registration.js`**

```js
/**
 * The registration form's model and rules, with no Svelte and no network (spec
 * 2026-10-04). The form model keeps every value as the string the browser posts, so a refused
 * save can hand exactly what was typed back to the page; `bodyFromValues` turns it into the
 * API's JSON.
 */

/** Sports the API accepts (enrolment.MAX_SPORTS). */
export const MAX_SPORTS = 15;

/** An empty row of the sports table. */
export const emptySport = () => ({ sport: '', level: '', practice: '', years: '', months: '', notes: '' });

/** Months as the two fields a person fills: years and months, blank when unknown. */
export function durationParts(total) {
	if (total === null || total === undefined) return { years: '', months: '' };
	return { years: String(Math.floor(total / 12)), months: String(total % 12) };
}

/**
 * Years and months back to a number of months: null when both are blank. A value that is
 * not a whole non-negative number comes back negative, which the API refuses
 * (`invalid_sport`): a bad entry is reported, never silently dropped.
 */
export function monthsOf(years, months) {
	const y = String(years ?? '').trim();
	const m = String(months ?? '').trim();
	if (y === '' && m === '') return null;
	const whole = (s) => (s === '' ? 0 : /^\d+$/.test(s) ? Number(s) : NaN);
	const total = whole(y) * 12 + whole(m);
	return Number.isFinite(total) ? total : -1;
}

const text = (value) => (value === null || value === undefined ? '' : String(value));

const sportFrom = (row) => ({
	sport: text(row.sport),
	level: text(row.level),
	practice: text(row.practice),
	...durationParts(row.duration_months),
	notes: text(row.notes)
});

/**
 * The form model of a `GET /registration/` payload: what was posted last (`posted`, the
 * model a refused save returned), else the caller's saved answers, else the stable answers
 * suggested from their last registration (sports, frequency, dietary restrictions: never
 * the ratings, wishes or the tick), else blanks. Always at least one sports row.
 */
export function initialValues(payload, posted = null) {
	if (posted) {
		return { ...posted, sports: posted.sports?.length > 0 ? posted.sports : [emptySport()] };
	}
	const values = {
		ratings: Object.fromEntries(payload.skills.map((s) => [s.identifier, ''])),
		global_level: '',
		sport_frequency: '',
		sports: [],
		team_wishes: '',
		dietary_restrictions: '',
		attendance_confirmed: false,
		email: ''
	};
	const saved = payload.registration;
	const suggested = payload.suggested;
	if (saved) {
		for (const skill of payload.skills) {
			if (saved.ratings?.[skill.identifier] !== undefined) {
				values.ratings[skill.identifier] = String(saved.ratings[skill.identifier]);
			}
		}
		values.global_level = text(saved.global_level);
		values.sport_frequency = text(saved.sport_frequency);
		values.sports = (saved.sports ?? []).map(sportFrom);
		values.team_wishes = text(saved.team_wishes);
		values.dietary_restrictions = text(saved.dietary_restrictions);
		values.attendance_confirmed = Boolean(saved.attendance_confirmed);
	} else if (suggested) {
		values.sport_frequency = text(suggested.sport_frequency);
		values.dietary_restrictions = text(suggested.dietary_restrictions);
		values.sports = (suggested.sports ?? []).map(sportFrom);
	}
	if (values.sports.length === 0) values.sports = [emptySport()];
	return values;
}

const SPORT_FIELD = /^sport\.(\d+)\.(sport|level|practice|years|months|notes)$/;

/**
 * The form model of a posted `FormData`: the skills listed in the hidden `skill` fields, the
 * sports rows by index (blank rows dropped), the tick as a boolean. Pure, so the server
 * action can return it to the page after a refusal.
 */
export function valuesFromForm(form) {
	const rows = new Map();
	for (const [name, value] of form.entries()) {
		const match = SPORT_FIELD.exec(name);
		if (!match) continue;
		const index = Number(match[1]);
		if (!rows.has(index)) rows.set(index, emptySport());
		rows.get(index)[match[2]] = String(value);
	}
	const sports = [...rows.entries()]
		.sort(([a], [b]) => a - b)
		.map(([, row]) => row)
		.filter((row) => Object.values(row).some((value) => value.trim() !== ''));
	return {
		ratings: Object.fromEntries(form.getAll('skill').map((id) => [id, text(form.get(`rating.${id}`))])),
		global_level: text(form.get('global_level')),
		sport_frequency: text(form.get('sport_frequency')),
		sports,
		team_wishes: text(form.get('team_wishes')),
		dietary_restrictions: text(form.get('dietary_restrictions')),
		attendance_confirmed: form.get('attendance_confirmed') === 'on',
		email: text(form.get('email'))
	};
}

const WHOLE = /^-?\d+$/;

/** A number field as the API wants it: a whole number as a number, a blank as `blank`, anything else as typed (the API refuses it). */
const asNumber = (value, blank) => {
	const s = text(value).trim();
	if (s === '') return blank;
	return WHOLE.test(s) ? Number(s) : s;
};

/**
 * The `PUT /registration/` body of a form model. A blank rating is left out and a blank
 * global level sent as null, so the API reports them; nothing is corrected silently. The
 * email only goes when the form asked for one (the account had no usable address).
 */
export function bodyFromValues(values, emailEditable) {
	const ratings = {};
	for (const [id, value] of Object.entries(values.ratings)) {
		const rating = asNumber(value, undefined);
		if (rating !== undefined) ratings[id] = rating;
	}
	const body = {
		ratings,
		global_level: asNumber(values.global_level, null),
		sport_frequency: values.sport_frequency,
		sports: values.sports.map((row) => ({
			sport: row.sport.trim(),
			level: row.level,
			practice: row.practice,
			duration_months: monthsOf(row.years, row.months),
			notes: row.notes.trim()
		})),
		team_wishes: values.team_wishes,
		dietary_restrictions: values.dietary_restrictions,
		attendance_confirmed: values.attendance_confirmed
	};
	if (emailEditable) body.email = values.email.trim();
	return body;
}

const ERROR_CODES = new Set([
	'missing_rating', 'invalid_rating', 'invalid_global_level', 'missing_frequency',
	'invalid_frequency', 'invalid_sport', 'too_many_sports', 'too_long', 'invalid_text',
	'attendance_required', 'no_email', 'invalid_email', 'email_taken'
]);

/**
 * The dictionary keys for the API's validation codes, once each, in its order. A code this
 * page does not know (added on the server later), or none, reads as one generic refusal.
 */
export function errorKeys(codes) {
	const keys = (Array.isArray(codes) ? codes : []).map((code) =>
		ERROR_CODES.has(code) ? `register.error.${code}` : 'register.error.invalid'
	);
	return keys.length > 0 ? [...new Set(keys)] : ['register.error.invalid'];
}

/** The label of a choice: the dictionary's (`register.<kind>.<value>`), else the API's for a value the front does not know. */
export function choiceLabel(t, kind, choice) {
	const key = `register.${kind}.${choice.value}`;
	const label = t(key);
	return label === key ? choice.label : label;
}

/** Names joined with the locale's conjunction (`Relais, Fléchettes et Darts`). */
export function listNames(locale, names) {
	return new Intl.ListFormat(locale, { style: 'long', type: 'conjunction' }).format(names);
}

/** Today's date in Paris as `YYYY-MM-DD`: the event's calendar, whatever the renderer's timezone. */
export function parisToday(now = new Date()) {
	return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Paris' }).format(now);
}

const dayBefore = (iso) => {
	const date = new Date(`${iso}T00:00:00Z`);
	date.setUTCDate(date.getUTCDate() - 1);
	return date.toISOString().slice(0, 10);
};

/**
 * Whether a visitor, who cannot ask the API, is shown the way in: the public window is open
 * (opening day set and reached, not past `registration_closes`, or the day before the start
 * when blank). The API decides for real once they log in; this only avoids a dead end.
 */
export function visitorCta(edition, today) {
	if (!edition?.registration_opens || !edition.start_date) return false;
	const closes = edition.registration_closes ?? dayBefore(edition.start_date);
	return today >= edition.registration_opens && today <= closes;
}

/**
 * The registration link of the hub and of the account page, from the layout data alone
 * (no API call): `{ href, year, visitor }` while the latest edition's public window is open,
 * else null. A visitor goes through the login; someone logged in who can register goes
 * straight to the form, which shows whether they are registered and offers the edit.
 */
export function registrationLink({ me, editions, today }) {
	const latest = editions?.[0];
	if (!latest || !visitorCta(latest, today)) return null;
	if (!me) return { href: '/login?next=/register', year: latest.year, visitor: true };
	return me.can_register ? { href: '/register', year: latest.year, visitor: false } : null;
}
```

- [ ] **Step 5: Run the tests**

Run: `cd front && npx vitest run src/lib/registration.test.js`
Expected: `OK`. (If `Intl.ListFormat` in the test runtime words the English list without the Oxford comma, fix the one assertion to what the runtime prints and say so.)

- [ ] **Step 6: Commit**

```bash
git add front/src/lib/registration.js front/src/lib/registration.test.js front/src/lib/fixtures/registration.js
git commit -m "[FEAT] pure registration module: form model, API body, call-to-action rules

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The dictionaries

**Files:**
- Modify: `front/src/lib/i18n/fr.js`, `front/src/lib/i18n/en.js`

`parity.test.js` already fails on any key present in one dictionary only; this task adds every string the slice uses, so the later tasks only reference keys.

- [ ] **Step 1: Add to `fr.js`** (after the `account.*` block; keep alphabetical-ish grouping the file already uses):

```js
	'account.section.registration': 'Inscription',
	'account.registrationLink': 'Inscription {year}',
	'hub.register': "Se connecter pour s'inscrire",
	'hub.registration': 'Inscription {year}',
	'login.registerNote':
		"Les inscriptions se font sur invitation : si vous n'avez pas encore de compte, contactez les organisateurs.",
	'register.title': 'Inscription {year}',
	'register.visibility': 'Votre nom apparaîtra dans la liste des joueurs.',
	'register.retention':
		'Vos réponses sont conservées tant que votre compte existe, et visibles des organisateurs seulement.',
	'register.closed.not_configured': "Les inscriptions ne sont pas encore ouvertes.",
	'register.closed.not_yet_open': 'Les inscriptions ouvrent le {date}.',
	'register.closed.closed': 'Les inscriptions sont terminées. Contactez les organisateurs pour toute demande.',
	'register.latePass': 'Les organisateurs ont autorisé votre inscription tardive.',
	'register.removed': 'Un organisateur a retiré votre inscription : contactez-le pour la rétablir.',
	'register.registered': 'Vous êtes inscrit·e. Vous pouvez modifier vos réponses tant que les inscriptions sont ouvertes.',
	'register.saved': 'Inscription enregistrée',
	'register.suggested': 'Repris de votre inscription {year} : vérifiez que tout est à jour.',
	'register.skillsIntro':
		'Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimez-vous le niveau que vous aurez en {month} selon les critères suivants ?',
	'register.skillsIntroNoMonth':
		'Sur une échelle de 1 (le plus faible) à 10 (le plus élevé), comment estimez-vous votre niveau selon les critères suivants ?',
	'register.globalLevel': 'Niveau global',
	'register.globalQuestion':
		'Sur une échelle de 1 à 10, comment estimez-vous votre niveau global pour les Olympic Warriors de {year} : {disciplines} ?',
	'register.globalQuestionShort':
		'Sur une échelle de 1 à 10, comment estimez-vous votre niveau global pour les Olympic Warriors de {year} ?',
	'register.frequency.legend': 'À quelle fréquence pratiquez-vous du sport ?',
	'register.frequency.rare': "Moins d'une fois par mois",
	'register.frequency.monthly': "Moins d'une fois par semaine mais plusieurs fois par mois",
	'register.frequency.hour': 'Environ une heure par semaine',
	'register.frequency.two_hours': 'Au moins deux heures par semaine',
	'register.frequency.four_hours': 'Au moins quatre heures par semaine',
	'register.sports.legend': 'Sports pratiqués (dans toute votre vie, à tout niveau)',
	'register.sports.sport': 'Sport',
	'register.sports.level': 'Niveau',
	'register.sports.practice': 'Pratique actuelle',
	'register.sports.years': 'Années',
	'register.sports.months': 'Mois',
	'register.sports.notes': 'Précisions (poste, spécialité…)',
	'register.sports.add': 'Ajouter un sport',
	'register.sports.remove': 'Retirer le sport {n}',
	'register.sports.none': '—',
	'register.level.beginner': 'Débutant',
	'register.level.amateur': 'Amateur',
	'register.level.club': 'Club',
	'register.level.competition': 'Compétition',
	'register.practice.no_longer': 'Ne pratique plus',
	'register.practice.occasionally': 'Pratique occasionnelle',
	'register.practice.regularly': 'Pratique régulière',
	'register.teamWishes': 'Avec qui souhaitez-vous être ou ne pas être en équipe ?',
	'register.teamWishesHint': 'Ces demandes restent confidentielles. Elles ne pourront pas toutes être satisfaites.',
	'register.dietary': 'Restrictions alimentaires',
	'register.optional': 'Facultatif',
	'register.email': 'Adresse e-mail',
	'register.emailNeeded':
		'Indiquez une adresse e-mail valide : elle servira aussi à retrouver votre mot de passe.',
	'register.emailChange': 'Modifier mon adresse',
	'register.attendance': "J'ai payé mon inscription et je confirme que je serai là",
	'register.submit': "M'inscrire",
	'register.submitEdit': 'Enregistrer mes réponses',
	'register.withdraw': 'Me désinscrire',
	'register.withdrawNote': 'Vos réponses sont conservées si vous vous inscrivez de nouveau.',
	'register.withdrawn': 'Vous êtes désinscrit·e. Vos réponses sont conservées.',
	'register.summary.title': 'Vos réponses',
	'register.summary.none': '—',
	'register.summary.years': { one: '{n} an', other: '{n} ans' },
	'register.summary.months': { one: '{n} mois', other: '{n} mois' },
	'register.summary.attendance': 'Présence confirmée',
	'register.error.missing_rating': 'Donnez une note à chaque critère',
	'register.error.invalid_rating': 'Les notes vont de 1 à 10',
	'register.error.invalid_global_level': 'Indiquez un niveau global de 1 à 10',
	'register.error.missing_frequency': 'Indiquez à quelle fréquence vous faites du sport',
	'register.error.invalid_frequency': 'Fréquence invalide',
	'register.error.invalid_sport': 'Une ligne de sport est incomplète ou invalide',
	'register.error.too_many_sports': '15 sports au maximum',
	'register.error.too_long': 'Un texte est trop long',
	'register.error.invalid_text': 'Un texte contient un caractère non valide',
	'register.error.attendance_required': 'Cochez la case de confirmation',
	'register.error.no_email': 'Indiquez une adresse e-mail',
	'register.error.invalid_email': 'Adresse e-mail invalide',
	'register.error.email_taken': 'Cette adresse est déjà utilisée par un autre compte',
	'register.error.invalid': 'Réponses refusées : vérifiez le formulaire',
	'register.error.closed': 'Les inscriptions sont terminées.',
	'register.error.not_yet_open': "Les inscriptions ne sont pas encore ouvertes.",
	'register.error.not_configured': "Les inscriptions ne sont pas encore ouvertes.",
	'register.error.removed_by_organiser': 'Un organisateur a retiré votre inscription : contactez-le pour la rétablir.',
	'register.error.has_team': 'Vous êtes déjà dans une équipe : contactez les organisateurs pour vous désinscrire.',
	'register.error.throttled': 'Trop de tentatives : réessayez plus tard',
	'register.error.failed': "L'enregistrement a échoué : réessayez plus tard",
```

- [ ] **Step 2: Add to `en.js`** the same keys, same order:

```js
	'account.section.registration': 'Registration',
	'account.registrationLink': 'Registration {year}',
	'hub.register': 'Log in to register',
	'hub.registration': 'Registration {year}',
	'login.registerNote':
		'Registration is by invitation: if you do not have an account yet, contact the organisers.',
	'register.title': 'Registration {year}',
	'register.visibility': 'Your name will appear in the players list.',
	'register.retention': 'Your answers are kept as long as your account exists, and only organisers can see them.',
	'register.closed.not_configured': 'Registration is not open yet.',
	'register.closed.not_yet_open': 'Registration opens on {date}.',
	'register.closed.closed': 'Registration is closed. Contact the organisers for any request.',
	'register.latePass': 'The organisers have allowed your late registration.',
	'register.removed': 'An organiser removed your registration: contact them to restore it.',
	'register.registered': 'You are registered. You can edit your answers while registration is open.',
	'register.saved': 'Registration saved',
	'register.suggested': 'Taken from your {year} registration: check that everything is up to date.',
	'register.skillsIntro':
		'On a scale from 1 (lowest) to 10 (highest), how would you rate the level you will have in {month} on the following criteria?',
	'register.skillsIntroNoMonth':
		'On a scale from 1 (lowest) to 10 (highest), how would you rate your level on the following criteria?',
	'register.globalLevel': 'Overall level',
	'register.globalQuestion':
		'On a scale from 1 to 10, how would you rate your overall level for Olympic Warriors {year}: {disciplines}?',
	'register.globalQuestionShort':
		'On a scale from 1 to 10, how would you rate your overall level for Olympic Warriors {year}?',
	'register.frequency.legend': 'How often do you play sport?',
	'register.frequency.rare': 'Less than once a month',
	'register.frequency.monthly': 'Less than once a week but several times a month',
	'register.frequency.hour': 'About one hour a week',
	'register.frequency.two_hours': 'At least two hours a week',
	'register.frequency.four_hours': 'At least four hours a week',
	'register.sports.legend': 'Sports you have played (in your whole life, at any level)',
	'register.sports.sport': 'Sport',
	'register.sports.level': 'Level',
	'register.sports.practice': 'Currently',
	'register.sports.years': 'Years',
	'register.sports.months': 'Months',
	'register.sports.notes': 'Details (position, specialty…)',
	'register.sports.add': 'Add a sport',
	'register.sports.remove': 'Remove sport {n}',
	'register.sports.none': '—',
	'register.level.beginner': 'Beginner',
	'register.level.amateur': 'Amateur',
	'register.level.club': 'Club',
	'register.level.competition': 'Competition',
	'register.practice.no_longer': 'No longer playing',
	'register.practice.occasionally': 'Occasionally',
	'register.practice.regularly': 'Regularly',
	'register.teamWishes': 'Who would you like to be, or not to be, in a team with?',
	'register.teamWishesHint': 'These requests stay confidential. Not all of them can be met.',
	'register.dietary': 'Dietary restrictions',
	'register.optional': 'Optional',
	'register.email': 'Email address',
	'register.emailNeeded': 'Enter a valid email address: it also lets you recover your password.',
	'register.emailChange': 'Change my address',
	'register.attendance': 'I have paid my registration and I confirm I will be there',
	'register.submit': 'Register',
	'register.submitEdit': 'Save my answers',
	'register.withdraw': 'Withdraw my registration',
	'register.withdrawNote': 'Your answers are kept if you register again.',
	'register.withdrawn': 'You are withdrawn. Your answers are kept.',
	'register.summary.title': 'Your answers',
	'register.summary.none': '—',
	'register.summary.years': { one: '{n} year', other: '{n} years' },
	'register.summary.months': { one: '{n} month', other: '{n} months' },
	'register.summary.attendance': 'Attendance confirmed',
	'register.error.missing_rating': 'Rate every criterion',
	'register.error.invalid_rating': 'Ratings go from 1 to 10',
	'register.error.invalid_global_level': 'Enter an overall level from 1 to 10',
	'register.error.missing_frequency': 'Say how often you play sport',
	'register.error.invalid_frequency': 'Invalid frequency',
	'register.error.invalid_sport': 'A sports row is incomplete or invalid',
	'register.error.too_many_sports': '15 sports at most',
	'register.error.too_long': 'A text is too long',
	'register.error.invalid_text': 'A text contains an invalid character',
	'register.error.attendance_required': 'Tick the confirmation box',
	'register.error.no_email': 'Enter an email address',
	'register.error.invalid_email': 'Invalid email address',
	'register.error.email_taken': 'This address is already used by another account',
	'register.error.invalid': 'Answers refused: check the form',
	'register.error.closed': 'Registration is closed.',
	'register.error.not_yet_open': 'Registration is not open yet.',
	'register.error.not_configured': 'Registration is not open yet.',
	'register.error.removed_by_organiser': 'An organiser removed your registration: contact them to restore it.',
	'register.error.has_team': 'You are already in a team: contact the organisers to withdraw.',
	'register.error.throttled': 'Too many attempts: try again later',
	'register.error.failed': 'Saving failed: try again later',
```

- [ ] **Step 3: Run the dictionary tests**

Run: `cd front && npx vitest run src/lib/i18n`
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add front/src/lib/i18n/fr.js front/src/lib/i18n/en.js
git commit -m "[FEAT] dictionaries for the registration pages

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The `/register` route (server)

**Files:**
- Create: `front/src/routes/register/+page.server.js`
- Modify: `front/src/routes/+layout.svelte` (`NO_TAB_BAR`)
- Test: `front/src/routes/register/page.server.test.js`

- [ ] **Step 1: Write the failing tests.** Create `routes/register/page.server.test.js`:

```js
// @vitest-environment node
// The actions read a real Request's form body, so these tests use Node's own FormData and Request.
import { describe, expect, it, vi } from 'vitest';
import { actions, load } from './+page.server.js';
import { registrationPayload } from '$lib/fixtures/registration.js';

vi.mock('$lib/server/urls', () => ({ api: (path) => `http://api${path}` }));

const json = (status, body) =>
	new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const cookiesWith = (token = 't') => ({
	get: (name) => (name === 'token' ? token : undefined),
	set: vi.fn(),
	delete: vi.fn()
});

/** A POST of `entries` (name/value pairs, repeats allowed) to the register page's `action`. */
const post = (action, entries) => {
	const form = new FormData();
	for (const [name, value] of entries) form.append(name, value);
	return new Request(`http://x/register?/${action}`, { method: 'POST', body: form });
};

const goodEntries = [
	['skill', 'CARD'], ['skill', 'STR'], ['rating.CARD', '6'], ['rating.STR', '7'],
	['global_level', '8'], ['sport_frequency', 'two_hours'],
	['sport.0.sport', 'Judo'], ['sport.0.level', 'amateur'], ['sport.0.practice', 'no_longer'],
	['sport.0.years', '2'], ['sport.0.months', '6'], ['sport.0.notes', ''],
	['team_wishes', ''], ['dietary_restrictions', ''], ['attendance_confirmed', 'on']
];

describe('register load', () => {
	it('sends a visitor to /login with a 303 and asks nothing', async () => {
		const fetch = vi.fn();
		await expect(load({ fetch, cookies: cookiesWith(null), setHeaders: vi.fn() })).rejects.toMatchObject({
			status: 303,
			location: '/login?next=/register'
		});
		expect(fetch).not.toHaveBeenCalled();
	});

	it('returns the registration form, never cached, asked with the token', async () => {
		const fetch = vi.fn(async () => json(200, registrationPayload));
		const setHeaders = vi.fn();

		const data = await load({ fetch, cookies: cookiesWith(), setHeaders });

		expect(fetch.mock.calls[0][0]).toBe('http://api/registration/');
		expect(fetch.mock.calls[0][1].headers).toEqual({ authorization: 'Token t' });
		expect(data).toEqual({ registration: registrationPayload });
		expect(setHeaders).toHaveBeenCalledWith({ 'cache-control': 'private, no-store' });
	});

	it('sends a dead token to /login too', async () => {
		const fetch = vi.fn(async () => json(401, { detail: 'Invalid token.' }));
		await expect(load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() })).rejects.toMatchObject({
			status: 303,
			location: '/login?next=/register'
		});
	});

	it('sends someone who cannot register home', async () => {
		const fetch = vi.fn(async () => json(404, { error: 'not_a_person' }));
		await expect(load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() })).rejects.toMatchObject({
			status: 303,
			location: '/'
		});
	});

	it('lets any other failure reach the error page', async () => {
		const fetch = vi.fn(async () => json(404, { error: 'no_edition' }));
		await expect(load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() })).rejects.toMatchObject({ status: 404 });
	});
});

describe('register save', () => {
	it('puts the answers as JSON and reports success', async () => {
		const fetch = vi.fn(async () => json(200, registrationPayload));

		const result = await actions.save({ request: post('save', goodEntries), cookies: cookiesWith(), fetch });

		const [url, options] = fetch.mock.calls[0];
		expect(url).toBe('http://api/registration/');
		expect(options.method).toBe('PUT');
		expect(options.headers).toMatchObject({ authorization: 'Token t', 'content-type': 'application/json' });
		expect(JSON.parse(options.body)).toEqual({
			ratings: { CARD: 6, STR: 7 },
			global_level: 8,
			sport_frequency: 'two_hours',
			sports: [{ sport: 'Judo', level: 'amateur', practice: 'no_longer', duration_months: 30, notes: '' }],
			team_wishes: '',
			dietary_restrictions: '',
			attendance_confirmed: true
		});
		expect(result).toEqual({ ok: true, action: 'save' });
	});

	it('sends the email only when the form had an email field', async () => {
		const fetch = vi.fn(async () => json(200, registrationPayload));

		await actions.save({ request: post('save', [...goodEntries, ['email', ' New@Example.com ']]), cookies: cookiesWith(), fetch });

		expect(JSON.parse(fetch.mock.calls[0][1].body).email).toBe('New@Example.com');
	});

	it("hands the API's codes back as dictionary keys with what was typed", async () => {
		const fetch = vi.fn(async () => json(400, { errors: ['missing_rating', 'attendance_required'] }));
		const entries = goodEntries.filter(([name]) => name !== 'attendance_confirmed' && name !== 'rating.STR');

		const result = await actions.save({ request: post('save', entries), cookies: cookiesWith(), fetch });

		expect(result.status).toBe(400);
		expect(result.data).toMatchObject({
			action: 'save',
			errors: ['register.error.missing_rating', 'register.error.attendance_required']
		});
		expect(result.data.values.ratings).toEqual({ CARD: '6', STR: '' });
		expect(result.data.values.team_wishes).toBe('');
	});

	it.each([
		[409, { error: 'closed' }, 'register.error.closed'],
		[409, { error: 'not_yet_open' }, 'register.error.not_yet_open'],
		[409, { error: 'removed_by_organiser' }, 'register.error.removed_by_organiser'],
		[429, { detail: 'Throttled' }, 'register.error.throttled'],
		[500, { detail: 'boom' }, 'register.error.failed']
	])('words a %i %j refusal', async (status, body, key) => {
		const fetch = vi.fn(async () => json(status, body));

		const result = await actions.save({ request: post('save', goodEntries), cookies: cookiesWith(), fetch });

		expect(result.status).toBe(status);
		expect(result.data).toMatchObject({ action: 'save', error: key });
		expect(result.data.values).toBeDefined();
	});

	it('refuses without a token', async () => {
		const fetch = vi.fn();

		const result = await actions.save({ request: post('save', goodEntries), cookies: cookiesWith(null), fetch });

		expect(result.status).toBe(403);
		expect(fetch).not.toHaveBeenCalled();
	});
});

describe('register withdraw', () => {
	it('deletes the registration', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 204 }));

		const result = await actions.withdraw({ request: post('withdraw', []), cookies: cookiesWith(), fetch });

		expect(fetch.mock.calls[0][0]).toBe('http://api/registration/');
		expect(fetch.mock.calls[0][1].method).toBe('DELETE');
		expect(result).toEqual({ ok: true, action: 'withdraw' });
	});

	it('words a placed player refusal', async () => {
		const fetch = vi.fn(async () => json(409, { error: 'has_team' }));

		const result = await actions.withdraw({ request: post('withdraw', []), cookies: cookiesWith(), fetch });

		expect(result.status).toBe(409);
		expect(result.data).toMatchObject({ action: 'withdraw', error: 'register.error.has_team' });
	});
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd front && npx vitest run src/routes/register/page.server.test.js`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `routes/register/+page.server.js`**

```js
import { fail, redirect } from '@sveltejs/kit';
import { apiGet, apiSend, statusOf } from '$lib/api';
import { bodyFromValues, errorKeys, valuesFromForm } from '$lib/registration';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE } from '$lib/session';

/** Where a visitor goes to log in, then comes back here. */
const LOGIN = '/login?next=/register';

/** The refusals the API words with an `{error}` code, each with its own sentence. */
const REFUSALS = new Set([
	'closed', 'not_yet_open', 'not_configured', 'removed_by_organiser', 'has_team'
]);

/**
 * The page is the caller's own registration for the latest edition: a visitor (or a dead
 * token) goes to /login, someone who cannot register (neither a person nor invited) goes
 * home, anything else, such as no edition at all, reaches the error page. Never cached: it
 * shows the person's answers.
 */
export const load = async ({ fetch, cookies, setHeaders }) => {
	const token = cookies.get(TOKEN_COOKIE);
	if (!token) redirect(303, LOGIN);
	setHeaders({ 'cache-control': 'private, no-store' });
	try {
		return { registration: await apiGet(fetch, api('/registration/'), token) };
	} catch (err) {
		if (err?.status === 401 || err?.status === 403) redirect(303, LOGIN);
		if (err?.status === 404 && err?.body?.message === 'not_a_person') redirect(303, '/');
		throw err;
	}
};

/** Dictionary key of a failed registration call: its `{error}` code (in the message) or a status. */
function registrationError(err) {
	if (statusOf(err) === 429) return 'register.error.throttled';
	const code = err?.body?.message;
	return REFUSALS.has(code) ? `register.error.${code}` : 'register.error.failed';
}

/** The posted form, or an empty one for a body that is not a form. */
async function formOf(request) {
	try {
		return await request.formData();
	} catch {
		return new FormData();
	}
}

export const actions = {
	/**
	 * Register, or edit the registration. A plain POST (never use:enhance): the page reloads
	 * with the saved answers. A refusal comes back with the codes as dictionary keys and the
	 * form model as typed, so the page keeps what the person wrote.
	 */
	save: async ({ request, cookies, fetch }) => {
		const token = cookies.get(TOKEN_COOKIE);
		if (!token) return fail(403, { action: 'save', error: 'register.error.failed' });
		const form = await formOf(request);
		const values = valuesFromForm(form);
		const body = bodyFromValues(values, form.has('email'));
		try {
			await apiSend(fetch, api('/registration/'), {
				method: 'PUT',
				token,
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify(body)
			});
		} catch (err) {
			const codes = err?.body?.errors;
			if (statusOf(err) === 400 && Array.isArray(codes)) {
				return fail(400, { action: 'save', errors: errorKeys(codes), values });
			}
			return fail(statusOf(err), { action: 'save', error: registrationError(err), values });
		}
		return { ok: true, action: 'save' };
	},

	/** Withdraw; the answers are kept for a later registration. */
	withdraw: async ({ cookies, fetch }) => {
		const token = cookies.get(TOKEN_COOKIE);
		if (!token) return fail(403, { action: 'withdraw', error: 'register.error.failed' });
		try {
			await apiSend(fetch, api('/registration/'), { method: 'DELETE', token });
		} catch (err) {
			return fail(statusOf(err), { action: 'withdraw', error: registrationError(err) });
		}
		return { ok: true, action: 'withdraw' };
	}
};
```

In `routes/+layout.svelte`, add `'/register'` to the `NO_TAB_BAR` set and update the comment above it (« …the login, claim, account and registration pages »).

- [ ] **Step 4: Run**

Run: `cd front && npx vitest run src/routes/register src/routes/layout.test.js`
Expected: `OK`. (`layout.test.js` may pin the `NO_TAB_BAR` routes: if so extend its list with `/register`.)

- [ ] **Step 5: Commit**

```bash
git add front/src/routes/register/+page.server.js front/src/routes/register/page.server.test.js front/src/routes/+layout.svelte front/src/routes/layout.test.js
git commit -m "[FEAT] /register: load, save and withdraw actions

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The registration form (page and component)

**Files:**
- Create: `front/src/lib/components/RegistrationForm.svelte`, `front/src/routes/register/+page.svelte`
- Test: `front/src/lib/components/RegistrationForm.test.js`, `front/src/routes/register/page.test.js`

- [ ] **Step 1: Write the failing component tests.** Create `lib/components/RegistrationForm.test.js`:

```js
import { fireEvent, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import RegistrationForm from './RegistrationForm.svelte';
import { registrationPayload, savedAnswers } from '$lib/fixtures/registration.js';

const open = registrationPayload;
const registered = { ...registrationPayload, registration: savedAnswers };
const closed = (reason) => ({ ...registrationPayload, state: { is_open: false, reason } });

describe('RegistrationForm', () => {
	it('shows the intro, one rating field per skill and the global question with the programme', () => {
		renderWith(RegistrationForm, { registration: open });

		expect(screen.getByText('Welcome to registration')).toBeInTheDocument();
		expect(screen.getByText(/the level you will have in August/)).toBeInTheDocument();
		expect(screen.getByLabelText('Cardio')).toHaveAttribute('name', 'rating.CARD');
		expect(screen.getByLabelText('Strength')).toHaveAttribute('name', 'rating.STR');
		expect(screen.getByLabelText('Cardio')).toHaveAttribute('min', '1');
		expect(screen.getByLabelText('Cardio')).toHaveAttribute('max', '10');
		expect(
			screen.getByText('On a scale from 1 to 10, how would you rate your overall level for Olympic Warriors 2027: Relay and Darts?')
		).toBeInTheDocument();
		// The skills travel with the form, so the server knows which ratings to read.
		expect(document.querySelectorAll('input[type="hidden"][name="skill"]')).toHaveLength(2);
	});

	it('leaves the month out when the edition names none, and the programme when it has none', () => {
		renderWith(RegistrationForm, {
			registration: { ...open, skills_month: { fr: '', en: '' }, disciplines: [] }
		});

		expect(screen.getByText(/how would you rate your level on the following criteria/)).toBeInTheDocument();
		expect(screen.getByText(/overall level for Olympic Warriors 2027\?/)).toBeInTheDocument();
	});

	it('offers the five frequencies as radios, with the dictionary wording', () => {
		renderWith(RegistrationForm, { registration: open });

		const group = screen.getByRole('group', { name: 'How often do you play sport?' });
		expect(within(group).getAllByRole('radio')).toHaveLength(5);
		expect(within(group).getByLabelText('At least two hours a week')).toHaveAttribute('value', 'two_hours');
	});

	it('shows the email read-only, with a way to change it, when the account has a usable one', () => {
		renderWith(RegistrationForm, { registration: open });

		expect(screen.getByText('lea@example.com')).toBeInTheDocument();
		expect(screen.queryByRole('textbox', { name: 'Email address' })).toBeNull();
		expect(screen.getByRole('link', { name: 'Change my address' })).toHaveAttribute('href', '/account');
	});

	it('asks for an email when the account has none', () => {
		renderWith(RegistrationForm, { registration: { ...open, email: { value: '', editable: true } } });

		const field = screen.getByRole('textbox', { name: 'Email address' });
		expect(field).toHaveAttribute('name', 'email');
		expect(field).toBeRequired();
		expect(screen.getByText(/also lets you recover your password/)).toBeInTheDocument();
	});

	it('requires the confirmation tick and shows the visibility and retention notices', () => {
		renderWith(RegistrationForm, { registration: open });

		expect(screen.getByRole('checkbox', { name: /I have paid my registration/ })).toBeRequired();
		expect(screen.getByText('Your name will appear in the players list.')).toBeInTheDocument();
		expect(screen.getByText(/kept as long as your account exists/)).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument();
	});

	it('adds and removes sports rows, indexed in order', async () => {
		renderWith(RegistrationForm, { registration: open });

		expect(screen.getAllByRole('textbox', { name: 'Sport' })).toHaveLength(1);
		await fireEvent.click(screen.getByRole('button', { name: 'Add a sport' }));
		const rows = screen.getAllByRole('textbox', { name: 'Sport' });
		expect(rows.map((r) => r.getAttribute('name'))).toEqual(['sport.0.sport', 'sport.1.sport']);

		await fireEvent.click(screen.getByRole('button', { name: 'Remove sport 1' }));
		expect(screen.getAllByRole('textbox', { name: 'Sport' })).toHaveLength(1);
		expect(screen.getByRole('textbox', { name: 'Sport' })).toHaveAttribute('name', 'sport.0.sport');
	});

	it('stops adding at fifteen sports', async () => {
		renderWith(RegistrationForm, { registration: open });
		for (let i = 0; i < 14; i++) await fireEvent.click(screen.getByRole('button', { name: 'Add a sport' }));

		expect(screen.getAllByRole('textbox', { name: 'Sport' })).toHaveLength(15);
		expect(screen.getByRole('button', { name: 'Add a sport' })).toBeDisabled();
	});

	it('fills the saved answers and offers to withdraw', () => {
		renderWith(RegistrationForm, { registration: registered });

		expect(screen.getByLabelText('Cardio')).toHaveValue(6);
		expect(screen.getByLabelText('Overall level')).toHaveValue(8);
		expect(screen.getByRole('radio', { name: 'At least two hours a week' })).toBeChecked();
		expect(screen.getByRole('textbox', { name: 'Sport' })).toHaveValue('Judo');
		expect(screen.getByRole('spinbutton', { name: 'Years' })).toHaveValue(2);
		expect(screen.getByRole('spinbutton', { name: 'Months' })).toHaveValue(6);
		expect(screen.getByText(/You are registered/)).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Save my answers' })).toBeInTheDocument();
		const withdraw = screen.getByRole('button', { name: 'Withdraw my registration' });
		expect(withdraw.closest('form')).toHaveAttribute('action', '?/withdraw');
	});

	it('tells someone suggested answers were taken from last time', () => {
		const suggested = {
			year: 2026, sport_frequency: 'hour', dietary_restrictions: 'Sans gluten',
			sports: [{ sport: 'Tennis', level: '', practice: '', duration_months: null, notes: '' }]
		};
		renderWith(RegistrationForm, { registration: { ...open, suggested } });

		expect(screen.getByText('Taken from your 2026 registration: check that everything is up to date.')).toBeInTheDocument();
		expect(screen.getByRole('textbox', { name: 'Sport' })).toHaveValue('Tennis');
		expect(screen.getByRole('radio', { name: 'About one hour a week' })).toBeChecked();
	});

	it('keeps what was typed after a refusal and lists every error', () => {
		const values = {
			ratings: { CARD: '9', STR: '' }, global_level: '', sport_frequency: '', sports: [],
			team_wishes: 'typed wish', dietary_restrictions: '', attendance_confirmed: false, email: ''
		};
		renderWith(RegistrationForm, {
			registration: open,
			form: { action: 'save', errors: ['register.error.missing_rating', 'register.error.attendance_required'], values }
		});

		const alert = screen.getByRole('alert');
		expect(within(alert).getByText('Rate every criterion')).toBeInTheDocument();
		expect(within(alert).getByText('Tick the confirmation box')).toBeInTheDocument();
		expect(screen.getByLabelText('Cardio')).toHaveValue(9);
		expect(screen.getByRole('textbox', { name: /Who would you like to be/ })).toHaveValue('typed wish');
	});

	it('words a single refusal and confirms a save', () => {
		const { unmount } = renderWith(RegistrationForm, {
			registration: open, form: { action: 'save', error: 'register.error.closed', values: undefined }
		});
		expect(screen.getByRole('alert')).toHaveTextContent('Registration is closed.');
		unmount();

		renderWith(RegistrationForm, { registration: registered, form: { ok: true, action: 'save' } });
		expect(screen.getByRole('status')).toHaveTextContent('Registration saved');
	});

	it('shows the has_team refusal of a withdrawal', () => {
		renderWith(RegistrationForm, {
			registration: registered, form: { action: 'withdraw', error: 'register.error.has_team' }
		});

		expect(screen.getByRole('alert')).toHaveTextContent('You are already in a team');
	});

	it.each([
		['not_configured', 'Registration is not open yet.'],
		['not_yet_open', 'Registration opens on 1 January 2027.'],
		['closed', 'Registration is closed. Contact the organisers for any request.']
	])('shows a %s registration as a notice, with no form', (reason, text) => {
		renderWith(RegistrationForm, { registration: closed(reason) });

		expect(screen.getByText(text)).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Register' })).toBeNull();
		expect(screen.queryByLabelText('Cardio')).toBeNull();
	});

	it('shows a registered player their answers, read-only, once registration is closed', () => {
		renderWith(RegistrationForm, { registration: { ...closed('closed'), registration: savedAnswers } });

		const summary = screen.getByRole('region', { name: 'Your answers' });
		expect(within(summary).getByText('Cardio')).toBeInTheDocument();
		expect(within(summary).getByText('6')).toBeInTheDocument();
		expect(within(summary).getByText('At least two hours a week')).toBeInTheDocument();
		expect(within(summary).getByText(/Judo/)).toHaveTextContent('Amateur');
		expect(within(summary).getByText(/Judo/)).toHaveTextContent('2 years 6 months');
		expect(within(summary).getByText(/Judo/)).toHaveTextContent('Ceinture orange');
		expect(within(summary).getByText('Avec Bob')).toBeInTheDocument();
		expect(within(summary).getByText('Végane')).toBeInTheDocument();
		expect(within(summary).getByText('Attendance confirmed')).toBeInTheDocument();
		expect(screen.queryByRole('spinbutton')).toBeNull();
		expect(screen.queryByRole('button')).toBeNull();
	});

	it('shows no summary to someone who is not registered, withdrew, or was removed', () => {
		const none = renderWith(RegistrationForm, { registration: closed('closed') });
		expect(screen.queryByRole('region', { name: 'Your answers' })).toBeNull();
		none.unmount();

		const withdrew = renderWith(RegistrationForm, {
			registration: { ...closed('closed'), registration: { ...savedAnswers, registered: false } }
		});
		expect(screen.queryByRole('region', { name: 'Your answers' })).toBeNull();
		withdrew.unmount();

		renderWith(RegistrationForm, {
			registration: { ...closed('closed'), registration: { ...savedAnswers, registered: false, removed_by_organiser: true } }
		});
		expect(screen.queryByRole('region', { name: 'Your answers' })).toBeNull();
	});

	it('speaks French in the summary', () => {
		renderWith(RegistrationForm, { registration: { ...closed('closed'), registration: savedAnswers } }, 'fr');

		expect(screen.getByRole('region', { name: 'Vos réponses' })).toBeInTheDocument();
		expect(screen.getByText(/Judo/)).toHaveTextContent('2 ans 6 mois');
	});

	it('mentions a late pass and shows the form', () => {
		renderWith(RegistrationForm, { registration: { ...open, state: { is_open: true, reason: 'late_pass' } } });

		expect(screen.getByText('The organisers have allowed your late registration.')).toBeInTheDocument();
		expect(screen.getByLabelText('Cardio')).toBeInTheDocument();
	});

	it('explains an organiser removal and shows no form', () => {
		renderWith(RegistrationForm, {
			registration: { ...registered, registration: { ...savedAnswers, registered: false, removed_by_organiser: true } }
		});

		expect(screen.getByText(/An organiser removed your registration/)).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Save my answers' })).toBeNull();
	});

	it('shows a withdrawn registration as withdrawn, with the form to register again', () => {
		renderWith(RegistrationForm, {
			registration: { ...registered, registration: { ...savedAnswers, registered: false } }
		});

		expect(screen.getByText('You are withdrawn. Your answers are kept.')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument();
		expect(screen.getByLabelText('Cardio')).toHaveValue(6);
	});

	it('speaks French', () => {
		renderWith(RegistrationForm, { registration: open }, 'fr');

		expect(screen.getByText('Bienvenue aux inscriptions')).toBeInTheDocument();
		expect(screen.getByLabelText('Cardio')).toBeInTheDocument();
		expect(screen.getByLabelText('Force')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: "M'inscrire" })).toBeInTheDocument();
		expect(screen.getByText('Votre nom apparaîtra dans la liste des joueurs.')).toBeInTheDocument();
		expect(screen.getByText(/pour les Olympic Warriors de 2027 : Relais et Fléchettes/)).toBeInTheDocument();
	});
});
```

(The French programme names come from `disciplineName(locale, name)`; if the repo has no French « Relais » or « Fléchettes » entries for `Relay`/`Darts`, take the names `FRENCH_NAMES` gives and change that one assertion.)

- [ ] **Step 2: Write the failing page test.** Create `routes/register/page.test.js`:

```js
import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { registrationPayload } from '$lib/fixtures/registration.js';

describe('register page', () => {
	it('shows the title with the year and the form', () => {
		renderWith(Page, { data: { registration: registrationPayload }, form: null });

		expect(screen.getByRole('heading', { level: 1, name: 'Registration 2027' })).toBeInTheDocument();
		expect(screen.getByLabelText('Cardio')).toBeInTheDocument();
	});

	it('words the title in French', () => {
		renderWith(Page, { data: { registration: registrationPayload }, form: null }, 'fr');

		expect(screen.getByRole('heading', { level: 1, name: 'Inscription 2027' })).toBeInTheDocument();
	});
});
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd front && npx vitest run src/lib/components/RegistrationForm.test.js src/routes/register/page.test.js`
Expected: FAIL (components missing).

- [ ] **Step 4: Implement `RegistrationForm.svelte`.** Plain POSTs; the sports rows are Svelte state (add/remove need JS; the first blank row works without it).

```svelte
<script>
	import { onMount } from 'svelte';
	import { disciplineName, useLocale, useT } from '$lib/i18n';
	import { MAX_SPORTS, choiceLabel, durationParts, emptySport, initialValues, listNames } from '$lib/registration';

	/** The `GET /registration/` payload. */
	export let registration;
	/** The result of the last post to this page, or null. */
	export let form = null;

	const t = useT();
	const locale = useLocale();

	$: edition = registration.edition;
	$: open = registration.state.is_open;
	$: saved = registration.registration;
	$: registered = Boolean(saved?.registered);
	$: removed = Boolean(saved?.removed_by_organiser);
	$: late = registration.state.reason === 'late_pass';

	// The model the inputs read: what was typed before a refusal, else saved, else suggested.
	let values;
	$: values = initialValues(registration, form?.values ?? null);

	// A month in the wrong language would sit oddly in a sentence: none beats the French one.
	$: month = registration.skills_month[locale] || '';
	$: skillName = (skill) => (locale === 'fr' ? skill.name_fr : skill.name_en);
	$: programme = listNames(
		locale,
		registration.disciplines.map((name) => disciplineName(locale, name))
	);
	$: introText = registration.intro[locale] || registration.intro.fr || '';

	/** The date the registration opens, in words. */
	$: opensOn = registration.edition.opens
		? new Intl.DateTimeFormat(locale === 'fr' ? 'fr' : 'en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(
				new Date(`${registration.edition.opens}T12:00:00Z`)
			)
		: '';

	$: resultOf = (action) => (form?.action === action ? form : null);
	$: saveResult = resultOf('save');
	$: withdrawResult = resultOf('withdraw');
	$: errorKeys = saveResult?.errors ?? (saveResult?.error ? [saveResult.error] : []);

	/** The label of a stored choice for the summary, the dash for none. */
	function summaryChoice(kind, value) {
		const choice = registration.choices[kind]?.find((c) => c.value === value);
		return choice ? choiceLabel(t, kind, choice) : t('register.summary.none');
	}

	/** One sports row as a line: sport, level, practice, how long, details; blanks left out. */
	function sportLine(row) {
		const { years, months } = durationParts(row.duration_months);
		const duration = [
			Number(years) > 0 && t('register.summary.years', { n: Number(years) }),
			Number(months) > 0 && t('register.summary.months', { n: Number(months) })
		]
			.filter(Boolean)
			.join(' ');
		return [
			row.sport,
			row.level && summaryChoice('level', row.level),
			row.practice && summaryChoice('practice', row.practice),
			duration,
			row.notes
		]
			.filter(Boolean)
			.join(' · ');
	}

	function addSport() {
		if (values.sports.length < MAX_SPORTS) values.sports = [...values.sports, emptySport()];
	}
	function removeSport(index) {
		const rest = values.sports.filter((_, i) => i !== index);
		values.sports = rest.length > 0 ? rest : [emptySport()];
	}

	// A plain POST reloads the page with the message not announced: focus it.
	onMount(() => {
		const target = document.getElementById(form?.ok ? 'register-status' : 'register-errors');
		if (!target || !form) return;
		target.focus();
		target.scrollIntoView?.({ block: 'center' });
	});
</script>

{#if introText}<p class="intro">{introText}</p>{/if}

{#if late}<p class="notice">{t('register.latePass')}</p>{/if}

{#if removed}
	<p class="notice" role="note">{t('register.removed')}</p>
{:else if !open}
	{#if registration.state.reason === 'not_yet_open' && opensOn}
		<p class="notice">{t('register.closed.not_yet_open', { date: opensOn })}</p>
	{:else}
		<p class="notice">{t(`register.closed.${registration.state.reason === 'closed' ? 'closed' : 'not_configured'}`)}</p>
	{/if}
	{#if registered && saved}
		<p class="notice">{t('register.registered')}</p>
		<!-- Closed: what they submitted stays readable (the form is gone). -->
		<section class="summary" aria-labelledby="register-summary">
			<h2 id="register-summary">{t('register.summary.title')}</h2>
			<dl>
				{#each registration.skills as skill}
					<dt>{skillName(skill)}</dt>
					<dd>{saved.ratings?.[skill.identifier] ?? t('register.summary.none')}</dd>
				{/each}
				<dt>{t('register.globalLevel')}</dt>
				<dd>{saved.global_level ?? t('register.summary.none')}</dd>
				<dt>{t('register.frequency.legend')}</dt>
				<dd>{summaryChoice('frequency', saved.sport_frequency)}</dd>
				<dt>{t('register.sports.legend')}</dt>
				<dd>
					{#if saved.sports.length === 0}
						{t('register.summary.none')}
					{:else}
						<ul>
							{#each saved.sports as row}
								<li>{sportLine(row)}</li>
							{/each}
						</ul>
					{/if}
				</dd>
				<dt>{t('register.teamWishes')}</dt>
				<dd>{saved.team_wishes || t('register.summary.none')}</dd>
				<dt>{t('register.dietary')}</dt>
				<dd>{saved.dietary_restrictions || t('register.summary.none')}</dd>
			</dl>
			{#if saved.attendance_confirmed}<p class="notes">{t('register.summary.attendance')}</p>{/if}
		</section>
	{/if}
{:else}
	{#if form?.ok && form.action === 'save'}
		<p class="saved" id="register-status" tabindex="-1" role="status">{t('register.saved')}</p>
	{:else if form?.ok && form.action === 'withdraw'}
		<p class="saved" id="register-status" tabindex="-1" role="status">{t('register.withdrawn')}</p>
	{/if}
	{#if registered}
		<p class="notice">{t('register.registered')}</p>
	{:else if saved}
		<p class="notice">{t('register.withdrawn')}</p>
	{:else if registration.suggested}
		<p class="notice">{t('register.suggested', { year: registration.suggested.year })}</p>
	{/if}

	<form method="POST" action="?/save" class="registration">
		{#each registration.skills as skill}
			<input type="hidden" name="skill" value={skill.identifier} />
		{/each}

		<section aria-labelledby="register-skills">
			<h2 id="register-skills">
				{month ? t('register.skillsIntro', { month }) : t('register.skillsIntroNoMonth')}
			</h2>
			{#each registration.skills as skill}
				<div class="field">
					<label for="rating-{skill.identifier}">{skillName(skill)}</label>
					<input
						id="rating-{skill.identifier}"
						type="number"
						name="rating.{skill.identifier}"
						min="1"
						max="10"
						step="1"
						inputmode="numeric"
						required
						bind:value={values.ratings[skill.identifier]}
					/>
				</div>
			{/each}
			<div class="field">
				<label for="global-level">{t('register.globalLevel')}</label>
				<p class="hint">
					{programme
						? t('register.globalQuestion', { year: edition.year, disciplines: programme })
						: t('register.globalQuestionShort', { year: edition.year })}
				</p>
				<input
					id="global-level"
					type="number"
					name="global_level"
					min="1"
					max="10"
					step="1"
					inputmode="numeric"
					required
					bind:value={values.global_level}
				/>
			</div>
		</section>

		<fieldset>
			<legend>{t('register.frequency.legend')}</legend>
			{#each registration.choices.frequency as choice}
				<label class="radio">
					<input type="radio" name="sport_frequency" value={choice.value} required bind:group={values.sport_frequency} />
					{choiceLabel(t, 'frequency', choice)}
				</label>
			{/each}
		</fieldset>

		<fieldset class="sports">
			<legend>{t('register.sports.legend')}</legend>
			{#each values.sports as row, i}
				<div class="sport" role="group" aria-label="{t('register.sports.sport')} {i + 1}">
					<div class="field">
						<label for="sport-{i}-sport">{t('register.sports.sport')}</label>
						<input id="sport-{i}-sport" type="text" name="sport.{i}.sport" maxlength="80" bind:value={row.sport} />
					</div>
					<div class="field">
						<label for="sport-{i}-level">{t('register.sports.level')}</label>
						<select id="sport-{i}-level" name="sport.{i}.level" bind:value={row.level}>
							<option value="">{t('register.sports.none')}</option>
							{#each registration.choices.level as choice}
								<option value={choice.value}>{choiceLabel(t, 'level', choice)}</option>
							{/each}
						</select>
					</div>
					<div class="field">
						<label for="sport-{i}-practice">{t('register.sports.practice')}</label>
						<select id="sport-{i}-practice" name="sport.{i}.practice" bind:value={row.practice}>
							<option value="">{t('register.sports.none')}</option>
							{#each registration.choices.practice as choice}
								<option value={choice.value}>{choiceLabel(t, 'practice', choice)}</option>
							{/each}
						</select>
					</div>
					<div class="field short">
						<label for="sport-{i}-years">{t('register.sports.years')}</label>
						<input id="sport-{i}-years" type="number" name="sport.{i}.years" min="0" step="1" bind:value={row.years} />
					</div>
					<div class="field short">
						<label for="sport-{i}-months">{t('register.sports.months')}</label>
						<input id="sport-{i}-months" type="number" name="sport.{i}.months" min="0" max="11" step="1" bind:value={row.months} />
					</div>
					<div class="field wide">
						<label for="sport-{i}-notes">{t('register.sports.notes')}</label>
						<input id="sport-{i}-notes" type="text" name="sport.{i}.notes" maxlength="200" bind:value={row.notes} />
					</div>
					<button type="button" class="pill remove" on:click={() => removeSport(i)}>
						{t('register.sports.remove', { n: i + 1 })}
					</button>
				</div>
			{/each}
			<button type="button" class="pill" disabled={values.sports.length >= MAX_SPORTS} on:click={addSport}>
				{t('register.sports.add')}
			</button>
		</fieldset>

		<div class="field">
			<label for="team-wishes">{t('register.teamWishes')}</label>
			<p class="hint">{t('register.teamWishesHint')}</p>
			<textarea id="team-wishes" name="team_wishes" rows="3" maxlength="1000" bind:value={values.team_wishes}></textarea>
		</div>

		<div class="field">
			<label for="dietary">{t('register.dietary')} <span class="optional">({t('register.optional')})</span></label>
			<textarea id="dietary" name="dietary_restrictions" rows="2" maxlength="500" bind:value={values.dietary_restrictions}></textarea>
		</div>

		{#if registration.email.editable}
			<div class="field">
				<label for="register-email">{t('register.email')}</label>
				<p class="hint">{t('register.emailNeeded')}</p>
				<input id="register-email" type="email" name="email" autocomplete="email" required bind:value={values.email} />
			</div>
		{:else}
			<p class="email">
				<span class="label">{t('register.email')}</span>
				<span>{registration.email.value}</span>
				<a class="quiet-link" href="/account">{t('register.emailChange')}</a>
			</p>
		{/if}

		<label class="check">
			<input type="checkbox" name="attendance_confirmed" required bind:checked={values.attendance_confirmed} />
			{t('register.attendance')}
		</label>

		<p class="notes">{t('register.visibility')}</p>
		<p class="notes">{t('register.retention')}</p>

		{#if errorKeys.length > 0}
			<div class="error" id="register-errors" tabindex="-1" role="alert">
				{#each errorKeys as key}<p>{t(key)}</p>{/each}
			</div>
		{/if}

		<button class="submit">{registered ? t('register.submitEdit') : t('register.submit')}</button>
	</form>

	{#if registered}
		<form method="POST" action="?/withdraw" class="withdraw">
			<p class="notes">{t('register.withdrawNote')}</p>
			{#if withdrawResult?.error}
				<p class="error" id="register-errors" tabindex="-1" role="alert">{t(withdrawResult.error)}</p>
			{/if}
			<button class="pill">{t('register.withdraw')}</button>
		</form>
	{/if}
{/if}

<style>
	.registration {
		display: grid;
		gap: 1.25rem;
	}
	.intro,
	.notice {
		margin: 0 0 1rem;
	}
	.notice {
		padding: 0.75rem 1rem;
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		background: var(--bg-raised);
	}
	h2 {
		font-size: 1rem;
		font-family: var(--font-body);
		text-transform: none;
		letter-spacing: 0;
		margin: 0 0 0.75rem;
	}
	.field {
		display: grid;
		gap: 0.25rem;
		margin-bottom: 0.75rem;
	}
	.field label,
	legend {
		font-weight: 600;
	}
	.hint,
	.notes,
	.optional {
		color: var(--muted);
		font-size: 0.875rem;
		margin: 0;
	}
	input[type='number'],
	input[type='text'],
	input[type='email'],
	select,
	textarea {
		width: 100%;
		max-width: 28rem;
		padding: 0.5rem 0.625rem;
		background: var(--bg-sunken);
		color: var(--ink);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		font: inherit;
	}
	input[type='number'] {
		max-width: 6rem;
	}
	fieldset {
		border: 1px solid var(--line);
		border-radius: var(--radius);
		padding: 0.75rem 1rem;
		margin: 0;
	}
	.radio,
	.check {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		padding: 0.25rem 0;
	}
	.sport {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
		gap: 0.5rem 0.75rem;
		align-items: end;
		padding: 0.75rem 0;
		border-bottom: 1px solid var(--line);
	}
	.field.wide {
		grid-column: 1 / -1;
	}
	.field.short input {
		max-width: 5rem;
	}
	.error,
	.saved {
		margin: 0;
		padding: 0.5rem 0.75rem;
		border-radius: var(--radius);
	}
	.error {
		color: var(--loss);
		border: 1px solid var(--loss);
	}
	.saved {
		color: var(--win);
		border: 1px solid var(--win);
		margin-bottom: 1rem;
	}
	.submit,
	.pill {
		justify-self: start;
		padding: 0.625rem 1.25rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: transparent;
		color: var(--accent);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.submit {
		background: var(--accent);
		color: var(--bg);
	}
	.pill:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.summary dl {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.25rem 1rem;
		margin: 0;
	}
	.summary dt {
		color: var(--muted);
	}
	.summary dd {
		margin: 0;
	}
	.summary ul {
		margin: 0;
		padding-left: 1rem;
	}
	.withdraw {
		display: grid;
		gap: 0.5rem;
		margin-top: 2rem;
		padding-top: 1rem;
		border-top: 1px solid var(--line);
	}
	.email {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: baseline;
		margin: 0;
	}
</style>
```

Implement `routes/register/+page.svelte`:

```svelte
<script>
	import RegistrationForm from '$lib/components/RegistrationForm.svelte';
	import { useT } from '$lib/i18n';

	export let data;
	export let form;

	const t = useT();
</script>

<svelte:head>
	<title>{t('register.title', { year: data.registration.edition.year })}</title>
</svelte:head>

<div class="page">
	<h1>{t('register.title', { year: data.registration.edition.year })}</h1>
	<RegistrationForm registration={data.registration} {form} />
</div>

<style>
	.page {
		width: 100%;
		max-width: var(--page);
		margin: 0 auto;
		padding: 1.5rem 1rem 3rem;
	}
</style>
```

(Match the surrounding pages' `.page` wrapper and `h1` styling: read `routes/account/+page.svelte`'s `<style>` and reuse its rules for `.page` and `h1` rather than inventing them. The token names used in the two `<style>` blocks of this task (`--line`, `--line-strong`, `--bg-raised`, `--bg-sunken`, `--muted`, `--ink`, `--accent`, `--win`, `--loss`, `--radius`) are the repo's families, but check each against `routes/styles.css` and the account page's own rules and use the real name where one differs; colours are tokens only, `styles.test.js` forbids hard-coded ones.)

- [ ] **Step 5: Run the tests**

Run: `cd front && npx vitest run src/lib/components/RegistrationForm.test.js src/routes/register src/routes/styles.test.js`
Expected: `OK`. Mechanical fixes you may make (list each): accessible-name details of `getByRole` queries (labels with an `optional` span, the `group` roles), the French discipline names, `toHaveValue(6)` versus a string for number inputs.

- [ ] **Step 6: Commit**

```bash
git add front/src/lib/components/RegistrationForm.svelte front/src/lib/components/RegistrationForm.test.js front/src/routes/register/+page.svelte front/src/routes/register/page.test.js
git commit -m "[FEAT] the registration form: ratings, frequency, sports table, wishes, notices

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The hub's registration link

**Files:**
- Modify: `front/src/lib/components/EditionHub.svelte`, `front/src/routes/+page.svelte`, `front/src/routes/[year=year]/+page.svelte`, `front/src/routes/login/login.svelte`
- Test: `front/src/lib/components/EditionHub.test.js`, `front/src/routes/login/login.test.js`

The link needs no API call: `registrationLink` (Task 2) reads the layout data the hub already receives (`me.can_register`, the latest edition's public window), so neither hub gains a server load (a server load awaiting `parent()` would re-run the layout loads on every client-side visit, which this project avoids). The label is « Se connecter pour s'inscrire » for a visitor (through the login: registration is by invitation, so the label does not promise a signup, and the login page says so, Step 6) and « Inscription {year} » for someone logged in who can register; `/register` shows whether they are registered and offers the edit. Only the latest edition's hub carries it.

- [ ] **Step 1: Write the failing tests.** In `EditionHub.test.js` add inside `describe('EditionHub', ...)`:

```js
	describe('registration link', () => {
		// The latest edition (2026, starting 2026-09-19) with its public window set.
		const withWindow = [
			{ ...editions[0], start_date: '2026-09-19', registration_opens: '2026-01-01', registration_closes: null },
			...editions.slice(1)
		];
		const player = { id: 1, first_name: 'Léa', last_name: 'Martin', can_register: true };

		it('sends a visitor through the login while registration is open', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary, editions: withWindow, me: null });

			expect(screen.getByRole('link', { name: 'Log in to register' })).toHaveAttribute(
				'href', '/login?next=/register'
			);
		});

		it('links someone who can register straight to the form', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary, editions: withWindow, me: player });

			expect(screen.getByRole('link', { name: 'Registration 2026' })).toHaveAttribute('href', '/register');
		});

		it('shows nothing to someone who cannot register', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary, editions: withWindow, me: { ...player, can_register: false } });

			expect(screen.queryByRole('link', { name: /Regist/ })).toBeNull();
		});

		it('shows nothing once the window has closed, before it opens, or when it is not set', () => {
			vi.setSystemTime(new Date('2026-09-19T08:00:00Z')); // the day of the start: closed
			const closed = renderWith(EditionHub, { summary, editions: withWindow, me: null });
			expect(screen.queryByRole('link', { name: /Regist/ })).toBeNull();
			closed.unmount();

			vi.setSystemTime(new Date('2025-12-31T12:00:00Z'));
			const early = renderWith(EditionHub, { summary, editions: withWindow, me: null });
			expect(screen.queryByRole('link', { name: /Regist/ })).toBeNull();
			early.unmount();

			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			renderWith(EditionHub, { summary, editions, me: null }); // no registration_opens at all
			expect(screen.queryByRole('link', { name: /Regist/ })).toBeNull();
		});

		it('is only on the latest edition hub', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			const older = { ...summary, edition: { ...summary.edition, year: 2025 } };
			renderWith(EditionHub, { summary: older, editions: withWindow, me: null });

			expect(screen.queryByRole('link', { name: /Regist/ })).toBeNull();
		});

		it('says it in French', () => {
			vi.setSystemTime(new Date('2026-09-17T07:00:00Z'));
			const visitor = renderWith(EditionHub, { summary, editions: withWindow, me: null }, 'fr');
			expect(screen.getByRole('link', { name: "Se connecter pour s'inscrire" })).toBeInTheDocument();
			visitor.unmount();

			renderWith(EditionHub, { summary, editions: withWindow, me: player }, 'fr');
			expect(screen.getByRole('link', { name: 'Inscription 2026' })).toBeInTheDocument();
		});
	});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd front && npx vitest run src/lib/components/EditionHub.test.js`
Expected: the new tests fail (no `me` prop, no link).

- [ ] **Step 3: Implement.** In `EditionHub.svelte` add to the imports `import { parisToday, registrationLink } from '$lib/registration';`, a prop `export let me = null;` and, below the `phase` statements:

```js
	// The latest edition only: registration targets it (the API's latest_edition()).
	$: registration =
		editions[0]?.year === edition.year
			? registrationLink({ me, editions, today: parisToday(now) })
			: null;
```

In the `.actions` block put first:

```svelte
	{#if registration}
		<a class="register" href={registration.href}>
			{registration.visitor ? t('hub.register') : t('hub.registration', { year: registration.year })}
		</a>
	{/if}
```

Style `.actions a.register` as the filled main call, and make the other links `secondary` while it shows: change the Players link's `class:secondary={phase !== 'upcoming'}` to `class:secondary={phase !== 'upcoming' || registration}` and give the Ranking link the same `class:secondary={registration}`. Reuse the existing `.actions a` button rules rather than writing new colours (tokens only). Both hub pages pass `me`: `routes/+page.svelte` and `routes/[year=year]/+page.svelte` become `<EditionHub summary={data.summary} editions={data.editions} me={data.me} />`.

- [ ] **Step 4: Run**

Run: `cd front && npx vitest run src/lib/components/EditionHub.test.js src/routes`
Expected: `OK`. (A page test of the hubs that renders `EditionHub` through `+page.svelte` with data lacking `me` still works: `me` is `undefined`, a visitor.)

- [ ] **Step 5: The login page explains the invitation.** A newcomer who follows the visitor link lands on `/login?next=/register` with no account to log into. In `routes/login/login.test.js` (it renders `login.svelte` with `form` and `next` props: read how its other tests do) add:

```js
	it('explains that registration is by invitation when the login leads to /register', () => {
		renderWith(Login, { form: null, next: '/register' });

		expect(screen.getByText(/Registration is by invitation/)).toBeInTheDocument();
	});

	it('says nothing of it for any other destination, and words it in French', () => {
		const other = renderWith(Login, { form: null, next: '/account' });
		expect(screen.queryByText(/Registration is by invitation/)).toBeNull();
		other.unmount();

		renderWith(Login, { form: null, next: '/register' }, 'fr');
		expect(screen.getByText(/Les inscriptions se font sur invitation/)).toBeInTheDocument();
	});
```

(`Login` and `screen` are whatever that file already imports.) In `routes/login/login.svelte`, inside the `<form>` before the username input add `{#if next === '/register'}<p class="note">{t('login.registerNote')}</p>{/if}` and style `.note` like the form's other quiet text (tokens only: `color: var(--muted)`, a small font size and a margin below). The paths compared are the ones the hub link and `/register`'s own redirect write, `/register` exactly.

- [ ] **Step 6: Run the login tests**

Run: `cd front && npx vitest run src/routes/login`
Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add front/src/lib/components/EditionHub.svelte front/src/lib/components/EditionHub.test.js front/src/routes/+page.svelte "front/src/routes/[year=year]/+page.svelte" front/src/routes/login/login.svelte front/src/routes/login/login.test.js
git commit -m "[FEAT] hub: registration link from the layout data; the login explains the invitation

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The account page for invited newcomers

**Files:**
- Modify: `front/src/routes/account/+page.server.js`, `front/src/routes/account/+page.svelte`
- Test: `front/src/routes/account/page.server.test.js`, `front/src/routes/account/page.test.js`

An invited newcomer (`can_register`, not a person) has no profile (`/profile/<id>/` answers 404), so the page loses its photo and showcase sections and its profile breadcrumb, keeps the email, password and session sections, and (for everyone who can register, while the window is open) gains a registration link taken from the layout data, as the hub's is.

- [ ] **Step 1: Write the failing server tests.** In `account/page.server.test.js` add these inside the existing `describe('account load', ...)` (the file's `me` is a person; derive the invitee from it):

```js
	const invitee = { ...me, is_person: false, can_register: true };
	const registrationBody = { edition: { year: 2027 }, state: { is_open: true, reason: '' }, registration: null };

	it('serves an invited newcomer without asking for a profile they do not have', async () => {
		const fetch = vi.fn(async (url) => {
			if (url === 'http://api/me/') return json(200, invitee);
			if (url === 'http://api/registration/') return json(200, registrationBody);
			throw new Error(`unexpected ${url}`);
		});

		const data = await load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() });

		expect(data.profile).toBeNull();
		expect(data.account).toMatchObject({ id: 34, is_person: false });
		expect(fetch.mock.calls.some(([url]) => url.includes('/profile/'))).toBe(false);
	});

	it('still sends someone who cannot register home', async () => {
		const fetch = vi.fn(async () => json(200, { ...me, is_person: false, can_register: false }));

		await expect(load({ fetch, cookies: cookiesWith(), setHeaders: vi.fn() })).rejects.toMatchObject({
			status: 303, location: '/'
		});
	});
```

Update the existing tests: the person's `account` now also carries `is_person: true` (extend the expected objects). The load makes no registration call.

- [ ] **Step 2: Implement the load.** In `account/+page.server.js`:

Replace the person check and the return of `load`:

```js
	// An invited newcomer (no active player yet) has no profile page but may use the rest.
	const canRegister = account.can_register ?? account.is_person;
	if (!canRegister) redirect(303, '/');
	const isPerson = account.is_person === true;
	const profile = isPerson ? await apiGet(fetch, api(`/profile/${account.id}/`)) : null;
	return {
		account: {
			id: account.id,
			username: account.username,
			email: account.email ?? '',
			is_staff: account.is_staff === true,
			is_person: isPerson
		},
		profile
	};
```

and update the doc comment (« …an invited newcomer is served too, without a profile »).

- [ ] **Step 3: Write the failing page tests.** In `account/page.test.js` add:

```js
	describe('for an invited newcomer', () => {
		const invitee = {
			account: { id: 41, username: 'newbie', email: 'n@mail.example', is_staff: false, is_person: false },
			profile: null,
			registration: null,
			me: { id: 41, first_name: 'Nina', last_name: 'Neuf', photo: null, is_person: false, can_register: true, photo_locked: false }
		};

		it('shows the email, password and session sections but no photo or showcase', () => {
			renderWith(Page, { data: invitee, form: null });

			expect(screen.getByRole('heading', { level: 1, name: 'My account' })).toBeInTheDocument();
			for (const name of ['Email address', 'Password', 'Session']) {
				expect(screen.getByRole('heading', { level: 2, name })).toBeInTheDocument();
			}
			expect(screen.queryByRole('heading', { level: 2, name: 'Photo' })).toBeNull();
			expect(screen.queryByRole('heading', { level: 2, name: 'Badge showcase' })).toBeNull();
		});

		it('has no profile crumb to link to', () => {
			renderWith(Page, { data: invitee, form: null });

			const breadcrumb = screen.getByRole('navigation', { name: 'Breadcrumb' });
			expect(within(breadcrumb).getByRole('link', { name: 'Players' })).toBeInTheDocument();
			expect(within(breadcrumb).queryByRole('link', { name: /Nina/ })).toBeNull();
		});
	});

	describe('the registration link', () => {
		const open = {
			...data,
			me: { ...data.me, can_register: true },
			latestYear: 2027,
			editions: [{ year: 2027, start_date: '2027-09-18', registration_opens: '2027-01-01', registration_closes: null }]
		};

		beforeEach(() => vi.useFakeTimers());
		afterEach(() => vi.useRealTimers());

		it('links the registration while it is open', () => {
			vi.setSystemTime(new Date('2027-06-01T10:00:00Z'));
			renderWith(Page, { data: open, form: null });

			expect(within(section('Registration')).getByRole('link', { name: 'Registration 2027' })).toHaveAttribute('href', '/register');
		});

		it('shows no section once it is closed, for someone who cannot register, or without a window', () => {
			vi.setSystemTime(new Date('2027-09-18T10:00:00Z'));
			const closed = renderWith(Page, { data: open, form: null });
			expect(screen.queryByRole('heading', { level: 2, name: 'Registration' })).toBeNull();
			closed.unmount();

			vi.setSystemTime(new Date('2027-06-01T10:00:00Z'));
			const cannot = renderWith(Page, { data: { ...open, me: { ...open.me, can_register: false } }, form: null });
			expect(screen.queryByRole('heading', { level: 2, name: 'Registration' })).toBeNull();
			cannot.unmount();

			renderWith(Page, { data: { ...open, editions: [] }, form: null });
			expect(screen.queryByRole('heading', { level: 2, name: 'Registration' })).toBeNull();
		});

		it('words it in French', () => {
			vi.setSystemTime(new Date('2027-06-01T10:00:00Z'));
			renderWith(Page, { data: open, form: null }, 'fr');

			expect(screen.getByRole('heading', { level: 2, name: 'Inscription' })).toBeInTheDocument();
			expect(screen.getByRole('link', { name: 'Inscription 2027' })).toBeInTheDocument();
		});
	});
```

- [ ] **Step 4: Implement the page.** In `account/+page.svelte` (import `registrationLink` and `parisToday` from `$lib/registration`; the test file needs `beforeEach`, `afterEach` and `vi` from `vitest`):
  - `$: profile = data.profile;`, `$: name = profile ? fullName(profile) : '';`, `$: collection = profile ? badgeCollection(profile.badges ?? []) : null;`.
  - Breadcrumb: `items={profile ? [{ label: t('players.title'), href: '/players' }, { label: name, href: `/players/${profile.id}` }, { label: t('account.title') }] : [{ label: t('players.title'), href: '/players' }, { label: t('account.title') }]}`.
  - Wrap the photo and showcase `<section>`s in `{#if profile}` … `{/if}`.
  - In the script add `$: registration = registrationLink({ me: data.me, editions: data.editions ?? [], today: parisToday() });` (the page's `data` carries the layout's `me` and `editions`).
  - After the username line add:

```svelte
	{#if registration}
		<section aria-labelledby="account-registration">
			<h2 id="account-registration">{t('account.section.registration')}</h2>
			<a class="pill" href={registration.href}>{t('account.registrationLink', { year: registration.year })}</a>
		</section>
	{/if}
```

  (reuse the `.pill` class the page already styles for its buttons; if it is styled as a `button` only, give it `a.pill` the same rules).

- [ ] **Step 5: Run**

Run: `cd front && npx vitest run src/routes/account`
Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add front/src/routes/account
git commit -m "[FEAT] account page for invited newcomers and a registration section

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The claim lands on `/register` for an invited newcomer

**Files:**
- Modify: `front/src/lib/server/password-link.js`, `front/src/routes/claim/[uid]/[token]/+page.server.js`
- Test: `front/src/lib/server/password-link.test.js`, `front/src/routes/claim/[uid]/[token]/page.server.test.js`

The claim endpoint answers `{token, user_id}` and cannot say whether the person has a profile; the front asks `/me/` with the fresh token.

- [ ] **Step 1: Write the failing tests.** In `claim/[uid]/[token]/page.server.test.js` (read its existing helpers first: `json`, a `cookies` double, how it posts the `claim` action) add:

```js
	it('lands a person on their profile', async () => {
		const fetch = vi.fn(async (url) =>
			url.endsWith('/me/') ? json(200, { id: 7, is_person: true, can_register: true }) : json(200, { token: 'fresh', user_id: 7 })
		);

		await expect(runClaim({ fetch })).rejects.toMatchObject({ status: 303, location: '/players/7' });
		expect(fetch.mock.calls.find(([url]) => url.endsWith('/me/'))[1].headers).toEqual({ authorization: 'Token fresh' });
	});

	it('lands an invited newcomer, who has no profile yet, on the registration', async () => {
		const fetch = vi.fn(async (url) =>
			url.endsWith('/me/') ? json(200, { id: 7, is_person: false, can_register: true }) : json(200, { token: 'fresh', user_id: 7 })
		);

		await expect(runClaim({ fetch })).rejects.toMatchObject({ status: 303, location: '/register' });
	});

	it('falls back to the profile when /me/ cannot be read', async () => {
		const fetch = vi.fn(async (url) =>
			url.endsWith('/me/') ? json(500, { detail: 'boom' }) : json(200, { token: 'fresh', user_id: 7 })
		);

		await expect(runClaim({ fetch })).rejects.toMatchObject({ status: 303, location: '/players/7' });
	});
```

(The file's helper is `claim({ response, fields, getClientAddress, linkParams })`: it builds one `fetch` answering the SAME canned `response` to every call, which cannot serve the claim POST and then `/me/`. Extend it with an optional `fetch` parameter (`claim({ fetch })` uses it instead of the canned one) and use that in the three new tests; existing tests keep working through the try/catch fallback, but any that asserts `fetch` was called once must be updated to expect the extra `/me/` call (add, never loosen). Rename `runClaim` in the snippets above to this helper.) In `password-link.test.js`, add a test that `linkAction` awaits an async `landing` and hands it the body and `{ fetch, token }`:

```js
	it('awaits an async landing and gives it the answer, the fetch and the new token', async () => {
		const landing = vi.fn(async (body, context) => `/after/${body.user_id}/${context.token}`);
		const action = linkAction(() => '/claim/u/t/', landing);
		// ... post a valid pair as the file's other linkAction tests do, with fetch answering { token: 'fresh', user_id: 9 } ...
		await expect(action(event)).rejects.toMatchObject({ status: 303, location: '/after/9/fresh' });
		expect(landing.mock.calls[0][1].fetch).toBe(event.fetch);
	});
```

(Build `event` exactly as the existing `linkAction` tests in that file do.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd front && npx vitest run src/lib/server/password-link.test.js "src/routes/claim"`
Expected: the new tests fail (the landing is sync, no `/me/` call).

- [ ] **Step 3: Implement.** In `password-link.js`, `linkAction`'s last lines become:

```js
		const { token } = body ?? {};
		if (typeof token !== 'string' || token === '') return fail(502, { error: 'claim.error.failed' });
		cookies.set(TOKEN_COOKIE, token, tokenCookieOptions());
		// A 303 so the browser follows with a GET, and a full page load (the form is a plain
		// POST) so the root layout reads the new cookie and the header shows the account.
		// `landing` may be async: it gets the API's answer and what it needs to ask more.
		redirect(303, await landing(body, { fetch, token }));
```

and update its doc comment (« then a 303 to `await landing(body, { fetch, token })` »). In `claim/[uid]/[token]/+page.server.js`:

```js
import { apiGet } from '$lib/api';
import { linkAction, linkLoad, linkPath } from '$lib/server/password-link';
import { api } from '$lib/server/urls';

/** The API path of the claim link, or null for a link not shaped like one. */
const claimPath = linkPath('/claim');

export const load = linkLoad(claimPath);

export const actions = {
	/**
	 * Set the chosen password and log the person in. A person lands on their profile, an
	 * invited newcomer (no profile yet) on the registration, found by asking /me/ with the
	 * fresh token; if that fails, the profile when the API named the person, else home.
	 */
	claim: linkAction(claimPath, async ({ user_id }, { fetch, token }) => {
		const profile = Number.isInteger(user_id) && user_id > 0 ? `/players/${user_id}` : '/';
		try {
			const me = await apiGet(fetch, api('/me/'), token);
			if (me?.is_person !== true && me?.can_register === true) return '/register';
		} catch {
			// Unreadable: land as before.
		}
		return profile;
	})
};
```

- [ ] **Step 4: Run**

Run: `cd front && npx vitest run src/lib/server src/routes/claim src/routes/reset`
Expected: `OK` (the reset page's `linkAction` landing is synchronous and still works with `await`).

- [ ] **Step 5: Commit**

```bash
git add front/src/lib/server/password-link.js front/src/lib/server/password-link.test.js front/src/routes/claim
git commit -m "[FEAT] a claim lands an invited newcomer on the registration

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Documentation and final verification

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Document slice 3.** In `CLAUDE.md`, in the paragraph beginning `**In-app registration**` replace `Not built yet (slice 3): ...` (end of the « Registration questionnaire » paragraph) with `Slice 3 built the pages (see the front paragraph on registration).` and add, after the « Player accounts on the front » paragraph, a paragraph:

```markdown
**Registration on the front** (spec `2026-10-04-in-app-registration-design.md`, slice 3, plan `2026-10-05-registration-ui.md`): the root layout's `me` carries `can_register` (a person or an invited newcomer; a server without it reads as false) and `editions` keep `start_date`, `registration_opens` and `registration_closes` for a visitor's call to action. `Header` links `/register` (`nav.register`) for anyone who can register and links `/account` for an invited newcomer too. `/register` (`routes/register`, no tab bar) is the caller's own form: its load sends a visitor or dead token to `/login?next=/register`, someone who cannot register home (the API's 404 `not_a_person`) and lets any other failure reach the error page, `private, no-store`; the `save` and `withdraw` actions are plain POSTs (the page reloads with the saved answers) that map the API's codes to `register.error.*` (`errors` list of keys, or one `error` key from a status or an `{error}` code such as `closed`, `removed_by_organiser`, `has_team`) and return the form model as typed (`values`) so a refusal keeps what was written. `$lib/registration.js` is the pure core (`initialValues`: posted over saved over suggested over blank; `valuesFromForm`: the hidden `skill` fields, `rating.<id>`, `sport.<i>.<field>` rows with blank ones dropped; `bodyFromValues`: a blank rating is left out and a bad value passed on for the API to refuse; `errorKeys`; `registrationLink`, `visitorCta` and `parisToday`), `RegistrationForm.svelte` renders it (ratings 1 to 10, the global question built from the edition's disciplines, five frequency radios, a sports table with add and remove rows up to 15 and years plus months, wishes, dietary restrictions, the email read-only with a link to `/account` or an editable required field, the required presence tick, the visibility and retention notices, and the notices for a closed, not yet open, late-pass, withdrawn and organiser-removed registration; a registered player sees their saved answers read-only once it is closed). The hub and `/account` link the registration with no API call and no server load, from the layout data: `registrationLink` (`$lib/registration.js`) reads `me.can_register` and the latest edition's public window (`visitorCta`: `registration_opens` reached, `registration_closes` or the day before `start_date` not passed, Paris dates), giving a visitor « Se connecter pour s'inscrire » through `/login?next=/register` (the login page then says registration is by invitation) and someone who can register « Inscription {year} » to `/register`, which shows whether they are registered and offers the edit; `EditionHub` takes `me` and shows it on the latest edition's hub only. The account page of an invited newcomer has no photo, showcase or profile crumb (`/profile/<id>/` would 404) but keeps the registration link. A claim lands a person on their profile and an invited newcomer on `/register`: `linkAction` awaits its `landing(body, {fetch, token})`, and the claim page asks `/me/` with the fresh token. The strings are `register.*`, `nav.register`, `hub.register`, `hub.registration`, `login.registerNote` and `account.registrationLink` in both dictionaries, worded « vous ».
```

- [ ] **Step 2: Run every check CI runs**

```bash
cd front && npm test && npm run build
```

Expected: every Vitest file passes; the build succeeds. (`npm run build` may need `front/.env`; if it cannot run for environment reasons say so, never create or commit an env file.)

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "[DOCS] document the registration pages

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Hand over.** Report the branch (`feat/registration-ui`), the test and build results, that Task 10 (the smoke test on the dev stack) runs after the merge into `dev`, and the deploy note: the front needs the slice 2 API (`/registration/`, `can_register` on `/me/`), so deploy the server before the front; against an old server nothing shows (no `can_register`, so no registration link and no call to action). Do not open the PR or touch `dev` unasked.

---

### Task 10: Smoke test on the dev stack (after the merge into `dev`)

**Run by the controller, never by a subagent.** Hugo approved this on 2026-10-05, including applying the registration migrations to the dev database and creating, then removing, throwaway rows in it. Anything it finds is fixed on `dev` afterwards, as follow-up commits with a test each (« we merge on `dev`, run the tests and apply the fixes there »). Why it exists: every test of the three slices mocks the other half; this is the one time the real server and the real pages meet.

**Rules.** Every throwaway row is named `smoke…`. Existing editions, players and users are not touched. The seed and the cleanup are the only writes. Passwords and claim links are printed to the terminal only, never written to a file or the repo.

- [ ] **Step 1: Update `dev` and back up the dev database**

```bash
git switch dev && git pull
docker compose exec -T db pg_dump -U "$(docker compose exec -T db printenv POSTGRES_USER | tr -d '\r')" "$(docker compose exec -T db printenv POSTGRES_DB | tr -d '\r')" | gzip > "$SCRATCH/dev-before-smoke.sql.gz"
```

(`$SCRATCH` is the session scratchpad. If the compose file names the database or user differently, read them from `docker-compose.yml`.)

- [ ] **Step 2: Migrate** (`0041` to `0043` are not applied to the dev database yet)

```bash
docker compose exec -T server python manage.py migrate --plan
docker compose exec -T server python manage.py migrate
```

Expected: the plan lists only `0041_registration_foundations`, `0042_seed_registration_skills`, `0043_registration_window` (and any later migration of `dev`); migrate finishes `OK`. Note the counts to restore: `Edition.objects.count()`, `User.objects.count()`.

- [ ] **Step 3: Seed the throwaway data** with one `manage.py shell` script (printing the passwords and the claim link): a past edition 2028 with a `Player` for `smoke-returning` (frequency `hour`, one `PlayerSport`), the registration edition 2029 (`start_date` 2029-09-15, `registration_opens` yesterday, FR and EN intro and skills month, three `RegistrationSkill`s, a `Relay` discipline), the users `smoke-returning` (a real-looking `@example.test` email, a known password), `smoke-invited` (`UserProfile.invited=True`, an `@example.test` email, no usable password, a `claims.claim_link`) and `smoke-plain` (neither). Dev's `PUBLIC_URL` is `http://localhost:5173`.

- [ ] **Step 4: Walk the flows in the built-in browser** (front on `http://localhost:5173`, API on `:3003`), at desktop width and again at 375px, in French and in English, noting each result:
  1. As a visitor the hub shows « Se connecter pour s'inscrire »; it leads to `/login?next=/register`, which explains the invitation; after the real login it lands on `/register`.
  2. The invited claim link: set a password; it lands on `/register` (not a 404 profile), the header shows the account and register links, `/account` has no photo or showcase section.
  3. `/register`: native validation on an empty submit; a bad rating (11) and an unticked confirmation give the refusal list and keep what was typed; a valid save shows « Inscription enregistrée ».
  4. `smoke-returning`: the « Repris de votre inscription 2028 » banner and the prefilled sports; add and remove rows, the 16th is refused; save; the hub says « Inscription 2029 ».
  5. Email: give `smoke-returning` a `@olympicwarriors.com` address in the shell, reload: the form asks for one; an address already used by another account is refused (`email_taken`).
  6. Withdraw (no team) shows the withdrawn banner and keeps the answers; registering again restores them. Put the player in a team in the shell: withdraw is refused (`has_team`).
  7. Set `registration_closes` to yesterday: the closed notice and the read-only summary replace the form; grant a late pass in the admin (« Autoriser l'inscription tardive »): the form is back; deactivate the player in the admin (an organiser removal): the removal notice.
  8. The admin pages of slice 2 render: the Edition page (window, status), the invite page (paste the three seed names plus one new line, check the conflict and the link messages), the profile list (`invited` column).
  Also confirm: the dev servers log no errors (`docker compose logs --tail 200 server front`).

- [ ] **Step 5: Record and fix.** List every defect with its flow. Fix each on `dev` with a failing test first, commit, and re-walk the flow.

- [ ] **Step 6: Clean up** in one `manage.py shell` script: delete the three `smoke-*` users and editions 2028 and 2029 (the cascade removes their players, ratings, sports, skills, passes and invited profiles), then check `Edition.objects.count()` and `User.objects.count()` equal the Step 2 counts and that no `smoke` row remains. Keep the dump from Step 1 until Hugo confirms.

---

## Self-review (spec coverage for slice 3)

| Spec requirement | Task |
|---|---|
| `/register` page, login-gated, with `/login?next=/register` | 4, 5 |
| Stepper per skill 1-10, the generated global-level question, frequency, sports table, wishes, dietary, email read-only or editable, required tick | 5 |
| Visibility and retention notices; « Repris de votre inscription » for suggested answers | 3, 5 |
| Closed, not-yet-open, not-configured, late-pass, withdrawn, organiser-removed states | 5 |
| Saved registration shows « Enregistré » with edit and withdraw (`has_team` refusal worded) | 4, 5 |
| Header link for anyone who can register, even outside the window | 1 |
| Hub call to action (and `/account`), a visitor via the login; no hub load calls `/registration/` (the link comes from the layout data) | 6, 7 |
| Invited newcomer: claim lands on `/register`, `/account` open without photo and showcase, header links the name to `/account` | 1, 7, 8 |
| `register.*` strings in both dictionaries with the parity test; one French test per surface | 3 and each task |
| `NO_TAB_BAR` | 4 |
| `CLAUDE.md` | 9 |
| Real server and real pages meet once before release | 10 (a manual smoke test on `dev`) |

Deliberate choices not in the spec text (decided with Hugo on 2026-10-05): a visitor's link reads « Se connecter pour s'inscrire » and the login page explains that registration is by invitation (no signup exists); the hub and account links come from the layout data, so they cannot say whether the player is already registered (« Inscription {year} » for everyone logged in who can register; `/register` shows and edits the state) and no hub gains a server load; once registration is closed a registered player reads their saved answers in a read-only summary; the form is worded « vous » like the rest of the site; the claim asks `/me/` rather than the claim endpoint growing a field.

Names used across tasks: `registrationLink`, `visitorCta`, `parisToday`, `initialValues`, `valuesFromForm`, `bodyFromValues`, `errorKeys`, `choiceLabel`, `listNames`, `emptySport`, `MAX_SPORTS` (Task 2, used by 5 and 6); `registrationPayload`, `savedAnswers` fixtures (Task 2, used by 4, 5); `registrationLink`'s `{href, year, visitor}` (Task 2, used by 6 and 7); the keys `register.*`, `nav.register`, `hub.register`, `hub.registration`, `account.registrationLink` (Task 3, used by 1, 5, 6, 7).
