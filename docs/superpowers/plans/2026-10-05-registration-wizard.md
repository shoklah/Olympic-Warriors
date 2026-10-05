# Registration Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the registration form into a three-step wizard with 1–10 sliders and two team-preference fields (`team_with`, `team_avoid`).

**Architecture:** Two PRs, server first. The server adds two private `Player` text fields (legacy `team_wishes` stays, relabelled) and swaps them into the `PUT /registration/` contract and every privacy list. The front keeps one plain-POST `<form>` holding three panels, shows one at a time with client-side step state, validates forward navigation natively, and starts on the step of the first refusal.

**Tech Stack:** Django 4.2 / DRF / PostgreSQL; SvelteKit 2 / Svelte 4 (plain JS, tabs), Vitest + @testing-library/svelte.

Spec: `docs/superpowers/specs/2026-10-05-registration-wizard-design.md`.

**Rules for every implementer** (from CLAUDE.md and past slices):
- Never write to the dev database from a script or `manage.py shell`. Tests only (`docker compose exec server python manage.py test ...` use the test DB).
- Server tests run in Docker; front tests with `cd front && npm test -- <file>`.
- Run each new test red before the code that makes it green.
- Commit per task, on the PR's branch (server: `feat/registration-team-fields` from `dev`; front: `feat/registration-wizard` from `dev` once the server PR is merged, or stacked on the server branch).
- Svelte 4: keep the `loadedFrom` identity-check pattern in `RegistrationForm.svelte` (a `bind:value` inside an `{#each registration.skills}` marks `registration` dirty on every edit).

---

# PR 1 — Server

## File structure

- `server/olympic_warriors/models/Player.py` — two new fields, legacy relabel.
- `server/olympic_warriors/migrations/0044_player_team_with_avoid.py` — generated.
- `server/olympic_warriors/enrolment.py` — validate / save / answers carry the two fields; `MAX_TEAM = 500`.
- `server/olympic_warriors/accounts.py`, `transfer.py`, `admin.py` — privacy lists, admin columns and search.
- Tests: `test_enrolment.py`, `test_registration_api.py`, `test_registration_models.py`, `test_registration_admin.py`, `test_deactivate_private_answers.py`, `test_transfer.py`, `test_showcase.py`.

### Task 1: Model fields and migration

**Files:**
- Modify: `server/olympic_warriors/models/Player.py:40`
- Create: `server/olympic_warriors/migrations/0044_player_team_with_avoid.py` (generated)
- Test: `server/olympic_warriors/tests/test_registration_models.py`

- [ ] **Step 1: Write the failing test** — append to the registration model test class that holds the line-33 `team_wishes` default assertion (read the file, use its helpers):

```python
    def test_the_two_team_preferences_default_to_blank_and_are_capped(self):
        player = Player.objects.create(user=self.user, edition=self.edition, rating=5)
        self.assertEqual((player.team_with, player.team_avoid), ("", ""))

        player.team_with = "x" * 501
        with self.assertRaises(ValidationError):
            player.full_clean(exclude=["user", "edition", "team"])
        player.team_with = "x" * 500
        player.team_avoid = "y" * 501
        with self.assertRaises(ValidationError):
            player.full_clean(exclude=["user", "edition", "team"])
```

If the class names the user/edition differently (`self.ana`, `self.edition`...), use its names; import `ValidationError` from `django.core.exceptions` if absent.

- [ ] **Step 2: Run it red**

Run: `docker compose exec server python manage.py test olympic_warriors.tests.test_registration_models`
Expected: FAIL (`AttributeError`/`TypeError`: no `team_with`).

- [ ] **Step 3: Implement** — in `Player.py` replace the `team_wishes` line:

```python
    team_wishes = models.TextField(
        "Souhaits d'équipe (ancien format)",
        blank=True, default="", validators=[MaxLengthValidator(1000)],
        help_text="Combined free text of the CSV registration (up to 2026). The form no longer writes it.",
    )
    team_with = models.TextField(
        "Souhaite être avec", blank=True, default="", validators=[MaxLengthValidator(500)]
    )
    team_avoid = models.TextField(
        "Préfère éviter", blank=True, default="", validators=[MaxLengthValidator(500)]
    )
```

Then `docker compose exec server python manage.py makemigrations olympic_warriors -n player_team_with_avoid` and check the file is `0044_...` with `AddField` x2 and `AlterField` for `team_wishes`.

- [ ] **Step 4: Run green**, then `docker compose exec server python manage.py makemigrations --check --dry-run` (expect "No changes detected").

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/models/Player.py server/olympic_warriors/migrations/0044_player_team_with_avoid.py server/olympic_warriors/tests/test_registration_models.py
git commit -m "[FEAT] Player: team_with and team_avoid, team_wishes relabelled as legacy"
```

### Task 2: Enrolment validation, save and answers

**Files:**
- Modify: `server/olympic_warriors/enrolment.py` (lines ~24, 106, 137, 193, 285)
- Test: `server/olympic_warriors/tests/test_enrolment.py`

- [ ] **Step 1: Update the tests first.** In `test_enrolment.py`:
  - `good()`: replace `"team_wishes": "Avec Bob",` with `"team_with": "Avec Bob", "team_avoid": "Pas Carl",`.
  - `test_a_good_answer_is_cleaned`: `good(team_with="  Avec Bob \n", team_avoid=" Pas Carl ")`; assert `cleaned["team_with"] == "Avec Bob"` and `cleaned["team_avoid"] == "Pas Carl"` (drop the `team_wishes` assert).
  - `test_optional_parts_may_be_absent`: loop over `("sports", "team_with", "team_avoid", "dietary_restrictions")`; assert `(cleaned["team_with"], cleaned["team_avoid"], cleaned["dietary_restrictions"]) == ("", "", "")`.
  - `test_texts`:

```python
    def test_texts(self):
        for key in ("team_with", "team_avoid"):
            with self.subTest(key=key):
                self.assertEqual(self.codes(good(**{key: "x" * 501})), ["too_long"])
                self.assertEqual(self.codes(good(**{key: 5})), ["invalid_text"])
                validate(good(**{key: "x" * 500}), self.skills, False)
        self.assertEqual(self.codes(good(dietary_restrictions="x" * 501)), ["too_long"])
        validate(good(dietary_restrictions="x" * 500), self.skills, False)

    def test_a_body_that_still_sends_the_legacy_wishes_has_them_ignored(self):
        cleaned = validate(good(team_wishes="Avec Bob"), self.skills, False)

        self.assertNotIn("team_wishes", cleaned)
