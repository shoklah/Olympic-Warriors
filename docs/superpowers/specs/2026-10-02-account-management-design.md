# Account management: lost password and `/account` page

Date: 2026-10-02. Extends the player accounts spec (`2026-09-24-player-profile-customization-design.md`).

## Goals

- A player who lost their password can reset it by email.
- A logged-in player has one dedicated page, `/account`, to edit their photo and badge showcase, change their email and password, log out and delete their account.
- Clicking the header's account pill goes to `/account` (it links to the profile today).

## Decisions

- **Reset channel:** email over SMTP, self-service. No organiser fallback beyond the existing claim-link action.
- **Email change:** current password required, new address saved at once, no verification.
- **Account deletion:** disables login and keeps history. The name is masked at display time through a flag, so an organiser can reverse it. No data is erased.
- **Page placement:** new `/account` page. The camera button and « Choisir ma vitrine » stay on the public profile too.
- **Staff:** organisers (`is_staff`/`is_superuser`) have no `/account` and no reset: they keep the Django admin for their own password and email, as with claim links.

## Backend

### SMTP configuration
`config.py` gains optional `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`, mirrored in `.env.example`. `settings.py` uses the SMTP backend when `EMAIL_HOST` is set, else the console backend in dev; in prod without it a reset request logs an error and sends nothing. A deploy never fails on missing mail settings (as `PUBLIC_URL`).

### Password reset
- `POST /password-reset/` (`AllowAny`, `@authentication_classes([])`), body `{email}`. Always answers 200 `{}` whatever happens, so it never reveals which emails exist; an unparsable body is also 200.
- Sends a link `<PUBLIC_URL>/reset/<uidb64>/<token>` only when exactly one active, claimable person (`claims.unclaimable_reason` is `None`) has that email, compared case-insensitively. Several users sharing an email, or none, send nothing.
- Token: `default_token_generator`, same lifetime and invalidation as claim links. Needs an absolute `PUBLIC_URL`, else it logs and sends nothing.
- Throttle: `LoginRateThrottle` bucket per IP (shared with login and claim), plus a per-email limit (`RESET_EMAIL_THROTTLE_RATE`, default `3/hour`, keyed on the lower-cased email, counted whether or not the address exists).
- Completing it reuses `check_claim` and `complete_claim`: `GET`/`POST /password-reset/<uidb64>/<token>/` with the claim view's contract (identical 404 `invalid_link`, validator codes, new DRF token). `claimed_at` is set only if it was empty. The two links are interchangeable on the server; only the page wording differs.

### Account endpoints
All `IsAuthenticated`, for person accounts only (404 `not_a_person` otherwise, staff included), each listed in `test_permissions.py`'s `PLAYER` list.
- `PUT /me/email/` `{password, email}`: checks the current password (400 `wrong_password`), validates the address (400 `invalid_email`) and stores it. Throttled per user on the password check (`PASSWORD_CHECK_THROTTLE_RATE`, default `10/hour`, every attempt counting) so a stolen session cannot guess the password.
- `PUT /me/password/` `{current, new}`: same check and throttle, `validate_password` codes on refusal, then sets the password, replaces the DRF token (every older session ends) and answers `{token}`; the front stores it.
- `POST /me/deactivate/` `{password}`: same check and throttle. In one transaction: `User.is_active=False`, delete the DRF token, `avatars.remove_photo`, clear `showcase`, set `UserProfile.anonymized=True` (row created if missing). Answers 204.
- `GET /me/` gains `email` for its owner only (never in a public payload).

### Anonymization
- `UserProfile.anonymized` (`BooleanField`, default `False`, migration `0040`), editable in `UserProfileAdmin` with the filter and column. Reactivation by an organiser: untick `anonymized`, tick `is_active` on the user, generate a claim link (the password check on deactivation made the old one useless).
- One helper, `display_name(user)`, returns `{"first_name": "Joueur", "last_name": "anonyme"}` (French as the data language) when the profile is anonymized. Every public payload built from a user goes through it: summary rosters, `/profiles/`, `/profile/<id>/`, `/discipline/<id>/all-time/`, badge partners. Photos and showcase are already empty; the front hides initials for an anonymized person through the masked name.
- The person stays on the leaderboard and keeps places and badges (`person_players()` is unchanged). `/profile/<id>/` still answers, with the masked name.
- `test_showcase.py`'s privacy walk gains an anonymized case; the email appears in no payload but `/me/`.

## Front

- **`/account`**: no tab bar (`NO_TAB_BAR`), `cache-control: private, no-store`. A visitor is redirected to `/login`, an organiser or non-person gets a 404. Sections: photo (`PhotoEditor`, reused), showcase (`BadgeCollection` picker, reused with its save action), email form, password form, « Se déconnecter » and a danger zone « Supprimer mon compte » requiring the password and a typed confirmation (`SUPPRIMER`/`DELETE`). Actions are plain POSTs (no `use:enhance`) except the photo/showcase ones already built; after a password change the new token is stored; after deactivation the cookie is cleared and the visitor lands on `/` with a notice.
- **Header**: the account pill links to `/account` (aria name « Mon compte »). Logout button unchanged.
- **Profile**: owner controls stay; a « Modifier mon compte » link is added.
- **`/forgot`**: email form, always the neutral confirmation (« Si cette adresse correspond à un compte, un lien vient d'être envoyé »). `/login` gets « Mot de passe oublié ? ».
- **`/reset/[uid]/[token]`**: the claim page component with `reset.*` wording, same invalid/throttled states, referrer and no-store rules, token regex guard.
- All strings in `fr.js` and `en.js` (parity test); form actions map API codes to `account.error.<code>`.

## Testing

- Backend: reset (known, unknown, duplicate, staff, inactive emails all 200; link sent only in the valid case; token lifecycle; both throttles; no `PUBLIC_URL`; mail outbox), email and password change (wrong password, validators, throttle, token rotation), deactivation (side effects, masked payloads everywhere, leaderboard keeps the person, organiser reactivation), `test_permissions.py`, migration check.
- Front: `/account` page and server actions, `/forgot`, `/reset`, header link, profile link, French rendering of each.

## Deploy

`migrate` (`0040`), set the SMTP variables and `RESET_EMAIL_THROTTLE_RATE` optionally in the prod and stage `prod.env`, rebuild both images, deploy the server before the front, and update CLAUDE.md (Player accounts, API, Frontend).

## Known limitations

- A player with no or a mistyped email cannot self-reset and must ask an organiser for a claim link; the neutral response gives no feedback.
- Email changes are unverified, so a typo silently breaks reset for that player.
- Anonymization is display-level: the real name stays in the database.
