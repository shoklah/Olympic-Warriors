# In-app registration (2027 edition)

Status: design, approved section by section in conversation on 2026-10-04, then reviewed against the code twice (17 decisions, folded in below).

## Goal

Replace the Google Form + CSV upload with a registration done inside the app, by logged-in players. The CSV import stays for past editions.

## Decisions

- **Account-first.** A player must have an account to register. Returning players log in; newcomers are **invited** by an organiser (no open signup, no email verification for now).
- **Immediate.** Submitting creates or updates the `Player` and `PlayerRating` rows at once (no review step, no cap). Organisers remove anyone with the existing soft delete.
- **Questionnaire as data.** Skills and their weights are edited per edition in the admin; `FORM_PROFILES` in `registration.py` stays only for importing old CSVs.
- **Registration targets `latest_edition()`**, the only edition the site edits. The edition therefore exists before registration opens (it needs `host`, `start_date`, `end_date`; provisional values are fine, see `dates_confirmed`).
- **Out of scope:** mailing invites, in-app payment (the tick below is its placeholder), player caps, answering for someone else, a player picker for team wishes.

## Data model

### `RegistrationSkill` (new, per edition)

`edition`, `name_fr`, `name_en`, `identifier` (at most 4 characters, the `PlayerRating.identifier` limit, unique per edition), `weight` (positive integer, the old `coef`), `order`, `is_active`. `PlayerRating.name` keeps storing the English name, as the importer does; the French one is for display.

Admin: an inline on `EditionAdmin`. Once the edition has players with ratings, **adding, deleting and changing the identifier of a skill are refused**; weights, labels, order and `is_active` stay editable. A weight change does not touch stored ratings: the Edition action « Recalculer les notes » recomputes `Player.rating` from the stored raw `PlayerRating` and `global_level` values, for any edition, idempotently. Players without a `global_level` (every player of an edition imported before this feature: the blended `Player.rating` cannot be inverted) are skipped and counted in the report (« 34 joueurs ignorés : réponse globale inconnue »). An edition with no skills reports « Aucun questionnaire pour cette édition » and changes nothing. Another action, « Copier le questionnaire de l'édition précédente », copies the previous year's active skills into an edition that has none.

**Seeding by data migration:** edition 2024 from the 2024 profile of `FORM_PROFILES`, every edition from 2025 on from the 2025 profile, earlier editions nothing. During implementation, check the prod database (`PlayerRating` identifiers per edition) before writing the migration, and seed from what is actually there. A test builds editions shaped like the 2024 and 2026 forms from synthetic answers (the repo's CSV fixtures, plus the 2026 form's headers) and checks that seeded weights plus the shared function reproduce the importer's ratings; it does not claim to check prod values. Recomputing an old edition for real would need `global_level` backfilled from its CSV, an optional later command.

### `Edition` additions

- `registration_opens`, `registration_closes`: nullable dates. Registration is **open** only when all hold: `registration_opens` is set and reached (Europe/Paris, `paris_today()`), the edition has at least one active skill, and `registration_closes` has not passed (inclusive: open through that Paris day); a missing `registration_closes` means the day before the edition's `start_date`. A freshly created edition is therefore closed until an organiser sets `registration_opens`. A user holding a **late pass** (below) is open whatever the dates say, but still needs the skills. The API reports the state with a reason (`not_configured`, `not_yet_open`, `closed`, or `late_pass` for an exempted caller); the admin shows the dates' state next to them.
- `registration_intro_fr`, `registration_intro_en`: optional text above the form.
- `skills_month_fr`, `skills_month_en`: the month in « le niveau que tu auras en août » (blank omits the clause).
- `dates_confirmed` (bool, default true for existing rows). While false, the hub hides the countdown and date range and shows « Dates à venir ».
- The global-level question is generated from the edition's active disciplines in their stored order. Disciplines can be created early with no pairing system and scheduled later, once teams are known. With no discipline the clause is dropped.

### `Player` additions (per edition; private, organiser-visible)