```

  - NUL test: loop `("team_with", "team_avoid", "dietary_restrictions")` with `"a\x00b"` → `["invalid_text"]`.
  - Lines ~209 and ~274: `player.team_with == "Avec Bob"` and `player.team_avoid == "Pas Carl"` (the withdraw test keeps both).
  - Line ~410 (answers payload): assert `answers["team_with"] == "Avec Bob"`, `answers["team_avoid"] == "Pas Carl"`, `assertNotIn("team_wishes", answers)`.
  - Lines ~424/428 (suggestions fixture): `team_wishes="x"` → `team_with="x"`, `team_wishes="Avec Bob"` → `team_with="Avec Bob", team_avoid="Pas Carl"`; the existing assertion that `suggested` carries no wishes must also assert neither `team_with` nor `team_avoid` is a key of `suggested`.
  - Add a save test: a re-registration leaves the legacy column alone.

```python
    def test_a_save_never_touches_the_legacy_wishes(self):
        Player.objects.create(user=self.ana, edition=self.edition, rating=5, team_wishes="Ancien texte")

        player = self.save()

        player.refresh_from_db()
        self.assertEqual(player.team_wishes, "Ancien texte")
```

- [ ] **Step 2: Run red**: `docker compose exec server python manage.py test olympic_warriors.tests.test_enrolment` → FAIL (KeyError `team_with`, etc.).

- [ ] **Step 3: Implement.** `enrolment.py`:
  - Next to `MAX_WISHES = 1000` add `MAX_TEAM = 500` and delete `MAX_WISHES` if unused afterwards (`git grep MAX_WISHES`).
  - Line ~106: replace by

```python
    team_with = _text(data, "team_with", MAX_TEAM, fail)
    team_avoid = _text(data, "team_avoid", MAX_TEAM, fail)
```

  - Cleaned dict: replace `"team_wishes": wishes,` with `"team_with": team_with, "team_avoid": team_avoid,`.
  - `save` fields dict: replace `"team_wishes": cleaned["team_wishes"],` with `"team_with": cleaned["team_with"], "team_avoid": cleaned["team_avoid"],`.
  - `_answers`: replace `"team_wishes": player.team_wishes,` with `"team_with": player.team_with, "team_avoid": player.team_avoid,`.

- [ ] **Step 4: Run green** (same command) → PASS.

- [ ] **Step 5: Commit** `[FEAT] registration: team_with and team_avoid replace team_wishes in the API contract`.

### Task 3: API tests and privacy lists

**Files:**
- Modify: `accounts.py:73`, `transfer.py:68`, `tests/test_registration_api.py`, `tests/test_showcase.py:31`, `tests/test_deactivate_private_answers.py`, `tests/test_transfer.py`

- [ ] **Step 1: Update tests (red).**
  - `test_registration_api.py`: line ~34 `answer()` fixture → `"team_with": "Avec Bob", "team_avoid": "Pas Carl"`; line ~164 `self.put(team_with="Plutôt seule")` and assert `(player.team, player.team_with) == (team, "Plutôt seule")`; line ~276 `body["registration"]["team_with"] == "Avec Bob"` and `["team_avoid"] == "Pas Carl"`.
  - `test_registration_models.py` ~line 93 (privacy-walk fixture): add `team_with="Avec Bob", team_avoid="Pas Carl"` beside `team_wishes`.
  - `test_showcase.py` `PRIVATE_KEYS`: add `"team_with", "team_avoid"`.
  - `test_deactivate_private_answers.py`: `self.answers` gains `team_with="Avec Bob", team_avoid="Pas Carl"` (keep `team_wishes`); assert both new fields `== ""` after deactivate.
  - `test_transfer.py` `Player` fixture (~line 68) gains the two fields; the privacy loop (~128) lists `"team_with", "team_avoid"` too.
  - `test_registration_admin.py` `TestTeamPageRoster`: add `team_with="Avec Bob", team_avoid="Pas Carl"` to the player, add both names to the private-field loop, and `assertNotContains(response, "Pas Carl")`.

- [ ] **Step 2: Run red**: `docker compose exec server python manage.py test olympic_warriors.tests.test_registration_api olympic_warriors.tests.test_showcase olympic_warriors.tests.test_deactivate_private_answers olympic_warriors.tests.test_transfer olympic_warriors.tests.test_registration_admin olympic_warriors.tests.test_registration_models` → failures on the new keys (privacy walk, export, clearing, roster inline).

- [ ] **Step 3: Implement.**
  - `accounts.py:73`: after `team_wishes="",` add `team_with="", team_avoid="",`.
  - `transfer.py:68`: `{"dietary_restrictions", "sport_frequency", "team_wishes", "team_with", "team_avoid", "attendance_confirmed"}`.
  - `admin.py` `PlayerInline.exclude`: add `"team_with", "team_avoid"` after `"team_wishes"`.

- [ ] **Step 4: Run green** (same command) → PASS.

- [ ] **Step 5: Commit** `[FEAT] team preferences are private: export, deactivation, roster inline, public walk`.

### Task 4: Player admin columns and search

**Files:**
- Modify: `server/olympic_warriors/admin.py` (`PlayerAdmin`, ~354–395)
- Test: `server/olympic_warriors/tests/test_registration_admin.py`

- [ ] **Step 1: Failing test** — in `TestPlayerAdminRegistration` (setUp has `self.vegan` Ana and `self.plain` Bob):

```python
    def test_the_team_preferences_are_columns_and_searchable(self):
        Player.objects.filter(pk=self.vegan.pk).update(
            team_with="Avec Léa et " + "x" * 80, team_avoid="Pas Carl"
        )

        listing = self.client.get(PLAYERS, {"is_active__exact": "1"})
        by_with = self.client.get(PLAYERS, {"q": "Léa", "is_active__exact": "1"})
        by_avoid = self.client.get(PLAYERS, {"q": "Carl", "is_active__exact": "1"})
        nobody = self.client.get(PLAYERS, {"q": "Zoé", "is_active__exact": "1"})

        self.assertContains(listing, "Pas Carl")
        self.assertContains(listing, "Avec Léa et")
        self.assertNotContains(listing, "x" * 80)  # truncated in the list
        self.assertEqual(self.names(by_with), {"Ana "})
        self.assertEqual(self.names(by_avoid), {"Ana "})
        self.assertEqual(self.names(nobody), set())

    def test_the_change_page_shows_both_fields_and_the_legacy_one_relabelled(self):
        response = self.client.get(f"{PLAYERS}{self.vegan.pk}/change/")

        self.assertContains(response, "Souhaite être avec")
        self.assertContains(response, "Préfère éviter")
        self.assertContains(response, "Souhaits d&#x27;équipe (ancien format)")
