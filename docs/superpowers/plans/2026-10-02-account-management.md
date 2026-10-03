# Account Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add email password reset and a `/account` page (photo, showcase, email, password, logout, account deactivation with name masking).

**Architecture:** Django views + small modules (`accounts.py`, `anonymity.py`, `password_reset.py`) reuse `claims.py`'s token machinery; a `UserProfile.anonymized` flag masks names in every public payload. The SvelteKit front adds `/account`, `/forgot`, `/reset/[uid]/[token]`; the photo/showcase form actions move to a shared server module used by both the profile and the account pages.

**Tech Stack:** Django 4.2 / DRF 3.15 / pydantic-settings / Postgres; SvelteKit 2 / Svelte 4 / Vitest.

Spec: `docs/superpowers/specs/2026-10-02-account-management-design.md`.

**Rules for every task (from CLAUDE.md and memory):**
- Backend tests: `docker compose exec server python manage.py test olympic_warriors.tests.<module>` (needs the compose stack up). Front tests: `cd front && npm test -- <path>`.
- **Never write to the dev database** from a shell (`manage.py shell` writes, `loaddata`, `import_edition` without `--dry-run`): tests only.
- Do not run implementers in parallel in one checkout (shared git index).
- Commit after each task; end commit messages with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Branch: create `feat/account-management` from `dev` in the main checkout.

All paths below are relative to the repo root. `S` = `server/olympic_warriors`, `F` = `front/src`.

## File structure

| File | Responsibility |
|---|---|
| `S/config.py`, `S/../olympic_warriors/settings.py`, `server/.env.example` | SMTP + throttle settings |
| `S/models/UserProfile.py`, `S/migrations/0040_userprofile_anonymized.py` | `anonymized` flag |
| `S/anonymity.py` (new) | `shown_names(user)` masking helper |
| `S/accounts.py` (new) | password check, email/password change, deactivate |
| `S/password_reset.py` (new) | find the user for an email, send the link |
| `S/throttling.py` | `PasswordCheckThrottle`, `ResetEmailRateThrottle` |
| `S/views.py`, `S/urls.py` | new endpoints; `getMe` gains `email` |
| `S/admin.py` | `anonymized` in `UserProfileAdmin` |
| `F/lib/server/owner-actions.js` (new) | photo/removePhoto/showcase actions shared by two pages |
| `F/routes/account/*` (new) | `/account` page |
| `F/routes/forgot/*`, `F/routes/reset/[uid]/[token]/*` (new) | reset flow pages |
| `F/lib/components/Header.svelte`, `F/routes/+layout.svelte`, `F/routes/login/login.svelte`, `F/routes/players/[id]/+page.svelte` | links |
| `F/lib/i18n/fr.js`, `en.js` | strings |

---

### Task 1: SMTP and throttle settings

**Files:** Modify `S/config.py`, `server/olympic_warriors/settings.py`, `server/.env.example`; Test `S/tests/test_config.py`.

- [ ] **Step 1: Write the failing test.** Append to `S/tests/test_config.py`, inside its existing config test class style (look at how `PHOTO_THROTTLE_RATE` is tested there and mirror it):

```python
    def test_mail_and_account_throttle_defaults(self):
        config = DevConfig()
        self.assertEqual(config.EMAIL_HOST, "")
        self.assertEqual(config.EMAIL_PORT, 587)
        self.assertTrue(config.EMAIL_USE_TLS)
        self.assertEqual(config.DEFAULT_FROM_EMAIL, "Olympic Warriors <noreply@localhost>")
        self.assertEqual(config.PASSWORD_THROTTLE_RATE, "10/hour")
        self.assertEqual(config.RESET_EMAIL_THROTTLE_RATE, "3/hour")
```

- [ ] **Step 2: Run it, expect FAIL** (`AttributeError`): `docker compose exec server python manage.py test olympic_warriors.tests.test_config`.

- [ ] **Step 3: Implement.** In `BaseConfig` after `NUM_PROXIES`:

```python
    # Outgoing mail (password reset). Optional: with no EMAIL_HOST, dev prints mails on the
    # console and prod sends nothing (password_reset logs an error).
    EMAIL_HOST: str = ""
    EMAIL_PORT: int = 587
    EMAIL_HOST_USER: str = ""
    EMAIL_HOST_PASSWORD: str = ""
    EMAIL_USE_TLS: bool = True
    DEFAULT_FROM_EMAIL: str = "Olympic Warriors <noreply@localhost>"
    # Current-password checks per user (PUT /me/email/, PUT /me/password/, POST
    # /me/deactivate/ together), and password-reset mails per address, DRF's rate format.
    PASSWORD_THROTTLE_RATE: str = "10/hour"
    RESET_EMAIL_THROTTLE_RATE: str = "3/hour"
```

In `settings.py`, `DEFAULT_THROTTLE_RATES` add `'password': settings.PASSWORD_THROTTLE_RATE, 'reset_email': settings.RESET_EMAIL_THROTTLE_RATE,` and, after `PUBLIC_URL = settings.PUBLIC_URL`:

