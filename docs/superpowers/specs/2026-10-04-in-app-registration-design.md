# In-app registration (2027 edition)

Status: design, approved section by section in conversation on 2026-10-04.

## Goal

Replace the Google Form + CSV upload with a registration done inside the app, by logged-in players. The CSV import stays for past editions.

## Decisions

- **Account-first.** A player must have an account to register. Returning players log in; newcomers are **invited** by an organiser (no open signup, no email verification for now).
- **Immediate.** Submitting creates or updates the `Player` and `PlayerRating` rows at once (no review step, no cap). Organisers remove anyone with the existing soft delete.
- **Questionnaire as data.** Skills and their weights are edited per edition in the admin; `FORM_PROFILES` in `registration.py` stays only for importing old CSVs.
- **Email is not collected.** It is read from the account and shown read-only, with a link to `/account` to change it.
- **Out of scope:** mailing invites, in-app payment (the tick below is a placeholder for it), player caps, answering for someone else, a player picker for team wishes.

## Data model

### `RegistrationSkill` (new, per edition)

`edition`, `name_fr`, `name_en`, `identifier` (at most 4 characters, the `PlayerRating.identifier` limit, unique per edition), `weight` (positive integer, the old `coef`), `order`, `is_active`. An `EditionAdmin` inline edits them and an action, « Copier le questionnaire de l'édition précédente », copies the previous year's active skills into an edition that has none. The 2025/2026 set (ten skills) seeds the first copy through a data migration for the existing editions that have players.

### `Edition` additions

- `registration_opens`, `registration_closes`: nullable dates. Open when today in Europe/Paris (`paris_today()`) is within them; a missing bound is unbounded, so an edition with neither is always open.
- `registration_intro_fr`, `registration_intro_en`: optional text shown above the form.
- `skills_month_fr`, `skills_month_en`: the month in « le niveau que tu auras en août » (blank omits the clause).
- The global-level question is generated from the edition's active disciplines in their stored order, so it cannot drift from the programme.

### `Player` additions (all per edition, private, organiser-visible)

| Field | Type | Notes |
|---|---|---|
| `dietary_restrictions` | text, blank | Optional, at most 500 characters. New, not in the old form. |
| `sport_frequency` | choice, blank | `rare` (less than once a month), `monthly` (less than once a week but several times a month), `hour` (about 1 hour a week), `two_hours` (at least 2 hours), `four_hours` (at least 4 hours). |
| `team_wishes` | text, blank | Free text, at most 1000 characters, confidential. |
| `attendance_confirmed` | boolean | The player's tick: « J'ai payé mon inscription et je confirme que je serai là ». Self-declared, nothing is checked. Placeholder for a later in-app payment, which will replace or complement it. Required to submit. |

### `PlayerSport` (new, a row per sport)

`player` (FK), `order`, `sport` (free text, at most 80 characters, with suggestions drawn from sport names already entered), `level` (choice: `beginner`, `amateur`, `club`, `competition`), `practice` (choice: `no_longer`, `occasionally`, `regularly`), `duration_months` (positive integer, entered as years and months in the UI), `notes` (free text, at most 200 characters: position, specialty, rank). A player has at most 15 rows; rows are replaced as a set on every save. Not in any public payload.

## API

All views are `IsAuthenticated`, none public, each added to the `PLAYER` list of `test_permissions.py`. `private, no-store` on every response. Errors are stable string codes the front maps to `register.error.*`.

- `GET /registration/`: the registrable edition (the latest active edition whose window is open, else the latest active one) and its form: edition `{year, opens, closes, is_open}`, intro, skills month, skills `[{identifier, name_fr, name_en}]`, the active disciplines for the global-level wording, the account email (read-only), the choice lists, and the caller's saved answers if any. 404 `not_a_person` for a user who is neither a person nor invited.
- `PUT /registration/`: body `{ratings: {identifier: 1-10}, global_level, dietary_restrictions, sport_frequency, sports: [{sport, level, practice, duration_months, notes}], team_wishes, attendance_confirmed}`. In one transaction under the user's row lock it update-or-creates the caller's `Player` (no team) with its `PlayerRating` rows and `PlayerSport` rows, and recomputes `Player.rating`. Refusals: 409 `closed` / `not_yet_open`; 400 with codes `missing_rating`, `invalid_rating`, `invalid_global_level`, `invalid_frequency`, `invalid_sport`, `too_many_sports`, `too_long`, `attendance_required`; 400 `no_email` when the account has none. Throttled by a `registration` scope (`UserRateThrottle`, config rate, default `30/hour`).
- `DELETE /registration/`: soft-deletes the caller's `Player` while the window is open; 409 `closed` afterwards.