```

- [ ] **Step 2: Run red**: `... test_registration_admin.TestPlayerAdminRegistration` → FAIL.

- [ ] **Step 3: Implement** in `PlayerAdmin`:

```python
    list_display = [
        "user", "rating", "team", "edition", "attendance_confirmed", "has_dietary",
        "wants_with", "wants_to_avoid",
    ]
    ...
    search_fields = [
        "user__first_name", "user__last_name", "user__username", "team__name", "edition__year",
        "team_with", "team_avoid",
    ]

    @display(description="Souhaite être avec")
    def wants_with(self, obj):
        """The first characters of what the player asked to be paired with."""
        return Truncator(obj.team_with).chars(60)

    @display(description="Préfère éviter")
    def wants_to_avoid(self, obj):
        """The first characters of whom the player would rather avoid."""
        return Truncator(obj.team_avoid).chars(60)
```

Add `from django.utils.text import Truncator` to the imports if absent. Keep `list_editable = ["team"]` unchanged (`team` stays first editable column; the new columns are read-only).

- [ ] **Step 4: Run green**; then the whole suite: `docker compose exec server python manage.py test` → PASS, and `makemigrations --check --dry-run` clean.

- [ ] **Step 5: Commit** `[FEAT] Player admin: team preference columns and search`.

### Task 5: Server docs

**Files:** Modify `CLAUDE.md`.

- [ ] **Step 1:** In the root `CLAUDE.md`, replace every statement that `team_wishes` is what the registration API takes/returns (grep `team_wishes`): describe `team_with`/`team_avoid` (private, 500 chars, `_text`), the legacy `team_wishes` kept as « Souhaits d'équipe (ancien format) » (CSV import still writes it, the API neither reads nor returns it, deactivation clears it), `PRIVATE_FIELDS`, `PRIVATE_KEYS`, `PlayerInline.exclude`, the Player admin columns/search, migration `0044`. Deploy note: migrate, server, then front.
- [ ] **Step 2:** `git grep -n "team_wishes" CLAUDE.md` and check each remaining mention is about the legacy column.
- [ ] **Step 3: Commit** `[DOCS] CLAUDE.md: team_with and team_avoid`. Then open the PR only when Hugo asks.

---

# PR 2 — Front

## File structure

- `front/src/lib/registration.js` — form model uses `team_with`/`team_avoid`; `RATING_DEFAULT`, `stepOfErrors`, `stepOfForm`.
- `front/src/lib/components/RegistrationForm.svelte` — rewritten as the wizard.
- `front/src/lib/i18n/fr.js`, `en.js` — step, navigation, team strings.
- Tests: `registration.test.js`, `fixtures/registration.js`, `RegistrationForm.test.js`, `routes/register/page.server.test.js`.
- `CLAUDE.md`; scratchpad `seed_upcoming.py`.

### Task 6: Pure module

**Files:**
- Modify: `front/src/lib/registration.js`, `front/src/lib/fixtures/registration.js:53`
- Test: `front/src/lib/registration.test.js`

- [ ] **Step 1: Update/add tests (red).**
  - Fixture `savedAnswers`: replace `team_wishes: 'Avec Bob'` with `team_with: 'Avec Bob', team_avoid: 'Pas Carl'`.
  - Existing assertions: line 65 → `values.team_with` is `'Avec Bob'` and `values.team_avoid` is `'Pas Carl'`; line 86 (suggested: nothing carried) → both `''`; line 97–102 posted-values test → use `team_with: 'typed'` and `expect(values.team_with).toBe('typed')`; line 126 `['team_wishes', 'Avec Bob']` → `['team_with', 'Avec Bob'], ['team_avoid', 'Pas Carl']`; line 173 body → `team_with: 'Avec Bob', team_avoid: 'Pas Carl'`.
  - Sliders default to 5. Any existing assertion that a blank form's ratings/global_level are `''` becomes `String(RATING_DEFAULT)` (`'5'`). Import `RATING_DEFAULT`.
  - New tests:

```js
describe('sliders start at five', () => {
	it('a new form starts every rating and the global level at the default', () => {
		const values = initialValues({ ...registrationPayload, registration: null, suggested: null });

		expect(RATING_DEFAULT).toBe(5);
		expect(values.ratings).toEqual({ CARD: '5', STR: '5' });
		expect(values.global_level).toBe('5');
	});

	it('a refused post keeps its values but never hands a slider a blank', () => {
		const posted = { ...initialValues(registrationPayload), ratings: { CARD: '9', STR: '' }, global_level: '' };

		const values = initialValues(registrationPayload, posted);

		expect(values.ratings).toEqual({ CARD: '9', STR: '5' });
		expect(values.global_level).toBe('5');
	});
});

describe('stepOfErrors', () => {
	it.each([
		[['missing_frequency'], 1],
		[['invalid_frequency'], 1],
		[['invalid_sport'], 1],
		[['too_many_sports'], 1],
		[['missing_rating'], 2],
		[['invalid_rating'], 2],
		[['invalid_global_level'], 2],
		[['too_long'], 3],
		[['invalid_text'], 3],
		[['attendance_required'], 3],
		[['no_email'], 3],
		[['invalid_email'], 3],
		[['email_taken'], 3],
		[['something_new'], 3],
		[[], 3],
		[undefined, 3]
	])('%j goes to step %i', (codes, step) => {
		expect(stepOfErrors(codes)).toBe(step);
	});

	it('goes by the first error', () => {
		expect(stepOfErrors(['invalid_rating', 'missing_frequency'])).toBe(2);
		expect(stepOfErrors(['too_long', 'missing_frequency'])).toBe(3);
	});
});