```python
# Outgoing mail: SMTP when EMAIL_HOST is set, else the console in dev; in prod without a host
# the SMTP backend is kept so a reset request fails loudly in the log instead of vanishing.
EMAIL_HOST = settings.EMAIL_HOST
EMAIL_PORT = settings.EMAIL_PORT
EMAIL_HOST_USER = settings.EMAIL_HOST_USER
EMAIL_HOST_PASSWORD = settings.EMAIL_HOST_PASSWORD
EMAIL_USE_TLS = settings.EMAIL_USE_TLS
DEFAULT_FROM_EMAIL = settings.DEFAULT_FROM_EMAIL
EMAIL_BACKEND = (
    "django.core.mail.backends.console.EmailBackend"
    if not settings.EMAIL_HOST and os.environ.get("ENV", "dev").lower() == "dev"
    else "django.core.mail.backends.smtp.EmailBackend"
)
```
(Django's test runner swaps in the locmem backend, so tests are unaffected.) Add the same keys, commented, to `server/.env.example`.

- [ ] **Step 4: Run, expect PASS** (same command).
- [ ] **Step 5: Commit** `[FEAT] SMTP and account throttle settings`.

---

### Task 2: `anonymized` flag, `shown_names`, masking of public payloads

**Files:** Modify `S/models/UserProfile.py`, `S/admin.py`, `S/serializer.py` (`SummaryPlayerSerializer`, ~line 240), `S/profiles.py` (lines ~347 and ~549), `S/badges.py` (`_partner`, ~line 1222); Create `S/anonymity.py`, `S/migrations/0040_userprofile_anonymized.py` (generated), `S/tests/test_anonymity.py`.

- [ ] **Step 1: Write the failing tests** in `S/tests/test_anonymity.py`:

```python
"""A deactivated player's name is masked in every public payload (spec 2026-10-02)."""

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from olympic_warriors.anonymity import shown_names
from olympic_warriors.models import Edition, Player, Team, UserProfile


class AnonymitySetup:
    def setUp(self):
        self.edition = Edition.objects.create(
            year=2024, host="Nantes", start_date="2024-09-21", end_date="2024-09-22"
        )
        self.team = Team.objects.create(name="MxM", edition=self.edition)
        self.lea = User.objects.create_user("leamartin", first_name="Léa", last_name="Martin")
        Player.objects.create(user=self.lea, edition=self.edition, team=self.team, rating=5)


class TestShownNames(AnonymitySetup, APITestCase):
    def test_real_names_without_a_profile_or_a_flag(self):
        self.assertEqual(shown_names(self.lea), ("Léa", "Martin"))
        UserProfile.objects.create(user=self.lea)
        self.assertEqual(shown_names(User.objects.get(pk=self.lea.pk)), ("Léa", "Martin"))

    def test_masked_names_when_anonymized(self):
        UserProfile.objects.create(user=self.lea, anonymized=True)
        self.assertEqual(shown_names(User.objects.get(pk=self.lea.pk)), ("Joueur", "anonyme"))


class TestPublicPayloads(AnonymitySetup, APITestCase):
    def setUp(self):
        super().setUp()
        UserProfile.objects.create(user=self.lea, anonymized=True)

    def assertMasked(self, response):
        self.assertEqual(response.status_code, 200)
        text = response.content.decode()
        self.assertNotIn("Léa", text)
        self.assertNotIn("Martin", text)
        self.assertIn("anonyme", text)

    def test_summary_roster(self):
        self.assertMasked(self.client.get("/edition/year/2024/summary/"))

    def test_leaderboard(self):
        self.assertMasked(self.client.get("/profiles/"))

    def test_profile(self):
        self.assertMasked(self.client.get(f"/profile/{self.lea.pk}/"))
```
(Also add a `test_discipline_all_time_and_badge_partner` case mirroring `test_showcase.py`'s world helpers once the three above pass: build a revealed discipline result, anonymize its player, assert the `/discipline/<id>/all-time/` row and a `comrades` partner entry show `("Joueur", "anonyme")`. Reuse `test_profiles.py`'s `DisciplineWorld`/`World` helpers, whichever the file exports.)

- [ ] **Step 2: Run, expect FAIL** (`ImportError: anonymity`).
- [ ] **Step 3: Implement.**

`models/UserProfile.py`, after `claimed_at`:
```python
    # Set when the person deleted their account: login is off and every public payload shows
    # an anonymous name (anonymity.shown_names) while places and badges stay. An organiser
    # reverses it by unticking this and reactivating the user.
    anonymized = models.BooleanField(default=False)
```
`S/anonymity.py`:
```python
"""
The name a public payload shows for a user: the real one, or an anonymous one once the
person deleted their account (UserProfile.anonymized). The real name stays in the database;
only what is served changes, so an organiser can undo it.
"""

ANONYMOUS_NAMES = ("Joueur", "anonyme")


def shown_names(user):
    """(first_name, last_name) to serve for `user`. Reads the loaded `profile` relation, so
    callers that serve many users join it (`select_related("user__profile")`); a missing row
    reads as not anonymized."""
    profile = getattr(user, "profile", None)
    if profile is not None and profile.anonymized:
        return ANONYMOUS_NAMES
    return (user.first_name, user.last_name)
```
Then apply it: in `SummaryPlayerSerializer` replace the two `CharField(source=...)` with
```python
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()

    def get_first_name(self, player):
        return shown_names(player.user)[0]

    def get_last_name(self, player):
        return shown_names(player.user)[1]
```
`profiles.py` ~347: `first_name, last_name = shown_names(user)` before the `PlayerRecord(...)` call and pass them; ~549 same with `shown_names(user)` for `DisciplineRow` (add `"user__profile"` to that query's `select_related` if the all-time query-count test fails). `badges._partner`: `first_name, last_name = shown_names(user)`. Import `from .anonymity import shown_names` in each. `badges.py` ~969 sorts on `user.last_name`; leave it (ordering only, never served).

`admin.py` `UserProfileAdmin`: add `"anonymized"` to `list_display`, `list_filter`, and `fields` (editable: not in `readonly_fields`), and `list_editable = ["photo_locked"]` stays.

Generate the migration: `docker compose exec server python manage.py makemigrations olympic_warriors -n userprofile_anonymized` (expect `0040_userprofile_anonymized.py`).

- [ ] **Step 4: Run** `test_anonymity`, then `test_summary`, `test_profiles`, `test_showcase`, `test_user_profile_admin`; fix any query-count (`SUMMARY_QUERIES`, `LEADERBOARD_QUERIES`, `DISCIPLINE_TABLE_QUERIES`) regressions by adding the missing `select_related("…profile")`, never by loosening the constants. Also run `makemigrations --check --dry-run`.
- [ ] **Step 5: Commit** `[FEAT] anonymized flag and masked names in public payloads`.

---

### Task 3: `accounts.py` and its throttles

**Files:** Create `S/accounts.py`, `S/tests/test_accounts.py`; Modify `S/throttling.py`.

- [ ] **Step 1: Failing tests** (`S/tests/test_accounts.py`):

```python
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.authtoken.models import Token

from olympic_warriors import accounts
from olympic_warriors.models import Edition, Player, Team, UserProfile


class AccountsTests(TestCase):
    def setUp(self):
        edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        team = Team.objects.create(name="MxM", edition=edition)
        self.user = User.objects.create_user(
            "leamartin", email="lea@mail.example", password="old-password-x1",
            first_name="Léa", last_name="Martin",
        )
        Player.objects.create(user=self.user, edition=edition, team=team, rating=5)

    def test_check_password(self):
        self.assertTrue(accounts.password_ok(self.user, "old-password-x1"))
        self.assertFalse(accounts.password_ok(self.user, "nope"))
        self.assertFalse(accounts.password_ok(self.user, None))

    def test_change_email_normalises_and_validates(self):
        accounts.change_email(self.user, "  New@Mail.Example ")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@mail.example")
        with self.assertRaises(ValidationError):
            accounts.change_email(self.user, "not-an-email")

    def test_change_password_rotates_the_token(self):
        old = Token.objects.get(user=self.user).key
        key = accounts.change_password(self.user, "a-brand-new-pass-77")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("a-brand-new-pass-77"))
        self.assertNotEqual(key, old)
        self.assertFalse(Token.objects.filter(key=old).exists())

    def test_change_password_runs_the_validators(self):
        with self.assertRaises(ValidationError):
            accounts.change_password(self.user, "short")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("old-password-x1"))

    def test_deactivate(self):
        profile = UserProfile.objects.create(user=self.user, showcase=["champion"])
        accounts.deactivate(self.user)
        self.user.refresh_from_db()
        profile.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(profile.anonymized)
        self.assertEqual(profile.showcase, [])
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        self.assertTrue(Player.objects.get(user=self.user).is_active)  # history stays
```
(use any valid code of `Badge.Codes` instead of `"champion"` if it differs: check `S/models/Badge.py`).

- [ ] **Step 2: Run, expect FAIL** (no `accounts`).
- [ ] **Step 3: Implement.** `S/accounts.py`:

```python
"""
What a logged-in person does to their own account (spec 2026-10-02): change email or
password after proving the current password, or deactivate. Views check who the caller is
and throttle; the rules live here.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.views.decorators.debug import sensitive_variables
from rest_framework.authtoken.models import Token

from .avatars import remove_photo
from .models import UserProfile


@sensitive_variables("password")
def password_ok(user, password):
    """Whether `password` is the user's current one (a non-string never is)."""
    return isinstance(password, str) and user.check_password(password)


def change_email(user, email):
    """Store the address, stripped and lower-cased. Raises ValidationError(code
    `invalid_email`) for anything that is not an email."""
    email = (email or "").strip().lower() if isinstance(email, str) else ""
    try:
        validate_email(email)
    except ValidationError as error:
        raise ValidationError("invalid email", code="invalid_email") from error
    user.email = email
    user.save(update_fields=["email"])


@sensitive_variables("password")
def change_password(user, password):
    """Set a new password (django's ValidationError with the validators' codes when it is
    refused), replace the DRF token so every older session ends, and return the new key."""
    validate_password(password, user)
    with transaction.atomic():
        user.set_password(password)
        user.save(update_fields=["password"])
        Token.objects.filter(user=user).delete()
        return Token.objects.create(user=user).key


def deactivate(user):
    """Turn the account off and mask the person: no login, no photo, no pins, anonymized.
    Player rows stay, so places and badges remain on the public site."""
    with transaction.atomic():
        locked = get_user_model().objects.select_for_update().get(pk=user.pk)
        profile, _ = UserProfile.objects.get_or_create(user=locked)
        remove_photo(profile)
        profile.refresh_from_db()
        profile.showcase = []
        profile.anonymized = True
        profile.save(update_fields=["showcase", "anonymized", "updated_at"])
        locked.is_active = False
        locked.save(update_fields=["is_active"])
        Token.objects.filter(user=locked).delete()
```
`throttling.py` append:

```python
class PasswordCheckThrottle(UserRateThrottle):
    """The current-password checks of /me/email/, /me/password/ and /me/deactivate/, per
    user, at the "password" rate (PASSWORD_THROTTLE_RATE): every request counts, right or
    wrong, so a stolen session cannot guess the password."""

    scope = "password"


class ResetEmailRateThrottle(SimpleRateThrottle):
    """Reset requests per address ("reset_email" rate), counted whether or not the address
    belongs to anyone, so the 429 reveals nothing. A body without a usable email is not
    counted here (the per-IP login throttle still is)."""

    scope = "reset_email"

    def get_cache_key(self, request, view):
        try:
            email = request.data.get("email") if isinstance(request.data, dict) else None
        except Exception:  # unparsable body
            return None
        if not isinstance(email, str) or not email.strip():
            return None
        return self.cache_format % {"scope": self.scope, "ident": email.strip().lower()}
```
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `[FEAT] accounts module: email, password, deactivate`.

---

### Task 4: `/me/email/`, `/me/password/`, `/me/deactivate/` and `/me/` email

**Files:** Modify `S/views.py`, `S/urls.py`, `S/serializer.py` (`MeSerializer`, ~line 730), `S/tests/test_permissions.py`, `S/tests/test_me.py`; Test `S/tests/test_me_account.py` (new).

- [ ] **Step 1: Failing tests** (`S/tests/test_me_account.py`, reusing `MeSetup`, `PRIVATE_CACHE`, `NOT_A_PERSON` from `test_me.py`; add `password="old-password-x1"` by giving `MeSetup.user()` an optional password: change its `create_user(...)` call to pass `password="old-password-x1"`):

```python
from django.core.cache import cache
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from olympic_warriors.models import UserProfile
from olympic_warriors.tests.test_me import MeSetup, NOT_A_PERSON, PRIVATE_CACHE

GOOD = "old-password-x1"


@PRIVATE_CACHE
class TestAccountEndpoints(MeSetup, APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.login(self.lea)

    def test_me_carries_the_email(self):
        self.assertEqual(self.me()["email"], "leamartin@mail.example")

    def test_email_change(self):
        r = self.client.put("/me/email/", {"password": GOOD, "email": "New@Mail.example"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.lea.refresh_from_db()
        self.assertEqual(self.lea.email, "new@mail.example")

    def test_email_change_refusals(self):
        r = self.client.put("/me/email/", {"password": "wrong", "email": "a@b.co"}, format="json")
        self.assertEqual((r.status_code, r.data), (400, {"error": "wrong_password"}))
        r = self.client.put("/me/email/", {"password": GOOD, "email": "nope"}, format="json")
        self.assertEqual((r.status_code, r.data), (400, {"error": "invalid_email"}))

    def test_password_change_returns_a_new_token(self):
        old = Token.objects.get(user=self.lea).key
        r = self.client.put(
            "/me/password/", {"current": GOOD, "new": "a-brand-new-pass-77"}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.data["token"], old)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {old}")
        self.assertEqual(self.client.get("/me/").status_code, 401)

    def test_password_change_refusals(self):
        r = self.client.put("/me/password/", {"current": "wrong", "new": "a-brand-new-pass-77"}, format="json")
        self.assertEqual((r.status_code, r.data), (400, {"error": "wrong_password"}))
        r = self.client.put("/me/password/", {"current": GOOD, "new": "short"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("password_too_short", r.data["errors"])

    def test_deactivate(self):
        r = self.client.post("/me/deactivate/", {"password": GOOD}, format="json")
        self.assertEqual(r.status_code, 204)
        self.lea.refresh_from_db()
        self.assertFalse(self.lea.is_active)
        self.assertTrue(UserProfile.objects.get(user=self.lea).anonymized)
        self.assertEqual(self.client.get("/me/").status_code, 401)  # token gone

    def test_deactivate_needs_the_password(self):
        r = self.client.post("/me/deactivate/", {"password": "wrong"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.lea.refresh_from_db()
        self.assertTrue(self.lea.is_active)

    def test_not_for_non_persons_or_staff(self):
        for user in (self.olga, self.bea):
            self.login(user)
            for method, path in (("put", "/me/email/"), ("put", "/me/password/"), ("post", "/me/deactivate/")):
                r = getattr(self.client, method)(path, {}, format="json")
                self.assertEqual((r.status_code, r.data), (404, NOT_A_PERSON), (user.username, path))

    def test_the_password_check_is_throttled(self):
        for _ in range(10):
            self.client.put("/me/email/", {"password": "wrong", "email": "a@b.co"}, format="json")
        r = self.client.put("/me/email/", {"password": GOOD, "email": "a@b.co"}, format="json")
        self.assertEqual(r.status_code, 429)
```
Also in `test_permissions.py` add `"me/email/"`, `"me/password/"`, `"me/deactivate/"` to `PLAYER`. Note Chloé (staff and a player) must be refused too: `MeSetup.chloe` is `is_staff`; add a loop case for `self.chloe`, expecting 404 (account endpoints require `is_person` and not staff).

- [ ] **Step 2: Run, expect FAIL** (404s from missing routes).
- [ ] **Step 3: Implement.** In `views.py` imports add `from . import accounts` and `PasswordCheckThrottle`. Add after `setMyShowcase`:

```python
WRONG_PASSWORD = {"error": "wrong_password"}


def _account_body(request):
    """The JSON object of an account request, {} when the body cannot be read."""
    try:
        data = request.data
    except ParseError:
        return {}
    return data if isinstance(data, dict) else {}


def _not_an_account_owner(user):
    """404 response for anyone who is not a non-staff person, else None."""
    if user.is_staff or user.is_superuser or not is_person(user):
        return Response(NOT_A_PERSON, status=404)
    return None


@extend_schema(
    summary="Change the caller's email (current password required)",
    request=inline_serializer(
        "EmailChange", {"password": serializers.CharField(), "email": serializers.EmailField()}
    ),
    responses={
        "200": inline_serializer("EmailChanged", {"email": serializers.EmailField()}),
        "400": OpenApiResponse(description='{"error": "wrong_password" | "invalid_email"}'),
        "404": OpenApiResponse(description="Not a player account"),
        "429": OpenApiResponse(description="Too many password checks"),
    },
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@throttle_classes([PasswordCheckThrottle])
@parser_classes([JSONParser])
@sensitive_variables("password")
def myEmail(request):
    refusal = _not_an_account_owner(request.user)
    if refusal:
        return refusal
    data = _account_body(request)
    password = data.get("password")
    if not accounts.password_ok(request.user, password):
        return Response(WRONG_PASSWORD, status=400)
    try:
        accounts.change_email(request.user, data.get("email"))
    except ValidationError:
        return Response({"error": "invalid_email"}, status=400)
    return Response({"email": request.user.email})


@extend_schema(
    summary="Change the caller's password (current password required); ends every older session",
    request=inline_serializer(
        "PasswordChange", {"current": serializers.CharField(), "new": serializers.CharField()}
    ),
    responses={
        "200": inline_serializer("PasswordChanged", {"token": serializers.CharField()}),
        "400": OpenApiResponse(
            description='{"error": "wrong_password"} or {"errors": [validator codes]}'
        ),
        "404": OpenApiResponse(description="Not a player account"),
        "429": OpenApiResponse(description="Too many password checks"),
    },
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@throttle_classes([PasswordCheckThrottle])
@parser_classes([JSONParser])
@sensitive_variables("password", "new")
def myPassword(request):
    refusal = _not_an_account_owner(request.user)
    if refusal:
        return refusal
    data = _account_body(request)
    if not accounts.password_ok(request.user, data.get("current")):
        return Response(WRONG_PASSWORD, status=400)
    new = data.get("new")
    if not isinstance(new, str) or not new.strip():
        return Response({"errors": ["password_missing"]}, status=400)
    try:
        key = accounts.change_password(request.user, new)
    except ValidationError as error:
        return Response({"errors": [e.code for e in error.error_list]}, status=400)
    return Response({"token": key})


@extend_schema(
    summary="Deactivate the caller's account (current password required)",
    request=inline_serializer("Deactivate", {"password": serializers.CharField()}),
    responses={
        "204": OpenApiResponse(description="Account off, name masked, token deleted"),
        "400": OpenApiResponse(description='{"error": "wrong_password"}'),
        "404": OpenApiResponse(description="Not a player account"),
        "429": OpenApiResponse(description="Too many password checks"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([PasswordCheckThrottle])
@parser_classes([JSONParser])
@sensitive_variables("password")
def deactivateMe(request):
    refusal = _not_an_account_owner(request.user)
    if refusal:
        return refusal
    if not accounts.password_ok(request.user, _account_body(request).get("password")):
        return Response(WRONG_PASSWORD, status=400)
    accounts.deactivate(request.user)
    return Response(status=204)
```
`urls.py` after `me/showcase/`: `path("me/email/", views.myEmail), path("me/password/", views.myPassword), path("me/deactivate/", views.deactivateMe),`. In `getMe` add `"email": user.email,` and in `MeSerializer` `email = serializers.EmailField(allow_blank=True)`. `ME_QUERIES` does not change (the user row is already loaded).

- [ ] **Step 4: Run** `test_me_account`, `test_me`, `test_permissions`, `test_routes`; all pass.
- [ ] **Step 5: Commit** `[FEAT] /me/email, /me/password, /me/deactivate`.

---

### Task 5: password reset (mail, endpoints)

**Files:** Create `S/password_reset.py`, `S/tests/test_password_reset.py`; Modify `S/claims.py` (`claim_link`, `complete_claim`), `S/views.py` (split `claimAccount`), `S/urls.py`, `S/tests/test_permissions.py`.

- [ ] **Step 1: Failing tests** (`S/tests/test_password_reset.py`, reusing `ClaimSetup`, `PRIVATE_CACHE`, `INVALID`, `parts` from `test_claims.py`; give `ClaimSetup.person` an `email` kwarg through `**flags`, e.g. `User.objects.filter(pk=self.lea.pk).update(email="lea@mail.example")` in this test's `setUp`):

```python
import re

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from olympic_warriors.tests.test_claims import ClaimSetup, INVALID, PRIVATE_CACHE, parts

GOOD = "violet-harbour-lantern"


@PRIVATE_CACHE
@override_settings(PUBLIC_URL="https://ow.example")
class TestPasswordReset(ClaimSetup, APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        for user, email in ((self.lea, "lea@mail.example"), (self.staff, "ana@mail.example"),
                            (self.gone, "gone@mail.example"), (self.stranger, "sam@mail.example")):
            user.email = email
            user.save(update_fields=["email"])

    def ask(self, email):
        return self.client.post("/password-reset/", {"email": email}, format="json")

    def test_a_person_gets_a_link(self):
        response = self.ask("LEA@mail.example")
        self.assertEqual((response.status_code, response.data), (200, {}))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["lea@mail.example"])
        link = re.search(r"https://ow\.example/reset/([\w-]+)/([\w-]+)", mail.outbox[0].body)
        self.assertIsNotNone(link)
        uidb64, token = link.groups()
        response = self.client.post(
            f"/password-reset/{uidb64}/{token}/", {"password": GOOD}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.lea.refresh_from_db()
        self.assertTrue(self.lea.check_password(GOOD))

    def test_everyone_else_gets_the_same_answer_and_no_mail(self):
        for email in ("nobody@mail.example", "ana@mail.example", "gone@mail.example",
                      "sam@mail.example", "", None, 5):
            with self.subTest(email=email):
                response = self.ask(email)
                self.assertEqual((response.status_code, response.data), (200, {}))
        self.assertEqual(mail.outbox, [])

    def test_two_users_sharing_an_email_get_nothing(self):
        self.stranger.email = "lea@mail.example"
        self.stranger.save(update_fields=["email"])
        self.ask("lea@mail.example")
        self.assertEqual(mail.outbox, [])

    @override_settings(PUBLIC_URL="")
    def test_no_public_url_no_mail_and_still_200(self):
        self.assertEqual(self.ask("lea@mail.example").status_code, 200)
        self.assertEqual(mail.outbox, [])

    def test_the_address_is_throttled(self):
        for _ in range(3):
            self.assertEqual(self.ask("lea@mail.example").status_code, 200)
        self.assertEqual(self.ask("lea@mail.example").status_code, 429)

    def test_the_reset_link_page_contract(self):
        uidb64, token = parts(self.lea)
        self.assertEqual(self.client.get(f"/password-reset/{uidb64}/{token}/").status_code, 200)
        dead = self.client.get("/password-reset/x/y/")
        self.assertEqual((dead.status_code, dead.data), (404, INVALID))
```
- [ ] **Step 2: Run, expect FAIL** (404 routes).
- [ ] **Step 3: Implement.**
  - `claims.py`: `def claim_link(user, route="claim")` and `return f"{base}/{route}/{uidb64}/{token}"` (docstring: `route` is the front page, `claim` or `reset`). In `complete_claim` change the stamp to `if profile.claimed_at is None: profile.claimed_at = timezone.now(); profile.save(update_fields=["claimed_at", "updated_at"])`.
  - `S/password_reset.py`:

```python
"""
Lost password (spec 2026-10-02): a person gives their email and, if exactly one claimable
person has it, gets a link to the front's /reset page, valid like a claim link. The caller
never learns whether anyone matched, so every outcome here is silent.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail

from .claims import Unclaimable, claim_link

logger = logging.getLogger(__name__)

SUBJECT = "Olympic Warriors : réinitialisation de votre mot de passe"
BODY = (
    "Bonjour {name},\n\n"
    "Vous avez demandé à réinitialiser votre mot de passe. Ouvrez ce lien pour en choisir un "
    "nouveau (valable 7 jours) :\n\n{link}\n\n"
    "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : rien ne change.\n"
)


def user_for_email(email):
    """The one user whose email is `email` (case-insensitive), else None: no match, or
    several, which would let one address reset another person's account."""
    users = list(get_user_model().objects.filter(email__iexact=email.strip())[:2])
    return users[0] if len(users) == 1 else None


def send_reset(email):
    """Mail the reset link when `email` names exactly one claimable person. Returns whether a
    mail was sent; logs, never raises, on a missing PUBLIC_URL or a mail failure."""
    if not isinstance(email, str) or not email.strip():
        return False
    user = user_for_email(email)
    if user is None:
        return False
    try:
        link = claim_link(user, route="reset")
    except Unclaimable:
        return False
    except ImproperlyConfigured:
        logger.error("Password reset requested but PUBLIC_URL is not set: no mail sent")
        return False
    try:
        send_mail(
            SUBJECT,
            BODY.format(name=user.first_name or user.username, link=link),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
    except Exception:  # SMTP down or misconfigured: the caller must not learn it either
        logger.exception("Password reset mail failed")
        return False
    return True
```
  - `views.py`: rename the body of `claimAccount` into `def _claim_response(request, uidb64, token)` (the existing code after the decorators, unchanged), keep `claimAccount` calling it, and add:

```python
@extend_schema(
    summary="Ask for a password-reset mail (always 200: nobody learns which emails exist)",
    request=inline_serializer("ResetRequest", {"email": serializers.EmailField()}),
    responses={"200": OpenApiResponse(description="{}"), "429": OpenApiResponse(description="Throttled")},
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle, ResetEmailRateThrottle])
@parser_classes([JSONParser])
def requestPasswordReset(request):
    try:
        data = request.data
    except ParseError:
        data = {}
    email = data.get("email") if isinstance(data, dict) else None
    send_reset(email)
    return Response({})


@extend_schema(exclude=True)
@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([ClaimRateThrottle])
@parser_classes([JSONParser])
@sensitive_variables("password")
def resetPassword(request, uidb64, token):
    """A reset link: the claim contract (claims.py), reached from the mailed link."""
    return _claim_response(request, uidb64, token)
```
  with imports `from .password_reset import send_reset` and `ResetEmailRateThrottle`. `LoginRateThrottle` counts the POST for every email, so the per-IP bucket also bounds the endpoint.
  - `urls.py`: `path("password-reset/", views.requestPasswordReset), path("password-reset/<str:uidb64>/<str:token>/", views.resetPassword),` near the claim route.
  - `test_permissions.py` `PUBLIC`: add `"password-reset/"` and `"password-reset/<str:uidb64>/<str:token>/"`.

- [ ] **Step 4: Run** `test_password_reset`, `test_claims` (the `claimed_at` change), `test_permissions`, `test_routes`; all pass. Then the whole suite: `docker compose exec server python manage.py test` and `makemigrations --check --dry-run`.
- [ ] **Step 5: Commit** `[FEAT] password reset by email`.

---

### Task 6: share the owner form actions

Refactor with no behaviour change: the profile page's `photo`, `removePhoto` and `showcase` actions become reusable by `/account`.

**Files:** Create `F/lib/server/owner-actions.js`; Modify `F/routes/players/[id]/+page.server.js`; its existing `page.server.test.js` stays unchanged and must keep passing.

- [ ] **Step 1:** In `owner-actions.js` move, verbatim, `FORBIDDEN`, `FAILED`, `PHOTO_CODES`, `statusOf`, `photoError`, `showcaseError`, `PHOTO`, `SHOWCASE`, `asOwner`, `showcaseCodes`, `photoIn` and the three action bodies from the profile's `+page.server.js`, with these changes: export `statusOf`; `asOwner(event, action, token, keys, send, expectedId)` takes the id to match as a parameter (`null` = do not compare, only require a valid token); and export

```js
/**
 * The photo, removePhoto and showcase actions for a page. `expectedId(event)` is the id the
 * page must belong to (the profile's `params.id`), or null for a page that is always the
 * caller's own (/account), where `/me/` only has to answer.
 */
export function ownerActions(expectedId) {
	return { photo: ..., removePhoto: ..., showcase: ... };
}
```
In each action replace `asOwner(event, 'photo', token, PHOTO, send)` by `asOwner(event, 'photo', token, PHOTO, send, expectedId(event))`, and in `asOwner` the id check becomes `if (expectedId !== null && (!Number.isInteger(me?.id) || String(me.id) !== expectedId)) return fail(...)` while still requiring `Number.isInteger(me?.id)`.
- [ ] **Step 2:** `players/[id]/+page.server.js` keeps `load` and ends with `export const actions = ownerActions(({ params }) => params.id);` (imports trimmed to what `load` uses).
- [ ] **Step 3: Run** `cd front && npm test -- src/routes/players`; expected all green, unchanged.
- [ ] **Step 4: Commit** `[REFACTOR] shared owner form actions`.

---

### Task 7: `/account` page

**Files:** Create `F/routes/account/+page.server.js`, `F/routes/account/+page.svelte`, `F/routes/account/page.server.test.js`, `F/routes/account/page.test.js`; Modify `F/lib/i18n/fr.js`, `en.js`, `F/routes/+layout.svelte` (`NO_TAB_BAR`: add `'/account'`).

- [ ] **Step 1: Failing server tests** (`page.server.test.js`, node environment like the profile's; copy its `json`, `vi.mock('$lib/server/urls', ...)` header). Cover: `load` redirects a visitor (no cookie) to `/login` with status 303; `load` returns `{ account, profile }` from `/me/` and `/profile/<id>/` for a person; a `/me/` with `is_staff` or `is_person: false` is a 404. Action tests, each with a `Request` carrying a form and `cookies = { get: () => 't', set: vi.fn(), delete: vi.fn() }`:

```js
it('email sends the password and the address, and returns ok', async () => {
	const fetch = vi.fn(async () => json(200, { email: 'a@b.co' }));
	const form = new FormData(); form.set('password', 'pw'); form.set('email', 'a@b.co');
	const result = await actions.email({ request: new Request('http://x/account?/email', { method: 'POST', body: form }), fetch, cookies });
	expect(fetch.mock.calls[0][0]).toBe('http://api/me/email/');
	expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ password: 'pw', email: 'a@b.co' });
	expect(result).toEqual({ ok: true, action: 'email' });
});
it('email maps wrong_password and invalid_email to dictionary keys', ...) // 400 {error} -> fail(400,{action:'email', error:'account.error.wrong_password'})
it('password refuses a mismatch before calling the API', ...)  // new !== confirmation -> fail(400,{action:'password', error:'account.error.mismatch'}), fetch not called
it('password stores the new token on success', ...) // cookies.set('token', 'new-token', tokenCookieOptions()); result {ok:true, action:'password'}
it('password maps validator codes', ...) // 400 {errors:['password_too_short']} -> errors:['claim.error.password_too_short']
it('deactivate needs the typed word, calls the API, clears the cookie and redirects', ...)
// confirmation 'SUPPRIMER' or 'delete' (case-insensitive, trimmed) passes; anything else -> fail(400,{action:'deactivate', error:'account.error.confirmation'}) with no fetch;
// success -> cookies.delete('token',{path:'/'}) and the action throws redirect 303 to '/'.
```
- [ ] **Step 2: Run, expect FAIL** (no module).
- [ ] **Step 3: Implement `+page.server.js`:**

```js
import { error, fail, redirect } from '@sveltejs/kit';
import { apiGet, apiSend } from '$lib/api';
import { ownerActions } from '$lib/server/owner-actions';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE, tokenCookieOptions } from '$lib/session';

const PASSWORD_CODES = new Set([
	'password_too_short',
	'password_too_common',
	'password_entirely_numeric',
	'password_too_similar',
	'password_missing'
]);
const CONFIRM_WORDS = new Set(['supprimer', 'delete']);

/** The page is the caller's own: a visitor goes to /login, anyone who is not a non-staff person gets a 404. */
export const load = async ({ fetch, cookies }) => {
	const token = cookies.get(TOKEN_COOKIE);
	if (!token) redirect(303, '/login');
	const account = await apiGet(fetch, api('/me/'), token);
	if (account.is_staff || !account.is_person) error(404, 'No such page');
	const profile = await apiGet(fetch, api(`/profile/${account.id}/`));
	return {
		account: { id: account.id, username: account.username, email: account.email ?? '' },
		profile
	};
};

const statusOf = (err) =>
	Number.isInteger(err?.status) && err.status >= 400 && err.status <= 599 ? err.status : 500;

/** Dictionary key of a failed account call: the API's `{error: code}` (in the error message) or a status. */
function accountError(err) {
	const status = statusOf(err);
	if (status === 429) return 'account.error.throttled';
	const code = err?.body?.message;
	if (code === 'wrong_password' || code === 'invalid_email') return `account.error.${code}`;
	return 'account.error.failed';
}

const jsonCall = (event, token, method, path, body) =>
	apiSend(event.fetch, api(path), {
		method,
		token,
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify(body)
	});

export const actions = {
	...ownerActions(() => null),

	email: async (event) => {
		const token = event.cookies.get(TOKEN_COOKIE);
		if (!token) return fail(403, { action: 'email', error: 'account.error.failed' });
		const form = await event.request.formData();
		const password = String(form.get('password') ?? '');
		const email = String(form.get('email') ?? '').trim();
		if (!password || !email) return fail(400, { action: 'email', error: 'account.error.missing' });
		try {
			await jsonCall(event, token, 'PUT', '/me/email/', { password, email });
		} catch (err) {
			return fail(statusOf(err), { action: 'email', error: accountError(err) });
		}
		return { ok: true, action: 'email' };
	},

	password: async (event) => {
		const token = event.cookies.get(TOKEN_COOKIE);
		if (!token) return fail(403, { action: 'password', error: 'account.error.failed' });
		const form = await event.request.formData();
		const current = String(form.get('current') ?? '');
		const next = String(form.get('new') ?? '');
		const confirmation = String(form.get('confirmation') ?? '');
		if (!current || !next) return fail(400, { action: 'password', error: 'account.error.missing' });
		if (next !== confirmation) return fail(400, { action: 'password', error: 'account.error.mismatch' });
		let body;
		try {
			body = await jsonCall(event, token, 'PUT', '/me/password/', { current, new: next });
		} catch (err) {
			const codes = err?.body?.errors;
			if (statusOf(err) === 400 && Array.isArray(codes)) {
				const keys = codes.map((c) => (PASSWORD_CODES.has(c) ? `claim.error.${c}` : 'claim.error.invalid'));
				return fail(400, { action: 'password', errors: [...new Set(keys)] });
			}
			return fail(statusOf(err), { action: 'password', error: accountError(err) });
		}
		if (typeof body?.token !== 'string' || !body.token)
			return fail(502, { action: 'password', error: 'account.error.failed' });
		event.cookies.set(TOKEN_COOKIE, body.token, tokenCookieOptions());
		return { ok: true, action: 'password' };
	},

	deactivate: async (event) => {
		const token = event.cookies.get(TOKEN_COOKIE);
		if (!token) return fail(403, { action: 'deactivate', error: 'account.error.failed' });
		const form = await event.request.formData();
		const password = String(form.get('password') ?? '');
		const word = String(form.get('confirmation') ?? '').trim().toLowerCase();
		if (!CONFIRM_WORDS.has(word)) return fail(400, { action: 'deactivate', error: 'account.error.confirmation' });
		if (!password) return fail(400, { action: 'deactivate', error: 'account.error.missing' });
		try {
			await jsonCall(event, token, 'POST', '/me/deactivate/', { password });
		} catch (err) {
			return fail(statusOf(err), { action: 'deactivate', error: accountError(err) });
		}
		event.cookies.delete(TOKEN_COOKIE, { path: '/' });
		redirect(303, '/');
	}
};
```
- [ ] **Step 4: Run the server tests, expect PASS.**
- [ ] **Step 5: i18n.** Add to `fr.js` (and the same keys, English, to `en.js`: `parity.test.js` enforces it):

```js
	'account.title': 'Mon compte',
	'account.edit': 'Modifier mon compte',
	'account.section.photo': 'Photo',
	'account.section.showcase': 'Vitrine de badges',
	'account.section.email': 'Adresse e-mail',
	'account.section.password': 'Mot de passe',
	'account.section.session': 'Session',
	'account.section.danger': 'Supprimer mon compte',
	'account.username': 'Identifiant : {name}',
	'account.photoEdit': 'Changer ma photo',
	'account.showcaseEdit': 'Choisir ma vitrine',
	'account.email': 'Adresse e-mail',
	'account.currentPassword': 'Mot de passe actuel',
	'account.newPassword': 'Nouveau mot de passe',
	'account.newPasswordConfirmation': 'Confirmer le nouveau mot de passe',
	'account.saveEmail': "Enregistrer l'adresse",
	'account.savePassword': 'Changer le mot de passe',
	'account.saved': 'Modifications enregistrées',
	'account.dangerText': 'Votre compte sera désactivé et votre nom masqué sur le site. Vos résultats et badges restent visibles sous « Joueur anonyme ». Un organisateur peut réactiver le compte.',
	'account.confirmWord': 'Tapez SUPPRIMER pour confirmer',
	'account.confirmWordValue': 'SUPPRIMER',
	'account.delete': 'Supprimer mon compte',
	'account.error.wrong_password': 'Mot de passe actuel incorrect',
	'account.error.invalid_email': 'Adresse e-mail invalide',
	'account.error.missing': 'Remplissez tous les champs',
	'account.error.mismatch': 'Les deux mots de passe ne correspondent pas',
	'account.error.confirmation': 'Tapez le mot demandé pour confirmer',
	'account.error.throttled': 'Trop de tentatives : réessayez plus tard',
	'account.error.failed': 'La modification a échoué : réessayez plus tard',
```
English equivalents: `'Edit my account'`, `'Delete my account'`, confirm word `DELETE`, etc. (write all keys; the parity test fails otherwise). Also add to `+layout.svelte`'s `NO_TAB_BAR`: `'/account'`.
- [ ] **Step 6: Failing page test** (`page.test.js`, `renderWith`, `vi.mock('$app/forms', () => ({ enhance: () => ({ destroy() {} }) }))` as other page tests do; build `data` from `$lib/fixtures/players.js`'s `profile`):

```js
it('shows the sections and the username', () => {
	renderWith(Page, { data: { account: { id: 34, username: 'leamartin', email: 'lea@mail.example' }, profile, me: { id: 34, first_name: 'Léa', last_name: 'Martin', photo: null, is_person: true, photo_locked: false } }, form: null });
	expect(screen.getByRole('heading', { name: 'Photo' })).toBeInTheDocument();
	expect(screen.getByLabelText('Email address')).toHaveValue('lea@mail.example');
	expect(screen.getByText('Username: leamartin')).toBeInTheDocument();
	expect(screen.getByRole('button', { name: 'Delete my account' })).toBeInTheDocument();
});
it('shows an action error under its section only', ...) // form {action:'email', error:'account.error.wrong_password'}
it('renders in French', ...) // render(Page, {...}) without renderWith -> 'Adresse e-mail'
```
(Expected English strings must match the `en.js` values you wrote.)
- [ ] **Step 7: Implement `+page.svelte`.** Structure (reuse styles/patterns of the claim and profile pages; plain POST forms except none use `use:enhance`):
  - `<div class="page">` with `Breadcrumb` (`[{label: t('players.title'), href:'/players'}, {label: name, href:'/players/'+profile.id}, {label: t('account.title')}]`).
  - `h1` `account.title`; `p` `account.username`.
  - **Photo** section: `Avatar` large + button `account.photoEdit` opening `PhotoEditor` (copy the `editing`/`camera` wiring and the `<PhotoEditor open photo locked name opener on:close>` block from `players/[id]/+page.svelte`, using `data.me` for `photo`/`photo_locked`).
  - **Showcase** section: `<BadgeCollection {collection} badgeStats progress editable showcase />` exactly as the profile's Badges tab renders it (`collection = badgeCollection(profile.badges ?? [])`).
  - **Email** form `method="POST" action="?/email"`: `email` input (`autocomplete="email"`, label `account.email`, value `data.account.email`), `password` input (`autocomplete="current-password"`, label `account.currentPassword`), button `account.saveEmail`.
  - **Password** form `action="?/password"`: hidden readonly `username` input (password-manager hint), `current` (`current-password`), `new` and `confirmation` (`new-password`), button `account.savePassword`; render `form.errors` (a list of keys) as `<p>`s.
  - **Session**: `<form method="POST" action="/logout"><input type="hidden" name="redirectTo" value="/" /><button>{t('account.logout')}</button></form>`.
  - **Danger zone**: `<form method="POST" action="?/deactivate">` with `account.dangerText`, a `confirmation` input labelled `account.confirmWord` (placeholder `account.confirmWordValue`), `password` input, a `.danger` button `account.delete`.
  - Each section shows `{#if form?.action === 'x'}` its `form.error` (`role="alert"`) or, for `form.ok`, `account.saved` (`role="status"`). The `photo`/`removePhoto`/`showcase` results are handled by `PhotoEditor`/`BadgeCollection` as on the profile.
  - Styles: tokens only (`--line`, `--loss` for the danger button border/text, `--accent`), `.page` wrapper, sections as bordered `--bg-raised` blocks, inputs styled like the claim page's underlined fields.
- [ ] **Step 8: Run** `cd front && npm test -- src/routes/account src/lib/i18n` then the whole `npm test`; PASS. `npm run build` also succeeds.
- [ ] **Step 9: Commit** `[FEAT] /account page`.

---

### Task 8: links to `/account`

**Files:** Modify `F/lib/components/Header.svelte`, `F/lib/components/Header.test.js`, `F/routes/players/[id]/+page.svelte`, its `page.test.js`, `F/lib/i18n/fr.js`/`en.js`.

- [ ] **Step 1: Failing tests.** In `Header.test.js`, find the existing test asserting the account pill's link to `/players/<id>` (named `Léa · Mon profil`) and change it: the link's `href` is `/account` and its name `Léa · Mon compte` (English: `Léa · My account`). In the profile's `page.test.js` add: an owner sees a link named `Edit my account` with `href="/account"`; a visitor and another person's view do not.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** `Header.svelte`: `href="/account"` on the `.who` link; `accountName` uses new key `account.myAccount` (`fr` `Mon compte`, `en` `My account`; keep `account.profile` if still used elsewhere, else leave it). Profile `+page.svelte`: inside the `{#if owner}` area near the identity (below the position, next to the showcase hint), add `<a class="quiet-link" href="/account">{t('account.edit')}</a>`.
- [ ] **Step 4: Run** `npm test`; PASS.
- [ ] **Step 5: Commit** `[FEAT] header and profile link to /account`.

---

### Task 9: `/forgot` and `/reset/[uid]/[token]`

**Files:** Create `F/routes/forgot/+page.server.js`, `+page.svelte`, `page.server.test.js`, `page.test.js`; `F/routes/reset/[uid]/[token]/+page.server.js`, `+page.svelte`, `page.server.test.js`, `page.test.js`; Modify `F/routes/login/login.svelte` (link), `F/routes/+layout.svelte` (`NO_TAB_BAR`: `'/forgot'`, `'/reset/[uid]/[token]'`), i18n files.

- [ ] **Step 1: Failing tests for `/forgot`** (`page.server.test.js`):

```js
it('posts the email with the visitor address and always shows the neutral state', async () => {
	const fetch = vi.fn(async () => json(200, {}));
	const form = new FormData(); form.set('email', 'lea@mail.example');
	const result = await actions.request({ request: new Request('http://x/forgot', { method: 'POST', body: form }), fetch, getClientAddress: () => '203.0.113.9' });
	expect(fetch.mock.calls[0][0]).toBe('http://api/password-reset/');
	expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ email: 'lea@mail.example' });
	expect(fetch.mock.calls[0][1].headers['x-forwarded-for']).toBe('203.0.113.9');
	expect(result).toEqual({ sent: true });
});
it('refuses an empty email without calling the API', ...) // fail(400, { error: 'forgot.error.missing' })
it('maps a 429 to login.throttled and any other failure to the neutral state', ...)
```
(Header name: check `forwardedFor` in `$lib/server/forwarded-for.js` and assert what it returns.)
- [ ] **Step 2: Implement `forgot/+page.server.js`:**

```js
import { fail } from '@sveltejs/kit';
import { apiPost } from '$lib/api';
import { forwardedFor } from '$lib/server/forwarded-for';
import { api } from '$lib/server/urls';

export const actions = {
	/** Ask for a reset mail. Whatever the API says but 429, the page shows the same
	 *  confirmation: it must not reveal which emails exist, and the API does not either. */
	request: async ({ request, fetch, getClientAddress }) => {
		const email = String((await request.formData()).get('email') ?? '').trim();
		if (!email) return fail(400, { error: 'forgot.error.missing' });
		try {
			await apiPost(fetch, api('/password-reset/'), { email }, null, forwardedFor(getClientAddress));
		} catch (err) {
			if (err?.status === 429) return fail(429, { error: 'login.throttled' });
		}
		return { sent: true };
	}
};
```
`forgot/+page.svelte`: a form like the login's (one centred column, underlined input), `h1` `forgot.title`, input `email` (`type="email"`, `autocomplete="email"`), button `forgot.submit`; when `form?.sent` replace the form by `<p role="status">{t('forgot.sent')}</p>`; show `form.error` with `role="alert"`; a link back to `/login`. Page test: renders the form, shows the sent message for `form={{sent:true}}`, shows the error key text; one French test.
- [ ] **Step 3: `/reset/[uid]/[token]`.** Copy `routes/claim/[uid]/[token]/+page.server.js` and `+page.svelte` and their two test files into the new folder, then change: API path `/password-reset/${uid}/${token}/` (rename `claimPath` → `resetPath`), the action named `reset` (form `action="?/reset"`), the success redirect `redirect(303, '/')` after storing the token (the person lands home logged in; the `user_id` is not needed), copy keys `claim.*` → `reset.*` for title/greeting/submit/invalidLink only (reuse `claim.error.*`, `claim.password`, `claim.confirmation`, `claim.username`, `claim.copy*` keys unchanged), drop nothing else. Keep `cache-control: private, no-store`, the `LINK_PART` guard and the referrer meta. Add to the copied tests the changed path/action names and run them. Keys to add (fr/en): `reset.title` « Nouveau mot de passe », `reset.greeting` « Bonjour {name} », `reset.submit` « Changer mon mot de passe », `reset.invalidLink` « Ce lien n'est plus valide : demandez-en un nouveau depuis « Mot de passe oublié ? » », `forgot.title` « Mot de passe oublié », `forgot.email` « Adresse e-mail », `forgot.submit` « Envoyer le lien », `forgot.sent` « Si cette adresse correspond à un compte, un lien vient d'être envoyé. Pensez à vérifier vos courriers indésirables. », `forgot.error.missing` « Saisissez votre adresse e-mail », `login.forgot` « Mot de passe oublié ? » (+ English).
- [ ] **Step 4: Login link.** In `login/login.svelte` add `<a class="quiet-link" href="/forgot">{t('login.forgot')}</a>` below the submit button; add a case to `login.test.js` asserting the link name and `href`.
- [ ] **Step 5: `NO_TAB_BAR`** gets `'/forgot'` and `'/reset/[uid]/[token]'`.
- [ ] **Step 6: Run** `cd front && npm test && npm run build`; PASS.
- [ ] **Step 7: Commit** `[FEAT] forgot and reset password pages`.

---

### Task 10: documentation and deploy notes

**Files:** Modify `CLAUDE.md`, `docker-compose.prod.example.yml` (comment only), `docs/superpowers/specs/2026-10-02-account-management-design.md`.

- [ ] **Step 1:** Update the spec: in « Front → `/account` » replace « the visitor lands on `/` with a notice » with « lands on `/` (no notice) ».
- [ ] **Step 2:** In `CLAUDE.md`: Backend architecture's API paragraph (new public `password-reset/…` routes and the three `/me/` writes, `PasswordCheckThrottle`, `ResetEmailRateThrottle`, `*_THROTTLE_RATE` settings), Player accounts (reset flow, `anonymized`, `shown_names`, `accounts.py`, `password_reset.py`, `/me/` carries `email`, claim stamps `claimed_at` once), Settings (SMTP variables), the deploy sentence (migration `0040`, SMTP variables in prod and stage `prod.env`), and Frontend (routes `/account`, `/forgot`, `/reset/…`, `ownerActions`, header pill target, `NO_TAB_BAR`). Add a comment in `docker-compose.prod.example.yml` listing the SMTP variables on the `server` service. Keep each addition in the file's existing dense style.
- [ ] **Step 3: Full verification** (evidence before claims): `docker compose exec server python manage.py test`, `docker compose exec server python manage.py makemigrations --check --dry-run`, `cd front && npm test && npm run build`; all pass.
- [ ] **Step 4: Commit** `[DOCS] account management in CLAUDE.md`; then follow `finishing-a-development-branch` (PR into `dev`; never open the `dev`→`main` PR unasked).

---

## Self-review against the spec

- SMTP config → Task 1. Reset endpoints, per-IP and per-email throttles, link reuse → Tasks 3, 5. Email/password/deactivate endpoints, password throttle, `/me/` email → Tasks 3, 4. Anonymization flag, admin, masking in summary/profiles/leaderboard/all-time/partners → Task 2. `/account`, header, profile link, forgot/reset pages, login link → Tasks 7–9. Tests per area inside each task; docs/deploy → Task 10.
- Names used consistently: `shown_names`, `accounts.password_ok/change_email/change_password/deactivate`, `send_reset`, `claim_link(user, route=…)`, `ownerActions(expectedId)`, `PasswordCheckThrottle`, `ResetEmailRateThrottle`, `account.error.*` keys.
- Known risk to watch in execution: query-count constants (`SUMMARY_QUERIES`, `LEADERBOARD_QUERIES`, `DISCIPLINE_TABLE_QUERIES`, `PROFILES_QUERIES`) when masking needs the profile join; fix with `select_related`, not by changing constants.