The rating maths (weighted rating clipped to 1..10, global rating) moves from `registration.py` to a function shared by the CSV import and this endpoint, driven by a `{identifier: weight}` mapping; a test feeds both paths the same answers and requires equal ratings.

## Organisers (admin)

- `EditionAdmin`: window dates, intro and month texts, the `RegistrationSkill` inline, the copy action.
- `PlayerAdmin`: columns and filters for « confirmé » and « restrictions alimentaires », a `PlayerSport` inline, the private fields visible there only.
- **Invitations:** `UserProfile.invited` (bool). `claims.unclaimable_reason` accepts an invited user as well as a person (staff and inactive stay refused); `person_ids()`, the leaderboard and the badges are unchanged, since a person is still someone who played. An admin action « Inviter des joueurs » offers two modes: a form for one user (first name, last name, email) and a bulk textarea (one `Prénom Nom, email` per line). It creates users with a random password and `invited=True` and returns the claim links in Django messages, never logged. An email matching an existing user reuses that user and says so; malformed lines and duplicates within the paste are reported, not created. The username is derived as the registration import derives it (accents kept) so a returning player keeps their account.

## Front

- `/register` (no tab bar, `NO_TAB_BAR`): a visitor or a dead token goes to `/login?next=/register`. The form has a stepper per skill (1-10), the generated global-level question, the read-only email with a link to `/account`, the frequency choice, a sports table (add and remove rows, columns sport, level, practice, years and months, notes), team wishes, dietary restrictions and the required tick. Closed and not-yet-open states show the dates. A saved registration shows an « Enregistré » state with edit and withdraw.
- A « S'inscrire à l'édition 2027 » call to action on the hub and `/account` while registration is open and the caller has not registered.
- The `register` action is a plain POST/`fetch` like the account page's, with the API codes mapped to `register.error.*`. Strings in `fr.js` and `en.js` under `register.*` (parity test).

## Privacy

- None of the new `Player` fields nor `PlayerSport` appears in the summary or any public payload; `SummaryPlayerSerializer` keeps its explicit field list and the new keys join `PRIVATE_KEYS` in `test_showcase.py`.
- `deactivate()` (account deletion) clears every new private field and deletes the person's `PlayerSport` rows.
- `transfer.py` does not export the personal fields (`dietary_restrictions`, `team_wishes`, `sport_frequency`, `attendance_confirmed`, `PlayerSport`); `test_transfer.py` lists them.

## CSV import

The importer also stores frequency, team wishes and the confirmation from old CSVs (columns matched by header fragment as today). The free-text sports answer is not parsed into rows: it is kept as one `PlayerSport` row with the text in `notes`, `sport` set to « Historique (import) », or skipped when blank. Optional, slice 1.

## Testing

Django: shared rating function against the existing CSV fixtures; the endpoints (create, update, window edges in Paris time, every error code, withdraw and re-register, sports replaced as a set, throttle); invitation claimability; the bulk invite (reuse, duplicates, malformed lines); the copy action; query-count constants; `test_permissions.py` entries; the privacy walks; `makemigrations --check`. Front (Vitest): `/register` page and server tests (login redirect, closed state, validation, success), the call to action, `fr`/`en` parity.

## Rollout, three PRs from `dev`

1. Models, migrations, the skills admin and copy action, the shared rating function, the CSV import changes. No user-visible change.
2. `invited`, the invite action, and the registration API.
3. The front `/register` page and the calls to action.

Deploy order: server before front, `migrate`, rebuild the image. Seed the 2027 skills with the copy action once the edition exists. `CLAUDE.md` is updated in each PR.