describe('stepOfForm', () => {
	it('starts on step 1 without a post result or after a saved one', () => {
		expect(stepOfForm(null)).toBe(1);
		expect(stepOfForm({ action: 'save', ok: true })).toBe(1);
		expect(stepOfForm({ action: 'withdraw', ok: true })).toBe(1);
	});

	it('goes to the step of the first refusal, a refused withdrawal to step 3', () => {
		expect(stepOfForm({ action: 'save', errors: ['missing_rating'] })).toBe(2);
		expect(stepOfForm({ action: 'save', errors: ['invalid_sport', 'too_long'] })).toBe(1);
		expect(stepOfForm({ action: 'save', error: 'closed' })).toBe(3);
		expect(stepOfForm({ action: 'withdraw', error: 'register.error.has_team' })).toBe(3);
	});
});
```

  Import `stepOfErrors`, `stepOfForm` too.

- [ ] **Step 2: Run red**: `cd front && npm test -- src/lib/registration.test.js` → FAIL.

- [ ] **Step 3: Implement** in `registration.js`:
  - After `MAX_SPORTS`: `/** The slider's start, submitted as is when it is not touched. */ export const RATING_DEFAULT = 5;`
  - `initialValues`: posted path becomes

```js
	if (posted) {
		const fallback = String(RATING_DEFAULT);
		return {
			...posted,
			ratings: Object.fromEntries(
				Object.entries(posted.ratings ?? {}).map(([id, value]) => [id, text(value).trim() === '' ? fallback : value])
			),
			global_level: text(posted.global_level).trim() === '' ? fallback : posted.global_level,
			sports: posted.sports?.length > 0 ? posted.sports : [emptySport()]
		};
	}
```

  Blank model: `ratings: Object.fromEntries(payload.skills.map((s) => [s.identifier, String(RATING_DEFAULT)]))`, `global_level: String(RATING_DEFAULT)`, `team_with: ''`, `team_avoid: ''`; saved branch sets `values.team_with = text(saved.team_with); values.team_avoid = text(saved.team_avoid);`; update its doc comment (wishes → team preferences).
  - `valuesFromForm`: `team_with: text(form.get('team_with')), team_avoid: text(form.get('team_avoid')),`.
  - `bodyFromValues`: `team_with: values.team_with, team_avoid: values.team_avoid,`.
  - New, after `errorKeys`:

```js
const STEP_ONE = new Set(['missing_frequency', 'invalid_frequency', 'invalid_sport', 'too_many_sports']);
const STEP_TWO = new Set(['missing_rating', 'invalid_rating', 'invalid_global_level']);

/**
 * The wizard step (1 to 3) to open after a refusal: the step of the first API code, step 3
 * for every other code (texts, email, the tick, a closed or throttled form) and for none.
 */
export function stepOfErrors(codes) {
	const first = Array.isArray(codes) ? codes[0] : undefined;
	if (STEP_ONE.has(first)) return 1;
	if (STEP_TWO.has(first)) return 2;
	return 3;
}

/** The step a page opens on given the last post result: 1 unless a save or withdrawal was refused. */
export function stepOfForm(form) {
	if (!form || form.ok) return 1;
	if (form.action === 'withdraw') return 3;
	return stepOfErrors(form.errors ?? (form.error ? [form.error] : []));
}
```

- [ ] **Step 4: Run green** (same command) → PASS.
- [ ] **Step 5: Commit** `[FEAT] registration model: team_with/team_avoid, slider default, step of a refusal`.

### Task 7: Route action tests

**Files:** `front/src/routes/register/page.server.test.js` (lines 30, 92, 119).

- [ ] **Step 1:** Replace the posted pair `['team_wishes', '']` with `['team_with', ''], ['team_avoid', '']`; the expected body (line 92) `team_wishes: ''` → `team_with: '', team_avoid: ''`; line 119 → `expect(result.data.values.team_with).toBe('')`. Where a test posts blank ratings and expects `errors` back with blank values, the returned model is the raw `valuesFromForm` (unchanged: blanks stay blank in the action's result; the component applies the default). Add one test: posting `team_with=Léa` and `team_avoid=Carl` reaches the API body as typed (look at how the neighbouring test captures the fetch body and copy it).
- [ ] **Step 2:** `npm test -- src/routes/register/page.server.test.js` → PASS (the action has no code change: it goes through the pure module). If red, fix only what the test says.
- [ ] **Step 3: Commit** `[TEST] register action carries the two team fields`.

### Task 8: Dictionaries

**Files:** `front/src/lib/i18n/fr.js`, `en.js` (parity test `parity.test.js`).

- [ ] **Step 1:** In both files remove `register.teamWishes` and `register.teamWishesHint` and add (right where they were):

French:
```js
	'register.steps.label': "Étapes de l'inscription",
	'register.step.of': 'Étape {n} sur {total}',
	'register.step.1': 'Votre pratique sportive',
	'register.step.2': 'Votre niveau',
	'register.step.3': 'Demandes supplémentaires',
	'register.step.next': 'Suivant',
	'register.step.previous': 'Précédent',
	'register.step.incomplete': 'Complétez les champs obligatoires pour continuer.',
	'register.teamWith': 'Avec qui souhaitez-vous être ?',
	'register.teamWithHint': 'Ces demandes restent confidentielles. Elles ne pourront pas toutes être satisfaites.',
	'register.teamAvoid': 'Avec qui préférez-vous ne pas être ?',
	'register.teamAvoidHint': 'Ces demandes restent confidentielles. Elles ne pourront pas toutes être satisfaites.',
	'register.summary.with': 'Avec',
	'register.summary.avoid': 'À éviter',
	'register.scaleLow': '1, le plus bas',
	'register.scaleHigh': '10, le plus haut',