| Field | Type | Notes |
|---|---|---|
| `global_level` | integer 1-10, nullable | The player's raw global answer. `Player.rating` blends it (`(weighted + 4 × global_level) / 5`, rounded) so it cannot be recovered otherwise; needed to pre-fill the form. The CSV import fills it too; old editions stay null. |
| `dietary_restrictions` | text, blank | Optional, at most 500 characters. New, not in the old form. |
| `sport_frequency` | choice | Required. `rare` (less than once a month), `monthly` (less than once a week but several times a month), `hour` (about 1 hour a week), `two_hours` (at least 2 hours), `four_hours` (at least 4 hours). Blank on rows the import cannot fill. |
| `team_wishes` | text, blank | Optional, at most 1000 characters, confidential. |
| `attendance_confirmed` | boolean | The tick « J'ai payé mon inscription et je confirme que je serai là ». Self-declared, nothing is checked. Placeholder for a later in-app payment. Required to submit. |

### `PlayerSport` (new, a row per sport)

`player` (FK), `order`, `sport` (free text, at most 80 characters, with suggestions drawn from sport names already entered), `level` (`beginner`, `amateur`, `club`, `competition`), `practice` (`no_longer`, `occasionally`, `regularly`), `duration_months` (positive integer, entered as years and months), `notes` (at most 200 characters: position, specialty, rank). At most 15 rows; replaced as a set on every save. Optional: zero rows is allowed.

### `UserProfile.invited` (bool)

`claims.unclaimable_reason` accepts an invited user as well as a person (staff and inactive stay refused). `person_ids()`, the leaderboard and the badges are unchanged: a person is still someone who played.

### `LateRegistration` (new): the late pass

For replacements of forfeiting players, registering just before or during the edition. `user`, `edition`, `granted_at`, `granted_by` (the organiser, a `User`, set by the admin actions), unique on (`user`, `edition`). It is a per-user exemption from the registration window, not a link: registration stays account-first, so the replacement logs in (or claims an invited account) and goes to `/register`. A pass is valid until an organiser deletes the row or the edition's `end_date` has passed (Paris date); it does not bypass the missing-skills check (`not_configured`). Edits stay allowed for as long as the pass is valid, including after the player has been placed in a team: a submission recomputes `Player.rating` and never touches `team`.

## Rating maths

The weighted and global rating move from `registration.py` into one function shared by the CSV import, the endpoint and the recalculation action, driven by `{identifier: weight}` and the raw global level. It must carry the whole historical rule: weighted = weights-averaged skills clipped to 1..10; if weighted < 4 and the global answer > 4, weighted × 2.5; global rating = `((weighted + 4 × global_level) / 5)` clipped to 1..10, `Player.rating` its rounded value. A test feeds the CSV fixtures and the endpoint the same answers and requires equal ratings.

## API

All views are `IsAuthenticated`, none public, each added to the `PLAYER` list of `test_permissions.py`. `private, no-store` on every response. Errors are stable string codes the front maps to `register.error.*`.

