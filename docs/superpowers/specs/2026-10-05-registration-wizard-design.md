# Registration form as three steps, with sliders and split team preferences

Status: design, approved section by section in conversation on 2026-10-05. Builds on `2026-10-04-in-app-registration-design.md` (the form, the API and the data it describes are shipped, #118 to #121).

## Goal

Rework the player's registration form after trying it on the dev stack: the ratings become sliders, the single long page becomes three steps with next and previous buttons and a progress bar, and the one free-text « team wishes » box becomes two (who to be with, who to avoid).

## Decisions

- **Two free-text team fields**, not a list of names and not a player picker: players name friends who have not registered, a family member, « peu importe » (the 2026 answers), and a picker would expose the registrants to every player.
- **`team_wishes` is kept untouched** as the legacy combined text. The CSV import keeps writing it (the form of that year had one question), the admin shows it as « Souhaits d'équipe (ancien format) », and the new form never shows it. Nothing is migrated or guessed.
- **Sliders start at 5** and an untouched slider submits 5 (Hugo's choice). The data cannot tell an untouched 5 from a deliberate one.
- **Steps: gated forward, free backward, free jumping when a registration is saved.**
- **Step names:** « Votre pratique sportive », « Votre niveau », « Demandes supplémentaires ».
- **The organisers read the two fields in the Player admin list** (columns and a search), so a name can be searched across everyone's answers.
- **Notices stay above the progress bar, on every step**; only the edition's intro is step 1's.
- Out of scope: saving a draft between steps (the form is submitted once, at the end), a player picker for the team fields, a CSV export of the wishes, any change to the ratings formula or the questionnaire. **The team builder interface is the next task after this one**; it will read these two fields, which is why they stay separate and plain.

## Server (its own PR, first)

- `Player` gains `team_with` and `team_avoid`: private `TextField`s, blank by default, `MaxLengthValidator(500)` each. One migration, no data change.
- `PUT /registration/` takes `team_with` and `team_avoid` in place of `team_wishes`, validated like the other free texts (`enrolment._text`: optional, stripped, at most 500 characters → `too_long`, a non-string or a NUL byte → `invalid_text`). `GET`'s saved answers return the two fields; `suggested` still never carries them. The validation codes are unchanged. A body that still sends `team_wishes` has it ignored.
- Privacy as for the other private answers: both fields join `PRIVATE_KEYS` (`test_showcase.py`), `transfer.PRIVATE_FIELDS` (excluded from `export_edition`), `accounts.deactivate`'s clearing and the `Player` admin (shown beside the legacy field, which is relabelled).
- The legacy `team_wishes` column is not cleared by a re-registration and not exposed by the API.
- **Player admin list:** `team_with` and `team_avoid` become columns (truncated to about 60 characters; the full text in the player form) and `search_fields` covers both, so typing a name finds everyone who wants to be with that person or avoid them. They sit beside the existing presence and dietary columns.
- Deploy: migrate, server, then front. An older front sending `team_wishes` would have it dropped silently.

## Front (second PR)

**One form, three panels.** A single `<form>` (still a plain POST) holds the three step panels; JavaScript shows one at a time. Without JavaScript all three show stacked in order with one submit button (no « Suivant », no progress bar): it works as a long form, as today. The panels are hidden by CSS from the first paint (only step 1 shows) and a `<noscript>` style block un-hides them all, so a JavaScript visitor never sees the long form flash before hydration. Hidden panels' inputs are still submitted; « Suivant » validates the current step so no required field in a hidden panel can block the final submit.

**Notices.** The saved status, the error list, the late-pass, registered, withdrawn, removed and « Repris de votre inscription » notices sit above the progress bar and stay visible on every step; only the edition's intro text belongs to step 1.

**Progress.** A labelled `nav` above the form reads « Étape 2 sur 3 » with a bar and the three step names (`aria-current="step"`). The bar has a text equivalent. Each step name is a button, enabled according to the navigation rules below.

**Step 1, Votre pratique sportive.** The sport-frequency radios (required) and the sports table (add and remove rows up to 15, years and months), unchanged. The table stays optional.

**Step 2, Votre niveau.** The skills intro, one slider per skill, then the global-level slider with its question. Every slider is a native `<input type="range">`, 1 to 10, step 1, value 5, with its current value shown as a large number beside it and the 1 and 10 ends labelled; arrow keys, Home and End and touch work. It is submitted as before (`rating.<id>`, `global_level`): the API contract for ratings does not change.

**Step 3, Demandes supplémentaires.** Two text areas, « Avec qui souhaitez-vous être ? » (`team_with`) and « Avec qui préférez-vous ne pas être ? » (`team_avoid`), each with the confidentiality hint; the optional dietary restrictions; the email (read-only with a link to `/account`, or the required field when the account has no usable one); the required presence and payment tick; the visibility and retention notices; the final button (« M'inscrire » or « Enregistrer mes réponses »); and, for a registered player, the withdraw button.

**Navigation.**
- « Suivant » checks the current step's required fields and refuses to advance, with a message next to the field: step 1 needs a frequency; step 2 has none (a slider always has a value); step 3 needs the tick and an email when one is asked. Native `checkValidity` / `reportValidity` do the work.
- « Précédent » and a click on an earlier step name always work.
- A player with a saved registration (`registration.registered`) can click any step.
- The last step shows the submit button instead of « Suivant »; the first shows no « Précédent ».
- The step is client state: a reload goes back to step 1 (the form is not saved between steps).

**A refused save.** The page reloads on the step of the first error, with the whole error list still shown above the form and everything typed kept: `missing_frequency`, `invalid_frequency`, `invalid_sport`, `too_many_sports` → step 1; `missing_rating`, `invalid_rating`, `invalid_global_level` → step 2; every other code (texts, email, the tick, `email_taken`) and any single `error` (closed, removed, throttled, failed) → step 3. A refused withdrawal shows on step 3.

**Closed registration.** Unchanged: the notice and the read-only summary, which lists both team fields (« Avec » and « À éviter »).

**Accessibility.** The progress `nav` is labelled « Étapes de l'inscription ». Focus moves to the step's heading when the step changes. A panel not shown is `hidden` (out of the accessibility tree), not just invisible. Every slider has a visible label and a value output tied to it with `aria-describedby`; « Suivant » errors sit in a `role="alert"` by the failing field. No slide animation under `prefers-reduced-motion`. Tokens only for colours.

**Pure module.** `$lib/registration.js`: `valuesFromForm`, `bodyFromValues`, `initialValues` carry `team_with` and `team_avoid` instead of `team_wishes`; a new `stepOfErrors(codes)` maps API codes to a step (1 to 3); `RATING_DEFAULT = 5` is the one place the default lives. Dictionaries gain the step names, the slider and navigation strings, the two team labels and hints (`register.*`, both languages).

## Tests

Server: `enrolment` validation of the two fields (blank, stripped, 500, 501, NUL, non-string), the save and the answers payload, the privacy walk, the export exclusion, deactivation clearing, the admin (the legacy label, the two columns, a search for a name found in either field), the migration. Front: the pure module (the form model, the body, `stepOfErrors`), the component (the three steps, gated forward and free backward, free jumping when saved, the first-error step, the sliders: default 5, value shown and submitted, keyboard; both team fields; the no-JS stacked rendering through the server-rendered markup; the summary with both fields; French), and the route's actions. The dev stack is walked again in the browser on the smoke edition, since the previous form bug only showed there.

## Rollout, two PRs

1. Server: the two fields, API, privacy, admin, migration.
2. Front: the steps, the sliders, the two fields, the dictionaries, `CLAUDE.md`. The smoke seed (`seed_upcoming.py`) is updated to the new fields.