```

English:
```js
	'register.steps.label': 'Registration steps',
	'register.step.of': 'Step {n} of {total}',
	'register.step.1': 'Your sports background',
	'register.step.2': 'Your level',
	'register.step.3': 'Additional requests',
	'register.step.next': 'Next',
	'register.step.previous': 'Previous',
	'register.step.incomplete': 'Fill in the required fields to continue.',
	'register.teamWith': 'Who would you like to be with?',
	'register.teamWithHint': 'These requests stay confidential. Not all of them can be met.',
	'register.teamAvoid': 'Who would you rather not be with?',
	'register.teamAvoidHint': 'These requests stay confidential. Not all of them can be met.',
	'register.summary.with': 'With',
	'register.summary.avoid': 'To avoid',
	'register.scaleLow': '1, lowest',
	'register.scaleHigh': '10, highest',
```

- [ ] **Step 2:** `npm test -- src/lib/i18n` → PASS (parity). `RegistrationForm.svelte` still references the removed keys, so its tests fail until Task 9: that is expected, do not fix them here.
- [ ] **Step 3: Commit** `[FEAT] registration wizard dictionaries (fr, en)`.

### Task 9: The wizard component

**Files:**
- Modify: `front/src/lib/components/RegistrationForm.svelte`
- Test: `front/src/lib/components/RegistrationForm.test.js`

**How the existing tests change.** The form is now three `hidden` panels. `getByLabelText`/`getByText` ignore `hidden`, but `getByRole` does not see inside a hidden panel, so every role query on a step-2/3 field must first go to that step. Add this helper at the top of the test file and use it:

```js
import { tick } from 'svelte';