- `GET /registration/`: the latest edition's form: `{year, opens, closes, is_open, reason, dates_confirmed}`, intro, skills month, skills `[{identifier, name_fr, name_en}]`, the active disciplines for the global-level wording, the choice lists, the account email as `{value, editable}` (editable when the account has no usable email, see below), and the caller's saved answers (ratings, `global_level`, frequency, sports, wishes, dietary, tick) if any. 404 `not_a_person` unless the caller `can_register`.
- `PUT /registration/`: body `{ratings: {identifier: 1-10}, global_level, sport_frequency, sports: [{sport, level, practice, duration_months, notes}], team_wishes, dietary_restrictions, attendance_confirmed, email?}`. In one transaction under the user's row lock it update-or-creates the caller's `Player` (keeping any team an organiser assigned) with its `PlayerRating` rows, `global_level`, the private fields and the `PlayerSport` rows, and recomputes `Player.rating`. Refusals: 409 `closed` / `not_yet_open` / `not_configured` (never for a valid late pass but the last); 400 with codes `missing_rating`, `invalid_rating`, `invalid_global_level`, `missing_frequency`, `invalid_frequency`, `invalid_sport`, `too_many_sports`, `too_long`, `attendance_required`, `no_email`, `invalid_email`. Throttled by a `registration` scope (`UserRateThrottle`, `REGISTRATION_THROTTLE_RATE`, default `30/hour`, so CI needs no new variable).
- `DELETE /registration/`: soft-deletes the caller's `Player` (`is_active` off) while open or under a valid late pass; 409 `closed` afterwards. **Answers are kept** and restored if the person registers again (decision: no clearing on withdrawal; a known retention limit).
- **Usable email:** an address at `olympicwarriors.com` (the importer's `FALLBACK_EMAIL_DOMAIN` placeholder) or an empty one counts as no email, here and in the form's pre-fill. With no usable email the form shows an empty required email field and `PUT` takes `email`, validated like `change_email` (stripped, lower-cased) and saved to the account in the same transaction, with no password asked (there is no real address to protect). With a usable email it is shown read-only, changed only through `/account`.
- `/me/` gains `can_register` (a person, or invited), read from the profile row it already joins, so `ME_QUERIES` stays 2. The front's `me` payload carries it.
- `GET /registration/` also returns `suggested` for a caller with no registration in this edition: the sports table, sport frequency and dietary restrictions of their most recent previous `Player` (a withdrawn one included). Ratings, global level, team wishes and the tick are never suggested. Nothing is saved until they submit.

## Organisers (admin)

- `EditionAdmin`: window dates and the state beside them, intro and month texts, `dates_confirmed`, the skills inline, the two actions above, in an « Inscription » fieldset.
- `PlayerAdmin`: columns and filters for « confirmé » and « restrictions alimentaires », a `PlayerSport` inline, the private fields visible there only.
- **Late pass:** an action « Autoriser l'inscription tardive » on `PlayerAdmin` and `UserProfileAdmin` (for the latest edition; permission: change on `Player`) creates the `LateRegistration` rows with `granted_by` set to the organiser and reports who already had one. A `LateRegistration` admin lists and deletes them (revocation), filtered by edition. The action also works for an invited user with no `Player`, so a replacement newcomer needs no extra step.
- **Invitations:** a custom admin page (a button on the user changelist, needing `auth.add_user` and `auth.change_user`), not a selection action, with two modes: a form for one user (first name, last name, email) and a bulk textarea (one `Prénom Nom, email` per line). Per line:
  - a real email matching an existing user reuses that user;
  - otherwise a username match (derived as the importer derives it, accents kept) is reused only when the existing user's email is a placeholder or empty, or equal to the pasted one; a placeholder email is replaced by the pasted real one;
  - a username match with a different real email is a **conflict**: skipped and reported, nothing created, no link;
  - no match creates a user with a random password and `invited=True`.
  - A claim link is returned (in Django messages, never logged) for every created or reused user, **including one whose `claimed_at` is set**; that line carries a warning that using the link resets the password they chose.
  - A checkbox « Inscription tardive » grants the pass to every created or reused user of the paste in the same action; the report then adds the `/register` address to send with the link.
  - Malformed lines and duplicates inside the paste are reported, not created. The rest of the paste is processed whatever a line does.

## Front

- `/register` (`NO_TAB_BAR`): a visitor or a dead token goes to `/login?next=/register`. The form has a stepper per skill (1-10), the generated global-level question, the email (read-only, or an editable field when there is no usable one), the frequency choice, a sports table (add and remove rows; columns sport, level, practice, years and months, notes), team wishes, dietary restrictions and the required tick. A line states « Ton nom apparaîtra dans la liste des joueurs » (registering makes the person visible on the public leaderboard at once, with no rank; the form says so) and another the retention: « Tes réponses sont conservées tant que ton compte existe, et visibles des organisateurs seulement ». A returning player's sports table, frequency and dietary field start filled from `suggested`, with a line « Repris de ton inscription 2026, vérifie qu'il est à jour ». Closed, not-yet-open and not-configured states explain themselves with the dates; under a late pass the form works and a note says it is a late registration. A saved registration shows an « Enregistré » state with edit and withdraw.
- **Invited newcomers (can register, not a person):** a claim sends an invited non-person to `/register` instead of `/players/<id>`; `/account` stays open to them with the photo and showcase sections hidden until they are a person; the header links their name to `/account`.
- **Entry points:** a header link to `/register` for any caller who can register (shown even outside the window, where it explains the state), and a « S'inscrire à l'édition 2027 » call to action on the hub (`EditionHub`) and `/account` while registration is open and the caller has not registered; the hub's load calls `/registration/` only when `me.can_register`. A visitor sees the hub call to action as a link to `/login?next=/register`.
- The hub shows « Dates à venir » while `dates_confirmed` is false.
- The `register` action is a plain POST/`fetch` like the account page's, with the API codes mapped to `register.error.*`. Strings in `fr.js` and `en.js` under `register.*` (parity test).
- All read pages remain public; invited users keep full read access, and appear on the leaderboard only after registering.

## Slice 2 review decisions (Hugo, 2026-10-05)

- **Withdrawal:** `DELETE /registration/` is refused with 409 `has_team` once the player is in a team; the organiser removes them and grants the replacement a late pass.
- **Organiser removal:** `Player.withdrawn_at` is set by a self-withdrawal and cleared by a registration. A save on an inactive row without it answers 409 `removed_by_organiser`, unless the person holds a late pass.
- **Email:** an address another active account already has is refused (`email_taken`) in the placeholder-email case.
- **Invitations:** `UserProfile.invited` is a column, a filter and editable in the profile list (unticking revokes). The paste takes an optional third column `identifiant` (the username, for two people sharing a name). A staff account is flagged invited with no claim link, ever, so an organiser who never played can register.
- **Delivery:** slice 1 merges to `dev` first; slice 2 is rebased on it.

## Privacy

- None of the new `Player` fields nor `PlayerSport` appears in the summary or any public payload; `SummaryPlayerSerializer` keeps its explicit field list and the new keys join `PRIVATE_KEYS` in `test_showcase.py`.
- **Retention:** no purge. The private answers stay while the account exists (decision: Hugo, 2026-10-04), including after the edition and after a withdrawal; the form says so. `deactivate()` (account deletion) clears every new private field and deletes the person's `PlayerSport` rows. Known limitation: dietary notes can be sensitive data, so a purge command (clearing them after the edition, like `refresh_badges --if-due`) is the first follow-up if that changes.
- `transfer.py` does not export the personal fields (`dietary_restrictions`, `team_wishes`, `sport_frequency`, `attendance_confirmed`, `PlayerSport`); `global_level` travels with the rating. `test_transfer.py` lists them.

## CSV import

The importer also stores `global_level`, frequency, team wishes and the confirmation from old CSVs (columns matched by header fragment as today). The free-text sports answer is not parsed into rows: it is kept as one `PlayerSport` row with the text in `notes` and `sport` set to « Historique (import) », or skipped when blank. Optional, slice 1.

## Testing

Django: the shared rating function including the 2.5 rule against the existing CSV fixtures; recalculation (skipping players without a `global_level`, the report counts them) and the seeded weights against 2024- and 2026-shaped synthetic answers; `suggested` from the latest previous `Player`; the endpoints (create, update keeping the team, window and reason edges in Paris time, every error code, withdraw and re-register restoring answers, sports replaced as a set, usable and placeholder email, throttle); skill-set locking; the late pass (window bypass, `not_configured` still refused, expiry at `end_date`, revocation, edit after team placement keeps the team, `granted_by`, the invite checkbox); invitation claimability and the invited claim redirect data; the bulk invite (email reuse, username reuse, placeholder replacement, conflicts, already-claimed warning, duplicates, malformed lines); the three admin actions; query-count constants; `test_permissions.py` entries; the privacy walks; `makemigrations --check`. Front (Vitest): `/register` page and server tests (login redirect, closed states, validation, success, editable email), the hub call to action and « Dates à venir », the header link, the claim redirect, `fr`/`en` parity.

## Rollout, three PRs from `dev`

1. Models, migrations (including the skills seeding and `dates_confirmed`; the `Edition` window and form-text fields wait for slice 2, which reads them), the skills admin with its locking and both actions, the shared rating function, the CSV import changes. No user-visible change except the hub's `dates_confirmed` condition.
2. `invited`, the invite action, `/me/`'s `can_register`, and the registration API.
3. The front `/register` page, the claim redirect, the header link and the calls to action.

Deploy order: server before front, `migrate`, rebuild the image. Create the 2027 edition, set its skills (copy action), then `registration_opens`. `CLAUDE.md` is updated in each PR.