/** Opens a step the way a player does: a registered player jumps, a new one fills step 1's frequency and goes forward. */
async function toStep(n) {
	for (let step = 1; step < n; step += 1) {
		const radio = screen.queryAllByRole('radio').find((r) => r.checked) ?? null;
		if (!radio && screen.queryAllByRole('radio').length > 0) {
			await fireEvent.click(screen.getAllByRole('radio')[0]);
		}
		await fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		await tick();
	}
}
```

(`Next` is the English `register.step.next`; `renderWith` is English by default.) Tests about the email, tick and notices (step 3) call `await toStep(3)` before role queries; tests about sports rows stay on step 1; tests about the posted values (`team_wishes` → `team_with`) read the textarea through `getByLabelText`, which needs no step.

- [ ] **Step 1: Write the new failing tests** (append; keep and fix the existing ones as above):

```js
describe('RegistrationForm wizard', () => {
	const step = (n) => document.querySelector(`[data-step="${n}"]`);

	it('shows step 1 only, with the progress, and no previous button', () => {
		renderWith(RegistrationForm, { registration: open });

		expect(step(1)).not.toHaveAttribute('hidden');
		expect(step(2)).toHaveAttribute('hidden');
		expect(step(3)).toHaveAttribute('hidden');
		expect(screen.getByText('Step 1 of 3')).toBeInTheDocument();
		const nav = screen.getByRole('navigation', { name: 'Registration steps' });
		expect(within(nav).getByRole('button', { name: 'Your sports background' })).toHaveAttribute('aria-current', 'step');
		expect(screen.queryByRole('button', { name: 'Previous' })).toBeNull();
		expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '1');
		expect(screen.queryByRole('button', { name: 'Register' })).toBeNull();
	});

	it('refuses to leave step 1 without a frequency, then goes forward once it is chosen', async () => {
		renderWith(RegistrationForm, { registration: open });

		await fireEvent.click(screen.getByRole('button', { name: 'Next' }));

		expect(step(1)).not.toHaveAttribute('hidden');
		expect(screen.getByRole('alert')).toHaveTextContent('Fill in the required fields to continue.');

		await fireEvent.click(screen.getByLabelText('About one hour a week'));
		await fireEvent.click(screen.getByRole('button', { name: 'Next' }));

		expect(step(2)).not.toHaveAttribute('hidden');
		expect(step(1)).toHaveAttribute('hidden');
		expect(screen.getByText('Step 2 of 3')).toBeInTheDocument();
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('moves focus to the new step heading', async () => {
		renderWith(RegistrationForm, { registration: open });
		await fireEvent.click(screen.getByLabelText('About one hour a week'));

		await fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		await tick();

		expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Your level' }));
	});

	it('goes back freely and a new player cannot jump ahead', async () => {
		renderWith(RegistrationForm, { registration: open });
		const nav = screen.getByRole('navigation', { name: 'Registration steps' });

		expect(within(nav).getByRole('button', { name: 'Your level' })).toBeDisabled();
		expect(within(nav).getByRole('button', { name: 'Additional requests' })).toBeDisabled();

		await toStep(2);
		await fireEvent.click(screen.getByRole('button', { name: 'Previous' }));
		expect(step(1)).not.toHaveAttribute('hidden');

		await fireEvent.click(within(nav).getByRole('button', { name: 'Your level' }));
		expect(step(2)).not.toHaveAttribute('hidden');
	});

	it('lets a registered player jump to any step', async () => {
		renderWith(RegistrationForm, { registration: registered });
		const nav = screen.getByRole('navigation', { name: 'Registration steps' });

		await fireEvent.click(within(nav).getByRole('button', { name: 'Additional requests' }));

		expect(step(3)).not.toHaveAttribute('hidden');
		expect(screen.getByRole('button', { name: 'Save my answers' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Withdraw my registration' })).toBeInTheDocument();
	});

	it('gates step 3 on the tick, and on an email when one is asked', async () => {
		renderWith(RegistrationForm, { registration: { ...open, email: { value: '', editable: true } } });
		await toStep(3);

		expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Next' })).toBeNull();
		expect(screen.getByRole('textbox', { name: 'Email address' })).toBeRequired();
		expect(screen.getByRole('checkbox')).toBeRequired();
	});

	it.each([
		[['missing_frequency'], 1],
		[['invalid_rating'], 2],
		[['too_long'], 3]
	])('opens on the step of the first error %j, keeping the whole list above', (errors, n) => {
		renderWith(RegistrationForm, {
			registration: open,
			form: { action: 'save', errors, values: initialValues(open) }
		});

		expect(step(n)).not.toHaveAttribute('hidden');
		expect(screen.getByText(`Step ${n} of 3`)).toBeInTheDocument();
		expect(screen.getByRole('alert')).toBeInTheDocument();
		// after a refusal every step is reachable again
		expect(within(screen.getByRole('navigation', { name: 'Registration steps' })).getByRole('button', { name: 'Additional requests' })).toBeEnabled();
	});

	it('shows the notices above the progress, on every step', async () => {
		renderWith(RegistrationForm, { registration: registered, form: { action: 'save', ok: true } });
		const status = screen.getByRole('status');
		const nav = screen.getByRole('navigation', { name: 'Registration steps' });

		expect(status.compareDocumentPosition(nav) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
		await fireEvent.click(within(nav).getByRole('button', { name: 'Additional requests' }));
		expect(screen.getByRole('status')).toBeInTheDocument();
	});

	it('keeps the intro on step 1 only', () => {
		renderWith(RegistrationForm, { registration: open });

		expect(step(1)).toContainElement(screen.getByText('Welcome to registration'));
	});

	it('does not hide any panel for visitors without JavaScript', () => {
		const { container } = renderWith(RegistrationForm, { registration: open });

		// the stylesheet that un-hides the panels lives in a <noscript> in the head
		expect(document.head.innerHTML + container.innerHTML).toContain('noscript');
	});
});

describe('RegistrationForm sliders', () => {
	it('starts every slider at 5, shows its value and submits it', () => {
		renderWith(RegistrationForm, { registration: open });

		const cardio = screen.getByLabelText('Cardio');
		expect(cardio).toHaveAttribute('type', 'range');
		expect(cardio).toHaveAttribute('min', '1');
		expect(cardio).toHaveAttribute('max', '10');
		expect(cardio).toHaveAttribute('step', '1');
		expect(cardio).toHaveValue('5');
		expect(document.getElementById('rating-CARD-value')).toHaveTextContent('5');
		expect(cardio).toHaveAttribute('aria-describedby', 'rating-CARD-value');
		const global = screen.getByLabelText('Overall level');
		expect(global).toHaveAttribute('type', 'range');
		expect(global).toHaveValue('5');
	});

	it('shows the value the player moves it to', async () => {
		renderWith(RegistrationForm, { registration: open });

		await fireEvent.input(screen.getByLabelText('Cardio'), { target: { value: '8' } });

		expect(document.getElementById('rating-CARD-value')).toHaveTextContent('8');
		expect(screen.getByLabelText('Cardio')).toHaveValue('8');
	});

	it('shows the saved ratings, not the default', () => {
		renderWith(RegistrationForm, { registration: registered });

		expect(screen.getByLabelText('Cardio')).toHaveValue(String(savedAnswers.ratings.CARD));
	});
});

describe('RegistrationForm team preferences', () => {
	it('has two fields, tied to their hints, and no legacy field', () => {
		renderWith(RegistrationForm, { registration: open });

		const withField = screen.getByLabelText('Who would you like to be with?');
		const avoidField = screen.getByLabelText('Who would you rather not be with?');
		expect(withField).toHaveAttribute('name', 'team_with');
		expect(avoidField).toHaveAttribute('name', 'team_avoid');
		expect(withField).toHaveAttribute('aria-describedby', 'team-with-hint');
		expect(avoidField).toHaveAttribute('aria-describedby', 'team-avoid-hint');
		expect(document.querySelector('[name="team_wishes"]')).toBeNull();
	});

	it('fills them from the saved answers', () => {
		renderWith(RegistrationForm, { registration: registered });
		expect(screen.getByLabelText('Who would you like to be with?')).toHaveValue('Avec Bob');
		expect(screen.getByLabelText('Who would you rather not be with?')).toHaveValue('Pas Carl');
	});

	it('shows both in the read-only summary once registration is closed', () => {
		renderWith(RegistrationForm, { registration: { ...registered, state: { is_open: false, reason: 'closed' } } });

		expect(screen.getByText('With')).toBeInTheDocument();
		expect(screen.getByText('Avec Bob')).toBeInTheDocument();
		expect(screen.getByText('To avoid')).toBeInTheDocument();
		expect(screen.getByText('Pas Carl')).toBeInTheDocument();
	});

	it('speaks French', () => {
		renderWith(RegistrationForm, { registration: open }, 'fr');

		expect(screen.getByText('Étape 1 sur 3')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Votre pratique sportive' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Suivant' })).toBeInTheDocument();
	});
});
```

Use the real fixture value for the saved Cardio rating (open `fixtures/registration.js`); if the fixture's `savedAnswers.team_avoid` is `'Pas Carl'` as set in Task 6 the summary test above passes unchanged. Confirm whether `renderWith`'s third argument is the locale string (it is, per CLAUDE.md).

- [ ] **Step 2: Run red**: `npm test -- src/lib/components/RegistrationForm.test.js` → FAIL (no `data-step`, no sliders, missing keys).

- [ ] **Step 3: Implement.** Edit `RegistrationForm.svelte`:

**Script** — imports: `import { onMount, tick } from 'svelte';` and add `RATING_DEFAULT` is not needed here; add `stepOfForm` to the `$lib/registration` import list. After the `loadedFrom` block replace it with (the identity check is unchanged, the step is set in the same place):

```js
	// The wizard's state: the step on screen and the furthest one reached (a new player goes
	// forward only through "Next", which validates the step; backwards is always free).
	let step = stepOfForm(form);
	let reached = step;
	let nextError = false;
	let formElement;

	let values = initialValues(registration, form?.values ?? null);
	let loadedFrom = [registration, form];
	$: if (registration !== loadedFrom[0] || form !== loadedFrom[1]) {
		loadedFrom = [registration, form];
		values = initialValues(registration, form?.values ?? null);
		step = stepOfForm(form);
		reached = Math.max(reached, step);
		nextError = false;
	}
	```

(keep the long explanatory comment above it, adding "and puts the wizard on the step of the first refusal".) Then:

```js
	const STEPS = [1, 2, 3];
	$: formShown = open && !removed;
	// Anyone with a saved registration may jump anywhere; a new player only back or to the step reached.
	$: canGo = (n) => registered || n <= reached;

	/** Moves to a step and puts focus on its heading, so a screen reader announces it. */
	async function goTo(n) {
		step = n;
		nextError = false;
		await tick();
		document.getElementById(`register-step-${n}`)?.focus();
		document.getElementById(`register-step-${n}`)?.scrollIntoView?.({ block: 'start' });
	}

	/** Whether the step's required fields are filled; the browser shows its own message on the first that is not. */
	function stepIsValid(n) {
		const panel = formElement?.querySelector(`[data-step="${n}"]`);
		if (!panel) return true;
		return [...panel.querySelectorAll('input, select, textarea')].every((field) => field.reportValidity());
	}

	function next() {
		if (!stepIsValid(step)) {
			nextError = true;
			return;
		}
		reached = Math.max(reached, step + 1);
		goTo(step + 1);
	}
```

**Markup** — (1) the intro: replace the top `{#if introText}<p class="intro">…{/if}` with `{#if introText && !formShown}<p class="intro">{introText}</p>{/if}`. (2) In the open branch, keep the status/registered/withdrawn/suggested notices, then put the `register-errors` alert **above** the progress (move it out of the form's end; same markup `{#if errorKeys.length > 0}<div class="error" id="register-errors" tabindex="-1" role="alert">…</div>{/if}`), then add the head and progress:

```svelte
	<svelte:head>
		<noscript>
			<style>
				.registration .step[hidden] { display: block; }
				.wizard-only { display: none; }
			</style>
		</noscript>
	</svelte:head>

	<nav class="progress wizard-only" aria-label={t('register.steps.label')}>
		<p class="progress-text num">{t('register.step.of', { n: step, total: STEPS.length })}</p>
		<div class="bar" role="progressbar" aria-valuemin="1" aria-valuemax={STEPS.length} aria-valuenow={step} aria-valuetext={t('register.step.of', { n: step, total: STEPS.length })}>
			<div class="fill" style="width: {(step / STEPS.length) * 100}%"></div>
		</div>
		<ol>
			{#each STEPS as n}
				<li>
					<button type="button" class="step-name" aria-current={n === step ? 'step' : undefined} disabled={!canGo(n)} on:click={() => goTo(n)}>
						<span class="num">{n}</span> {t(`register.step.${n}`)}
					</button>
				</li>
			{/each}
		</ol>
	</nav>
```

(`style="width: …"` is layout, not colour, so `styles.test.js` accepts it. If the test forbids inline style, use a CSS custom property `--progress` set the same way and `width: var(--progress)`.) (3) Wrap the form content in three panels, in this order, inside `<form method="POST" action="?/save" class="registration" bind:this={formElement}>` (hidden `skill` inputs stay first):

```svelte
		<div class="step" data-step="1" hidden={step !== 1}>
			<h2 id="register-step-1" tabindex="-1">{t('register.step.1')}</h2>
			{#if introText}<p class="intro">{introText}</p>{/if}
			<!-- the frequency <fieldset> and the sports <fieldset class="sports">, unchanged -->
		</div>

		<div class="step" data-step="2" hidden={step !== 2}>
			<h2 id="register-step-2" tabindex="-1">{t('register.step.2')}</h2>
			<p class="lead" id="register-skills">{month ? t('register.skillsIntro', { month }) : t('register.skillsIntroNoMonth')}</p>
			{#each registration.skills as skill}
				<div class="field slider">
					<label for="rating-{skill.identifier}">{skillName(skill)}</label>
					<div class="range">
						<span class="end" aria-hidden="true">1</span>
						<input
							id="rating-{skill.identifier}"
							type="range"
							name="rating.{skill.identifier}"
							min="1"
							max="10"
							step="1"
							aria-describedby="rating-{skill.identifier}-value"
							bind:value={values.ratings[skill.identifier]}
						/>
						<span class="end" aria-hidden="true">10</span>
						<output id="rating-{skill.identifier}-value" for="rating-{skill.identifier}" class="value num">{values.ratings[skill.identifier]}</output>
					</div>
				</div>
			{/each}
			<div class="field slider">
				<label for="global-level">{t('register.globalLevel')}</label>
				<p class="hint" id="global-level-hint">
					{programme
						? t('register.globalQuestion', { year: edition.year, disciplines: programme })
						: t('register.globalQuestionShort', { year: edition.year })}
				</p>
				<div class="range">
					<span class="end" aria-hidden="true">1</span>
					<input id="global-level" type="range" name="global_level" min="1" max="10" step="1" aria-describedby="global-level-hint global-level-value" bind:value={values.global_level} />
					<span class="end" aria-hidden="true">10</span>
					<output id="global-level-value" for="global-level" class="value num">{values.global_level}</output>
				</div>
			</div>
		</div>

		<div class="step" data-step="3" hidden={step !== 3}>
			<h2 id="register-step-3" tabindex="-1">{t('register.step.3')}</h2>
			<div class="field">
				<label for="team-with">{t('register.teamWith')} <span class="optional">({t('register.optional')})</span></label>
				<p class="hint" id="team-with-hint">{t('register.teamWithHint')}</p>
				<textarea id="team-with" aria-describedby="team-with-hint" name="team_with" rows="3" maxlength="500" bind:value={values.team_with}></textarea>
			</div>
			<div class="field">
				<label for="team-avoid">{t('register.teamAvoid')} <span class="optional">({t('register.optional')})</span></label>
				<p class="hint" id="team-avoid-hint">{t('register.teamAvoidHint')}</p>
				<textarea id="team-avoid" aria-describedby="team-avoid-hint" name="team_avoid" rows="3" maxlength="500" bind:value={values.team_avoid}></textarea>
			</div>
			<!-- the dietary field, the email (read-only or required), the tick, the two notes: unchanged -->
		</div>

		<div class="nav-buttons">
			{#if nextError}<p class="error wizard-only" role="alert">{t('register.step.incomplete')}</p>{/if}
			{#if step > 1}
				<button type="button" class="pill wizard-only" on:click={() => goTo(step - 1)}>{t('register.step.previous')}</button>
			{/if}
			{#if step < STEPS.length}
				<button type="button" class="submit wizard-only" on:click={next}>{t('register.step.next')}</button>
			{/if}
			<button class="submit final" hidden={step !== STEPS.length}>{registered ? t('register.submitEdit') : t('register.submit')}</button>
		</div>
```

Notes: (a) the final submit is `hidden` until step 3; the noscript style must un-hide it too — extend that style block with `.final[hidden] { display: inline-block; }` and `.withdraw[hidden] { display: grid; }`. (b) The withdraw `<form>` stays after the main form but is shown only on step 3 (or when `step === 3`): wrap it `{#if registered && step === 3}` — except without JS, where all show: use `hidden={step !== 3}` on the withdraw form plus `.withdraw[hidden]` in the noscript block. (c) The old per-section `<h2 id="register-skills">` becomes the `.lead` paragraph above (the heading is now the step name). Keep the `fieldset` frequency `required` radios. (d) The closed summary: replace the `register.teamWishes` row by

```svelte
				<dt>{t('register.summary.with')}</dt>
				<dd>{saved.team_with || t('register.summary.none')}</dd>
				<dt>{t('register.summary.avoid')}</dt>
				<dd>{saved.team_avoid || t('register.summary.none')}</dd>
```

(e) the `onMount` focus code is unchanged (the error alert is above the progress and always visible).

**Styles** — add (tokens only), and delete the `.registration h2` rule's dependence if needed:

```css
	.step[hidden] {
		display: none;
	}
	.progress {
		margin: 0 0 1.25rem;
	}
	.progress-text {
		margin: 0 0 0.5rem;
		color: var(--muted);
	}
	.bar {
		height: 0.375rem;
		border-radius: 999px;
		background: var(--bg-sunken);
		border: 1px solid var(--line);
		overflow: hidden;
	}
	.fill {
		height: 100%;
		background: var(--accent);
	}
	.progress ol {
		display: flex;
		gap: 0.5rem;
		list-style: none;
		margin: 0.75rem 0 0;
		padding: 0;
	}
	.progress li {
		flex: 1;
	}
	.step-name {
		width: 100%;
		padding: 0.5rem;
		background: transparent;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		color: var(--muted);
		font: inherit;
		cursor: pointer;
	}
	.step-name[aria-current='step'] {
		color: var(--ink);
		border-color: var(--accent);
	}
	.step-name:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.range {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		max-width: 28rem;
	}
	.range input[type='range'] {
		flex: 1;
		accent-color: var(--accent);
		min-height: 2rem;
	}
	.end {
		color: var(--muted);
		font-size: 0.875rem;
	}
	.value {
		min-width: 2ch;
		font-size: 1.75rem;
		text-align: right;
		color: var(--ink);
	}
	.lead {
		margin: 0 0 1rem;
	}
	.nav-buttons {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		align-items: center;
	}
	.nav-buttons .error {
		flex-basis: 100%;
	}
	.final[hidden] {
		display: none;
	}
```

(The `.sr` hints `register.scaleLow/High` are reserved for the end labels: give the two `.end` spans `title` attributes `t('register.scaleLow')`/`t('register.scaleHigh')` rather than leaving the keys unused, or delete the two keys from both dictionaries. Pick the `title` option.) A `prefers-reduced-motion` block is unnecessary: nothing animates.

- [ ] **Step 4: Run green**: `npm test -- src/lib/components/RegistrationForm.test.js` then the whole front suite `npm test` (parity, `styles.test.js`, the register page tests) and `npm run build`. Fix the existing tests the new structure broke by applying the `toStep` rule above, never by weakening an assertion. Expected: all PASS.

- [ ] **Step 5: Commit** `[FEAT] registration form as a three-step wizard with sliders and two team fields`.

### Task 10: CLAUDE.md and the smoke seed

**Files:** `CLAUDE.md`; scratchpad `seed_upcoming.py` (not in the repo).

- [ ] **Step 1:** In `CLAUDE.md`'s registration front paragraph, replace the single-form description with the wizard: three `hidden` panels in one plain-POST form, `data-step`, the progress `nav` (`aria-current="step"`, `role="progressbar"`), forward gated by native `reportValidity` (a registered player jumps freely; after a refusal all steps are reachable), the step of a refusal through `stepOfForm`/`stepOfErrors` in `$lib/registration.js`, `RATING_DEFAULT = 5` sliders (`<input type="range">`, value in an `<output>`), `team_with`/`team_avoid` textareas, notices and the error alert above the progress, intro on step 1, the `<noscript>` style that un-hides every panel, the test helper rule (role queries on a non-visible step need the step opened first). Grep `team_wishes|teamWishes` once more and fix leftovers.
- [ ] **Step 2:** Update the scratchpad seed `register()` data: `"team_wishes": "Avec mes amis"` → `"team_with": "Avec mes amis", "team_avoid": "Pierre Placé"`. (Do not run it.)
- [ ] **Step 3: Commit** `[DOCS] CLAUDE.md: the registration wizard`.

### Task 11: Browser re-walk (controller only, with Hugo's yes)

Subagents never do this. After the server PR is merged and `migrate` applied to the dev DB (Hugo's go-ahead needed for the migration and for any seed): walk the smoke edition in the built-in browser as `smoke-returning`, `smoke-placeholder`, `smoke-registered`: step gating, Next with and without a frequency, sliders by keyboard (arrows, Home, End), typing in each step then going back/forward (nothing resets: the `loadedFrom` pattern), a refusal (blank frequency forced by editing the DOM, or an over-long team text) landing on the right step with the list above, saving, the closed summary, 375px width, French, and a JS-disabled style check via the `<noscript>` block. Then run `cleanup_upcoming.py` only if Hugo asks.

---

## Self-review against the spec

- Two free-text fields, legacy kept and relabelled, CSV import untouched → Tasks 1, 2, 4. Sliders default 5, untouched submits 5 → Tasks 6, 9 (the slider's value is bound, so the submitted value is `5`). Gated forward / free back / free jump when registered → Task 9 (`canGo`, `next`). Step names → Tasks 8, 9. Admin columns and search → Task 4. Notices above progress, intro on step 1 → Task 9. Out of scope items (draft saving, picker, CSV export, team builder) have no task. Server errors for new fields reuse `too_long`/`invalid_text` → Task 2. `suggested` never carries the fields → Task 2 test. Privacy lists (`PRIVATE_KEYS`, `PRIVATE_FIELDS`, deactivate, inline exclude) → Task 3. No-JS stacking via `<noscript>` → Task 9. Focus on step change, `aria-current`, labelled `nav`, outputs tied by `aria-describedby`, `hidden` panels → Task 9. `stepOfErrors`, `RATING_DEFAULT` → Task 6.
- Known deviation: "Suivant errors in a `role=alert`" is a text line (`register.step.incomplete`) plus the browser's own bubble from `reportValidity`.
- Rollout: server PR first (migrate, deploy server), front PR second; an older front sending `team_wishes` has it silently dropped.
