# In-app registration, slice 2: window, invitations, late pass and API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Never write to the development database from a script or `manage.py shell`**; tests use the throwaway test database only.

**Goal:** The server half of the in-app registration (spec: `docs/superpowers/specs/2026-10-04-in-app-registration-design.md`): the open/closed rule with its late pass, invited newcomers, the `/registration/` API, the admin tools to open registration, invite people and grant late passes, and the account-deletion clearing that slice 1 left open.

**Architecture:** Small plain modules next to the existing ones (`registration_state.py` for the window rule, `enrolment.py` for validating, saving and presenting an answer, `invitations.py` for the bulk invite), one function view `myRegistration` wired like the other `/me/*` views, admin additions in `admin.py` plus two admin templates. Slice 1's `questionnaire.py`, `registration.rate` and the `RegistrationSkill`/`Player`/`PlayerSport` models are the base.

**Tech Stack:** Django 4.2 + DRF (+ drf-spectacular), PostgreSQL via `docker compose`, Django admin templates.

**Prerequisite:** slice 1 (`feat/registration-foundations`, pushed) is the base of this branch. Its migrations are `0041` and `0042`; this slice adds `0043`.

**Out of this slice (slice 3):** the SvelteKit pages (`/register`, header link, hub call to action, claim redirect, the account page for invited users). The API contract below is what slice 3 builds on.

**Two conventions for every test in this plan:**
- Create editions with `datetime.date` values (`start_date=date(2027, 9, 18)`), never strings: the registration rule does date arithmetic on an instance that was not reloaded from the database.
- A shorthand used throughout: `T=docker compose exec -T server python manage.py test`, run from the repo root with the compose stack up.

---

## File Structure

| File | Responsibility |
|---|---|
| `server/olympic_warriors/models/Edition.py` (modify) | Six registration window / text fields. |
| `server/olympic_warriors/models/UserProfile.py` (modify) | `invited`. |
| `server/olympic_warriors/models/LateRegistration.py` (create), `models/__init__.py` (modify) | The late pass. |
| `server/olympic_warriors/migrations/0043_registration_window.py` (generated) | Schema. |
| `server/olympic_warriors/registration_state.py` (create) | Is registration open for this edition and user, and why not. |
| `server/olympic_warriors/claims.py` (modify) | `can_register`; claim and reset accept invited users. |
| `server/olympic_warriors/accounts.py` (modify) | `deactivate` clears the private answers. |
| `server/olympic_warriors/enrolment.py` (create) | Validate, save, withdraw and present a registration. |
| `server/olympic_warriors/views.py`, `urls.py`, `serializer.py`, `throttling.py`, `config.py`, `settings.py` (modify) | `/registration/`, `/me/`'s `can_register`, the throttle. |
| `server/olympic_warriors/invitations.py` (create) | The bulk invite logic. |
| `server/olympic_warriors/admin.py` (modify), `templates/admin/olympic_warriors/userprofile/*.html` (create) | Edition fields and status, the late pass, `LateRegistration` admin, the invite page. |
| `server/olympic_warriors/transfer.py` (modify) | `LateRegistration` is not exported. |
| Tests | `test_registration_window.py`, `test_registration_state.py`, `test_invited.py`, `test_deactivate_private_answers.py`, `test_enrolment.py`, `test_registration_api.py`, `test_late_pass_admin.py`, `test_invitations.py`, `test_invite_admin.py` (all new); `test_permissions.py` (modify). |
| `CLAUDE.md` (modify) | Document it. |

---

### Task 0: Branch and baseline

- [ ] **Step 1: Cut the branch from slice 1**

```bash
git switch feat/registration-foundations
git switch -c feat/registration-api
```

- [ ] **Step 2: Baseline**

```bash
docker compose exec -T server python manage.py test olympic_warriors.tests.test_me olympic_warriors.tests.test_claims olympic_warriors.tests.test_permissions olympic_warriors.tests.test_accounts
```

Expected: `OK`.

---

### Task 1: Window fields, `invited`, `LateRegistration`

**Files:**
- Modify: `server/olympic_warriors/models/Edition.py`, `models/UserProfile.py`, `models/__init__.py`, `transfer.py`
- Create: `server/olympic_warriors/models/LateRegistration.py`, `migrations/0043_registration_window.py` (generated)
- Test: `server/olympic_warriors/tests/test_registration_window.py`

- [ ] **Step 1: Write the failing tests.** Create `tests/test_registration_window.py`:

```python
"""The registration window fields, the invited flag and the late pass."""
from datetime import date

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from olympic_warriors.models import Edition, LateRegistration, UserProfile


def make_edition(year=2027):
    return Edition.objects.create(
        year=year, host="Paris", start_date=date(year, 9, 18), end_date=date(year, 9, 19)
    )


class TestEditionWindowFields(TestCase):
    def test_defaults_close_the_registration(self):
        edition = make_edition()

        self.assertIsNone(edition.registration_opens)
        self.assertIsNone(edition.registration_closes)
        self.assertEqual(edition.registration_intro_fr, "")
        self.assertEqual(edition.registration_intro_en, "")
        self.assertEqual(edition.skills_month_fr, "")
        self.assertEqual(edition.skills_month_en, "")


class TestInvited(TestCase):
    def test_a_profile_is_not_invited_by_default(self):
        profile = UserProfile.objects.create(user=User.objects.create(username="ana"))

        self.assertFalse(profile.invited)


class TestLateRegistration(TestCase):
    def setUp(self):
        self.edition = make_edition()
        self.ana = User.objects.create(username="ana")
        self.orga = User.objects.create(username="orga", is_staff=True)

    def test_one_pass_per_user_and_edition(self):
        LateRegistration.objects.create(user=self.ana, edition=self.edition, granted_by=self.orga)

        with self.assertRaises(IntegrityError), transaction.atomic():
            LateRegistration.objects.create(user=self.ana, edition=self.edition)
        LateRegistration.objects.create(user=self.ana, edition=make_edition(2028))

    def test_it_records_who_and_when_and_survives_its_granter(self):
        late = LateRegistration.objects.create(
            user=self.ana, edition=self.edition, granted_by=self.orga
        )
        self.assertIsNotNone(late.granted_at)

        self.orga.delete()
        late.refresh_from_db()
        self.assertIsNone(late.granted_by)

    def test_it_dies_with_its_user_or_edition(self):
        LateRegistration.objects.create(user=self.ana, edition=self.edition)

        self.ana.delete()
        self.assertEqual(LateRegistration.objects.count(), 0)
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_registration_window`
Expected: ERROR `ImportError: cannot import name 'LateRegistration'`.

- [ ] **Step 3: Add the fields.** In `models/Edition.py`, after the `dates_confirmed` field:

```python
    # The in-app registration (registration_state.py): open from registration_opens, through
    # registration_closes (the day before start_date when blank), and only with a
    # questionnaire. The texts frame the form; the month completes « le niveau que tu auras
    # en … ».
    registration_opens = models.DateField(null=True, blank=True)
    registration_closes = models.DateField(null=True, blank=True)
    registration_intro_fr = models.TextField(blank=True, default="")
    registration_intro_en = models.TextField(blank=True, default="")
    skills_month_fr = models.CharField(max_length=30, blank=True, default="")
    skills_month_en = models.CharField(max_length=30, blank=True, default="")
```

In `models/UserProfile.py`, after `anonymized`:

```python
    # Set by an organiser's invitation: a newcomer with no Player yet may claim an account
    # and register (claims.can_register). Nothing else treats them as a person: that is
    # still someone who played.
    invited = models.BooleanField(default=False)
```

- [ ] **Step 4: Create `models/LateRegistration.py`**

```python
from django.contrib.auth.models import User
from django.db import models


class LateRegistration(models.Model):
    """
    A per-user exemption from an edition's registration window, for the replacement of a
    forfeiting player (registration_state.py). It is valid until it is deleted or the
    edition's end_date has passed. Not exported with an edition (transfer.NOT_EXPORTED):
    it is an organiser's decision about a person, taken on the database it was taken on.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    edition = models.ForeignKey("Edition", on_delete=models.CASCADE)
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "edition"], name="late_registration_unique")
        ]

    def __str__(self) -> str:
        return f"{self.user} ({self.edition.year})"
```

In `models/__init__.py` add `from .LateRegistration import LateRegistration` (after the `RegistrationSkill` import).

- [ ] **Step 5: Keep the transfer test green.** In `transfer.py`, add `"LateRegistration"` to `NOT_EXPORTED` and extend its comment: `LateRegistration` is an organiser's decision about a person on one database.

- [ ] **Step 6: Generate the migration and run the tests**

```bash
docker compose exec -T server python manage.py makemigrations olympic_warriors -n registration_window
docker compose exec -T server python manage.py test olympic_warriors.tests.test_registration_window olympic_warriors.tests.test_transfer
docker compose exec -T server python manage.py makemigrations --check --dry-run
```

Expected: `0043_registration_window.py` with six `Edition` fields, `UserProfile.invited` and the `LateRegistration` model with its constraint, nothing else (stop and report otherwise); tests `OK`; `No changes detected`.

- [ ] **Step 7: Commit**

```bash
git add server/olympic_warriors/models server/olympic_warriors/migrations/0043_registration_window.py server/olympic_warriors/transfer.py server/olympic_warriors/tests/test_registration_window.py
git commit -m "[FEAT] registration window fields, invited flag, late pass model

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The registration state

**Files:**
- Create: `server/olympic_warriors/registration_state.py`
- Test: `server/olympic_warriors/tests/test_registration_state.py`

- [ ] **Step 1: Write the failing tests.** Create `tests/test_registration_state.py`:

```python
"""Whether registration is open: the window, the questionnaire and the late pass."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors.models import Edition, LateRegistration, RegistrationSkill
from olympic_warriors.registration_state import (
    CLOSED,
    LATE_PASS,
    NOT_CONFIGURED,
    NOT_YET_OPEN,
    closing_date,
    registration_state,
)

OPENS = date(2027, 5, 1)
START = date(2027, 9, 18)
END = date(2027, 9, 19)


def make_edition(opens=OPENS, closes=None, skills=True):
    edition = Edition.objects.create(
        year=2027, host="Paris", start_date=START, end_date=END,
        registration_opens=opens, registration_closes=closes,
    )
    if skills:
        RegistrationSkill.objects.create(
            edition=edition, name_fr="Cardio", name_en="Cardio", identifier="CARD", weight=4
        )
    return edition


class TestRegistrationState(TestCase):
    def state(self, edition, today, user=None):
        return registration_state(edition, user, today=today)

    def test_open_from_the_opening_day_inclusive(self):
        edition = make_edition()

        self.assertEqual(self.state(edition, date(2027, 4, 30)).reason, NOT_YET_OPEN)
        self.assertFalse(self.state(edition, date(2027, 4, 30)).is_open)
        self.assertTrue(self.state(edition, OPENS).is_open)
        self.assertEqual(self.state(edition, OPENS).reason, "")

    def test_closes_the_day_before_the_start_by_default(self):
        edition = make_edition()

        self.assertEqual(closing_date(edition), date(2027, 9, 17))
        self.assertTrue(self.state(edition, date(2027, 9, 17)).is_open)
        closed = self.state(edition, date(2027, 9, 18))
        self.assertFalse(closed.is_open)
        self.assertEqual(closed.reason, CLOSED)

    def test_an_explicit_closing_day_is_inclusive(self):
        edition = make_edition(closes=date(2027, 6, 30))

        self.assertTrue(self.state(edition, date(2027, 6, 30)).is_open)
        self.assertEqual(self.state(edition, date(2027, 7, 1)).reason, CLOSED)

    def test_a_fresh_edition_is_closed_until_someone_opens_it(self):
        edition = make_edition(opens=None)

        state = self.state(edition, date(2027, 6, 1))

        self.assertFalse(state.is_open)
        self.assertEqual(state.reason, NOT_CONFIGURED)

    def test_without_a_questionnaire_it_is_never_open(self):
        edition = make_edition(skills=False)

        self.assertEqual(self.state(edition, date(2027, 6, 1)).reason, NOT_CONFIGURED)

    def test_inactive_skills_do_not_count_as_a_questionnaire(self):
        edition = make_edition()
        RegistrationSkill.objects.update(is_active=False)

        self.assertEqual(self.state(edition, date(2027, 6, 1)).reason, NOT_CONFIGURED)


class TestLatePass(TestCase):
    def setUp(self):
        self.edition = make_edition()
        self.ana = User.objects.create(username="ana")
        self.bob = User.objects.create(username="bob")
        LateRegistration.objects.create(user=self.ana, edition=self.edition)

    def test_a_pass_opens_a_closed_registration_for_its_user_only(self):
        during = date(2027, 9, 18)

        ana = registration_state(self.edition, self.ana, today=during)
        bob = registration_state(self.edition, self.bob, today=during)
        anonymous = registration_state(self.edition, None, today=during)

        self.assertEqual((ana.is_open, ana.reason), (True, LATE_PASS))
        self.assertEqual((bob.is_open, bob.reason), (False, CLOSED))
        self.assertEqual((anonymous.is_open, anonymous.reason), (False, CLOSED))

    def test_a_pass_works_before_the_opening_too(self):
        state = registration_state(self.edition, self.ana, today=date(2027, 1, 1))

        self.assertEqual((state.is_open, state.reason), (True, LATE_PASS))

    def test_a_pass_lasts_through_the_end_date_then_expires(self):
        last_day = registration_state(self.edition, self.ana, today=END)
        after = registration_state(self.edition, self.ana, today=date(2027, 9, 20))

        self.assertEqual(last_day.reason, LATE_PASS)
        self.assertEqual((after.is_open, after.reason), (False, CLOSED))

    def test_a_pass_does_not_bypass_a_missing_questionnaire(self):
        RegistrationSkill.objects.all().delete()

        state = registration_state(self.edition, self.ana, today=date(2027, 9, 18))

        self.assertEqual((state.is_open, state.reason), (False, NOT_CONFIGURED))

    def test_a_pass_holder_reports_the_pass_even_inside_the_window(self):
        state = registration_state(self.edition, self.ana, today=date(2027, 6, 1))

        self.assertEqual((state.is_open, state.reason), (True, LATE_PASS))
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_registration_state`
Expected: ERROR `ModuleNotFoundError: olympic_warriors.registration_state`.

- [ ] **Step 3: Implement `registration_state.py`**

```python
"""
Whether registration is open for an edition, and for a given user (spec 2026-10-04).

Open only when the edition has an active questionnaire AND either the caller holds a late
pass (valid through the edition's end_date, Paris), or today is within the window:
registration_opens set and reached, registration_closes not passed (inclusive; the day
before start_date when blank). A freshly created edition has no opening date, so it stays
closed until an organiser sets one. The reason names why it is closed, or `late_pass` when
a pass is what opens it.
"""
from dataclasses import dataclass
from datetime import timedelta

from .models import LateRegistration
from .profiles import paris_today

NOT_CONFIGURED = "not_configured"
NOT_YET_OPEN = "not_yet_open"
CLOSED = "closed"
LATE_PASS = "late_pass"


@dataclass(frozen=True)
class RegistrationState:
    """`is_open`, and `reason`: "" when the window is what opens it, LATE_PASS when a pass
    does, else why it is closed (NOT_CONFIGURED, NOT_YET_OPEN or CLOSED)."""

    is_open: bool
    reason: str = ""


def closing_date(edition):
    """The last day of the window: registration_closes, else the day before the start."""
    return edition.registration_closes or edition.start_date - timedelta(days=1)


def registration_state(edition, user=None, today=None):
    """The state for `edition`, for `user` (None: nobody in particular, so no pass)."""
    today = today or paris_today()
    if not edition.registrationskill_set.filter(is_active=True).exists():
        return RegistrationState(False, NOT_CONFIGURED)
    if (
        user is not None
        and today <= edition.end_date
        and LateRegistration.objects.filter(user=user, edition=edition).exists()
    ):
        return RegistrationState(True, LATE_PASS)
    if edition.registration_opens is None:
        return RegistrationState(False, NOT_CONFIGURED)
    if today < edition.registration_opens:
        return RegistrationState(False, NOT_YET_OPEN)
    if today > closing_date(edition):
        return RegistrationState(False, CLOSED)
    return RegistrationState(True)
```

- [ ] **Step 4: Run the tests**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_registration_state`
Expected: `OK` (11 tests).

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/registration_state.py server/olympic_warriors/tests/test_registration_state.py
git commit -m "[FEAT] registration state: window, questionnaire, late pass

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Invited users can claim, reset and register

**Files:**
- Modify: `server/olympic_warriors/claims.py`, `server/olympic_warriors/views.py` (`getMe`, `_not_an_account_owner`), `server/olympic_warriors/serializer.py` (`MeSerializer`)
- Test: `server/olympic_warriors/tests/test_invited.py`

The person check appears in four places that must now accept an invited newcomer: `unclaimable_reason` (claim link), `unresettable_reason` (lost-password mail), `complete_claim` (stamps `claimed_at`) and `_not_an_account_owner` (the `/me/email/`, `/me/password/`, `/me/deactivate/` views). `/me/photo/` and `/me/showcase/` stay person-only (an invited newcomer has no profile page yet).

- [ ] **Step 1: Write the failing tests.** Create `tests/test_invited.py`:

```python
"""An invited newcomer (no Player yet): they may claim an account, reset a password, use
/account's email and password, and see can_register on /me/; photo and showcase stay for
people only."""
from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from olympic_warriors import claims
from olympic_warriors.claims import (
    INACTIVE,
    NOT_A_PERSON,
    STAFF,
    can_register,
    claim_link,
    unclaimable_reason,
    unresettable_reason,
)
from olympic_warriors.models import Edition, Player, UserProfile
from olympic_warriors.tests.test_me import ME_QUERIES

PRIVATE_CACHE = override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "invited-tests",
        }
    }
)


@PRIVATE_CACHE
@override_settings(PUBLIC_URL="https://ow.example")
class InvitedSetup(APITestCase):
    def setUp(self):
        cache.clear()
        self.edition = Edition.objects.create(
            year=2026, host="Paris", start_date=date(2026, 9, 19), end_date=date(2026, 9, 20)
        )
        self.newcomer = self.user("newbie", invited=True)
        self.plain = self.user("plain")
        self.player = self.user("ana")
        Player.objects.create(user=self.player, edition=self.edition, rating=5)
        self.invited_staff = self.user("boss", invited=True, is_staff=True)
        self.invited_inactive = self.user("gone", invited=True, is_active=False)

    @staticmethod
    def user(username, invited=False, **flags):
        user = User.objects.create(username=username, first_name=username.title(), **flags)
        if invited:
            UserProfile.objects.create(user=user, invited=True)
        return user

    def client_of(self, user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.get_or_create(user=user)[0].key}")
        return client


class TestCanRegister(InvitedSetup):
    def test_a_person_or_an_invited_user(self):
        self.assertTrue(can_register(self.player))
        self.assertTrue(can_register(self.newcomer))
        self.assertFalse(can_register(self.plain))

    def test_an_uninvited_profile_does_not_count(self):
        UserProfile.objects.create(user=self.plain)

        self.assertFalse(can_register(self.plain))


class TestClaimRules(InvitedSetup):
    def test_an_invited_newcomer_is_claimable(self):
        self.assertIsNone(unclaimable_reason(self.newcomer))
        self.assertTrue(claim_link(self.newcomer).startswith("https://ow.example/claim/"))

    def test_the_other_refusals_still_apply_first(self):
        self.assertEqual(unclaimable_reason(self.invited_staff), STAFF)
        self.assertEqual(unclaimable_reason(self.invited_inactive), INACTIVE)
        self.assertEqual(unclaimable_reason(self.plain), NOT_A_PERSON)

    def test_an_invited_newcomer_may_reset_a_lost_password(self):
        self.assertIsNone(unresettable_reason(self.newcomer))
        self.assertEqual(unresettable_reason(self.plain), NOT_A_PERSON)

    def test_claiming_stamps_the_first_activation_for_an_invited_newcomer(self):
        from django.contrib.auth.tokens import default_token_generator

        token = default_token_generator.make_token(self.newcomer)

        key = claims.complete_claim(self.newcomer, token, "violet-harbour-lantern")

        self.assertTrue(key)
        self.assertIsNotNone(UserProfile.objects.get(user=self.newcomer).claimed_at)


class TestMe(InvitedSetup):
    def test_can_register_is_true_for_an_invited_newcomer_and_a_person_only(self):
        for user, expected in ((self.newcomer, True), (self.player, True), (self.plain, False)):
            with self.subTest(user=user.username):
                body = self.client_of(user).get("/me/").json()
                self.assertEqual(body["can_register"], expected)

        self.assertFalse(self.client_of(self.newcomer).get("/me/").json()["is_person"])

    def test_me_stays_at_its_query_budget(self):
        client = self.client_of(self.newcomer)

        with self.assertNumQueries(ME_QUERIES):
            client.get("/me/")


class TestAccountViews(InvitedSetup):
    def test_email_and_password_changes_are_open_to_an_invited_newcomer(self):
        self.newcomer.set_password("old-password-xyz")
        self.newcomer.save()
        client = self.client_of(self.newcomer)

        response = client.put(
            "/me/email/", {"password": "old-password-xyz", "email": "new@ow.example"}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"email": "new@ow.example"})

    def test_photo_and_showcase_stay_for_people(self):
        client = self.client_of(self.newcomer)

        self.assertEqual(client.delete("/me/photo/").status_code, 404)
        self.assertEqual(client.put("/me/showcase/", {"codes": []}, format="json").status_code, 404)
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_invited`
Expected: ERROR `ImportError: cannot import name 'can_register'`.

- [ ] **Step 3: Implement in `claims.py`.** Add after `is_claimable`... first, above `unclaimable_reason`, define:

```python
def can_register(user):
    """Whether `user` may register for an edition and claim an account: a person (an active
    Player in an active edition), or someone an organiser invited who has not played yet.
    One or two queries."""
    return is_person(user) or UserProfile.objects.filter(user=user, invited=True).exists()
```

In `unclaimable_reason`, replace `if not is_person(user):` by `if not can_register(user):` and adjust its docstring (« one query, … » becomes « one or two queries »). In `unresettable_reason`, replace `return None if is_person(user) else NOT_A_PERSON` by `return None if can_register(user) else NOT_A_PERSON`, and add « or an invited newcomer » to its docstring. In `complete_claim`, replace the block

```python
        if is_person(locked):
            profile, _ = UserProfile.objects.get_or_create(user=locked)
```

by

```python
        if can_register(locked):
            profile, _ = UserProfile.objects.get_or_create(user=locked)
```

and update the comment above it: « Only a person or an invited newcomer has a profile: an organiser resetting their password gets no row. »

- [ ] **Step 4: Implement the API side.** In `views.py`: import `can_register` from `.claims` (next to the existing `claims` imports), change `_not_an_account_owner` to

```python
def _not_an_account_owner(user):
    """404 response for anyone who cannot register (not a person, not invited), else None.
    An organiser who plays owns an account like any player (deletion aside, see
    deactivateMe), and so does an invited newcomer; the photo and the showcase stay for
    people only."""
    if not can_register(user):
        return Response(NOT_A_PERSON, status=404)
    return None
```

and in `getMe` add `can_register` to the response dict:

```python
                "is_person": user.is_person,
                "can_register": user.is_person or (profile is not None and profile.invited),
```

In `serializer.py`'s `MeSerializer`, after `is_person`:

```python
    can_register = serializers.BooleanField(
        help_text="A person, or invited by an organiser: may register for the open edition"
    )
```

- [ ] **Step 5: Run the affected suites**

```bash
docker compose exec -T server python manage.py test olympic_warriors.tests.test_invited olympic_warriors.tests.test_me olympic_warriors.tests.test_me_account olympic_warriors.tests.test_claims olympic_warriors.tests.test_password_reset olympic_warriors.tests.test_permissions
```

Expected: `OK`. If an existing test pins `/me/`'s exact keys, add `can_register` to its expectation (never loosen it) and list the change in your report.

- [ ] **Step 6: Commit**

```bash
git add server/olympic_warriors/claims.py server/olympic_warriors/views.py server/olympic_warriors/serializer.py server/olympic_warriors/tests
git commit -m "[FEAT] invited newcomers can claim, reset and use their account

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Account deletion clears the private answers

**Files:**
- Modify: `server/olympic_warriors/accounts.py`
- Test: `server/olympic_warriors/tests/test_deactivate_private_answers.py`

- [ ] **Step 1: Write the failing test.** Create `tests/test_deactivate_private_answers.py`:

```python
"""Deleting an account clears the private registration answers (spec: Privacy)."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors import accounts
from olympic_warriors.models import Edition, Player, PlayerSport


def make_player(edition, username, **answers):
    user = User.objects.create(username=username)
    return Player.objects.create(user=user, edition=edition, rating=6, **answers)


class TestDeactivateClearsAnswers(TestCase):
    def setUp(self):
        self.old = Edition.objects.create(
            year=2026, host="Paris", start_date=date(2026, 9, 19), end_date=date(2026, 9, 20)
        )
        self.new = Edition.objects.create(
            year=2027, host="Paris", start_date=date(2027, 9, 18), end_date=date(2027, 9, 19)
        )
        self.answers = dict(
            global_level=8, dietary_restrictions="Végane", sport_frequency="two_hours",
            team_wishes="Avec Bob", attendance_confirmed=True,
        )

    def test_every_player_row_of_the_person_is_cleared_but_keeps_its_rating(self):
        first = make_player(self.old, "ana", **self.answers)
        second = Player.objects.create(user=first.user, edition=self.new, rating=7, **self.answers)
        PlayerSport.objects.create(player=first, sport="Judo")
        PlayerSport.objects.create(player=second, sport="Tennis")

        accounts.deactivate(first.user)

        for player in (first, second):
            player.refresh_from_db()
            self.assertIsNone(player.global_level)
            self.assertEqual(player.dietary_restrictions, "")
            self.assertEqual(player.sport_frequency, "")
            self.assertEqual(player.team_wishes, "")
            self.assertFalse(player.attendance_confirmed)
        self.assertEqual((first.rating, second.rating), (6, 7))  # places and history stay
        self.assertEqual(PlayerSport.objects.count(), 0)

    def test_another_person_is_untouched(self):
        ana = make_player(self.old, "ana", **self.answers)
        bob = make_player(self.old, "bob", **self.answers)
        PlayerSport.objects.create(player=bob, sport="Judo")

        accounts.deactivate(ana.user)

        bob.refresh_from_db()
        self.assertEqual(bob.dietary_restrictions, "Végane")
        self.assertEqual(bob.global_level, 8)
        self.assertEqual(PlayerSport.objects.count(), 1)
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_deactivate_private_answers`
Expected: FAIL (`8 != None`).

- [ ] **Step 3: Implement.** In `accounts.py`, import `Player, PlayerSport` (`from .models import Player, PlayerSport, UserProfile`) and add inside `deactivate`'s transaction, right after the token deletion line:

```python
        # The registration answers are private personal data: they go with the account. The
        # Player rows stay (rating, team), so places and badges remain.
        Player.objects.filter(user=locked).update(
            global_level=None,
            dietary_restrictions="",
            sport_frequency="",
            team_wishes="",
            attendance_confirmed=False,
        )
        PlayerSport.objects.filter(player__user=locked).delete()
```

Extend the docstring: « …anonymized, and the private registration answers cleared. »

- [ ] **Step 4: Run**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_deactivate_private_answers olympic_warriors.tests.test_accounts olympic_warriors.tests.test_me_account olympic_warriors.tests.test_anonymity`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/accounts.py server/olympic_warriors/tests/test_deactivate_private_answers.py
git commit -m "[FEAT] account deletion clears the private registration answers

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Enrolment: validate, save, withdraw, present

**Files:**
- Create: `server/olympic_warriors/enrolment.py`
- Test: `server/olympic_warriors/tests/test_enrolment.py`

The API contract: the answer body is `{ratings: {identifier: 1-10}, global_level, sport_frequency, sports: [{sport, level, practice, duration_months, notes}], team_wishes, dietary_restrictions, attendance_confirmed, email?}`; a refusal is a list of stable codes, each once, in the order found: `missing_rating`, `invalid_rating`, `invalid_global_level`, `missing_frequency`, `invalid_frequency`, `invalid_sport`, `too_many_sports`, `too_long`, `invalid_text`, `attendance_required`, `no_email`, `invalid_email`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_enrolment.py`:

```python
"""Validating, saving, withdrawing and presenting a registration."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from olympic_warriors import enrolment
from olympic_warriors.enrolment import RegistrationError, usable_email, validate
from olympic_warriors.models import (
    Edition, Player, PlayerRating, PlayerSport, Relay, RegistrationSkill, Team,
)
from olympic_warriors.registration_state import RegistrationState


def make_edition(year=2027):
    return Edition.objects.create(
        year=year, host="Paris", start_date=date(year, 9, 18), end_date=date(year, 9, 19),
        registration_opens=date(year, 1, 1),
    )


def add_skill(edition, identifier, weight, order=0, **kw):
    return RegistrationSkill.objects.create(
        edition=edition, name_fr=f"{identifier} fr", name_en=f"{identifier} en",
        identifier=identifier, weight=weight, order=order, **kw
    )


def good(**changes):
    data = {
        "ratings": {"AAA": 6, "BBB": 6},
        "global_level": 8,
        "sport_frequency": "two_hours",
        "sports": [{"sport": "Judo", "level": "amateur", "practice": "no_longer",
                    "duration_months": 30, "notes": "Ceinture orange"}],
        "team_wishes": "Avec Bob",
        "dietary_restrictions": "Végane",
        "attendance_confirmed": True,
    }
    data.update(changes)
    return data


class Setup(TestCase):
    def setUp(self):
        self.edition = make_edition()
        self.aaa = add_skill(self.edition, "AAA", 1, 0)
        self.bbb = add_skill(self.edition, "BBB", 1, 1)
        self.skills = [self.aaa, self.bbb]
        self.ana = User.objects.create(username="ana", email="ana@example.com")

    def codes(self, data, email_editable=False):
        with self.assertRaises(RegistrationError) as ctx:
            validate(data, self.skills, email_editable)
        return ctx.exception.codes


class TestUsableEmail(TestCase):
    def test_blank_and_placeholder_addresses_are_not_usable(self):
        self.assertFalse(usable_email(""))
        self.assertFalse(usable_email(None))
        self.assertFalse(usable_email("anamartin@olympicwarriors.com"))
        self.assertFalse(usable_email(" AnaMartin@OlympicWarriors.com "))
        self.assertTrue(usable_email("ana@example.com"))


class TestValidate(Setup):
    def test_a_good_answer_is_cleaned(self):
        cleaned = validate(good(team_wishes="  Avec Bob \n"), self.skills, False)

        self.assertEqual(cleaned["ratings"], {"AAA": 6, "BBB": 6})
        self.assertEqual(cleaned["global_level"], 8)
        self.assertEqual(cleaned["team_wishes"], "Avec Bob")
        self.assertEqual(cleaned["sports"][0]["sport"], "Judo")
        self.assertIsNone(cleaned["email"])

    def test_optional_parts_may_be_absent(self):
        data = good()
        for key in ("sports", "team_wishes", "dietary_restrictions"):
            del data[key]

        cleaned = validate(data, self.skills, False)

        self.assertEqual(cleaned["sports"], [])
        self.assertEqual((cleaned["team_wishes"], cleaned["dietary_restrictions"]), ("", ""))

    def test_a_missing_or_invalid_rating(self):
        self.assertEqual(self.codes(good(ratings={"AAA": 6})), ["missing_rating"])
        self.assertEqual(self.codes(good(ratings={"AAA": 6, "BBB": 11})), ["invalid_rating"])
        self.assertEqual(self.codes(good(ratings={"AAA": 6, "BBB": True})), ["invalid_rating"])
        self.assertEqual(self.codes(good(ratings={"AAA": "6", "BBB": 6})), ["invalid_rating"])
        self.assertEqual(self.codes(good(ratings="six")), ["missing_rating"])

    def test_the_global_level(self):
        for bad in (0, 11, "8", None, 7.5, True):
            with self.subTest(bad=bad):
                self.assertEqual(self.codes(good(global_level=bad)), ["invalid_global_level"])

    def test_the_frequency(self):
        self.assertEqual(self.codes(good(sport_frequency="")), ["missing_frequency"])
        self.assertEqual(self.codes(good(sport_frequency=None)), ["missing_frequency"])
        self.assertEqual(self.codes(good(sport_frequency="always")), ["invalid_frequency"])

    def test_sports(self):
        rows = [{"sport": "x"}] * 16
        self.assertEqual(self.codes(good(sports=rows)), ["too_many_sports"])
        self.assertEqual(self.codes(good(sports="judo")), ["invalid_sport"])
        for bad in (
            {"sport": ""}, {"sport": "x" * 81}, {"sport": "Judo", "level": "god"},
            {"sport": "Judo", "practice": "always"}, {"sport": "Judo", "duration_months": -1},
            {"sport": "Judo", "duration_months": "3"}, "Judo",
        ):
            with self.subTest(bad=bad):
                self.assertEqual(self.codes(good(sports=[bad])), ["invalid_sport"])
        self.assertEqual(
            self.codes(good(sports=[{"sport": "Judo", "notes": "x" * 201}])), ["too_long"]
        )

    def test_texts(self):
        self.assertEqual(self.codes(good(team_wishes="x" * 1001)), ["too_long"])
        self.assertEqual(self.codes(good(dietary_restrictions="x" * 501)), ["too_long"])
        self.assertEqual(self.codes(good(team_wishes=5)), ["invalid_text"])
        validate(good(team_wishes="x" * 1000, dietary_restrictions="x" * 500), self.skills, False)

    def test_the_presence_tick_is_required(self):
        self.assertEqual(self.codes(good(attendance_confirmed=False)), ["attendance_required"])
        self.assertEqual(self.codes(good(attendance_confirmed="true")), ["attendance_required"])

    def test_every_problem_is_reported_once_in_order(self):
        codes = self.codes(
            good(ratings={}, global_level=0, sport_frequency="", attendance_confirmed=False)
        )

        self.assertEqual(
            codes,
            ["missing_rating", "invalid_global_level", "missing_frequency", "attendance_required"],
        )

    def test_the_email_is_only_read_when_the_account_has_no_usable_one(self):
        self.assertIsNone(validate(good(email="other@example.com"), self.skills, False)["email"])
        self.assertEqual(
            validate(good(email=" New@Example.com "), self.skills, True)["email"], "new@example.com"
        )
        self.assertEqual(self.codes(good(), email_editable=True), ["no_email"])
        self.assertEqual(self.codes(good(email="  "), email_editable=True), ["no_email"])
        self.assertEqual(
            self.codes(good(email="anamartin@olympicwarriors.com"), email_editable=True),
            ["no_email"],
        )
        self.assertEqual(self.codes(good(email="not an email"), email_editable=True), ["invalid_email"])


class TestSave(Setup):
    def save(self, **changes):
        return enrolment.save(self.ana, self.edition, self.skills, validate(good(**changes), self.skills, False))

    def test_creates_the_player_ratings_and_sports(self):
        player = self.save()

        self.assertEqual((player.user, player.edition, player.is_active), (self.ana, self.edition, True))
        self.assertEqual(player.rating, 8)  # skills 6 and 6, global 8: (6 + 32) / 5 = 7.6
        self.assertEqual(player.global_level, 8)
        self.assertEqual(player.sport_frequency, "two_hours")
        self.assertEqual(player.team_wishes, "Avec Bob")
        self.assertEqual(player.dietary_restrictions, "Végane")
        self.assertTrue(player.attendance_confirmed)
        self.assertIsNone(player.team)
        self.assertEqual(
            sorted(player.playerrating_set.values_list("identifier", "name", "rating")),
            [("AAA", "AAA en", 6.0), ("BBB", "BBB en", 6.0)],
        )
        sport = player.playersport_set.get()
        self.assertEqual((sport.sport, sport.level, sport.practice, sport.duration_months), ("Judo", "amateur", "no_longer", 30))

    def test_a_second_save_updates_in_place_keeps_the_team_and_replaces_the_sports(self):
        first = self.save()
        team = Team.objects.create(name="Red", edition=self.edition)
        Player.objects.filter(pk=first.pk).update(team=team)

        second = self.save(
            ratings={"AAA": 10, "BBB": 2}, global_level=5,
            sports=[{"sport": "Tennis"}, {"sport": "Golf"}],
        )

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(Player.objects.filter(user=self.ana).count(), 1)
        self.assertEqual(second.team, team)
        self.assertEqual(second.rating, 5)  # weighted 6, blend (6 + 20) / 5 = 5.2
        self.assertEqual(PlayerRating.objects.filter(player=second).count(), 2)
        self.assertEqual(
            list(second.playersport_set.values_list("sport", "order")), [("Tennis", 0), ("Golf", 1)]
        )

    def test_a_withdrawn_player_is_reactivated_not_duplicated(self):
        first = self.save()
        enrolment.withdraw(self.ana, self.edition)

        again = self.save()

        self.assertEqual(again.pk, first.pk)
        self.assertTrue(again.is_active)

    def test_it_saves_the_email_when_one_is_given(self):
        user = User.objects.create(username="newbie", email="newbie@olympicwarriors.com")
        cleaned = validate(good(email="real@example.com"), self.skills, True)

        enrolment.save(user, self.edition, self.skills, cleaned)

        user.refresh_from_db()
        self.assertEqual(user.email, "real@example.com")

    def test_inactive_skills_are_not_required_nor_rated(self):
        add_skill(self.edition, "OLD", 5, 2, is_active=False)

        player = self.save()

        self.assertFalse(player.playerrating_set.filter(identifier="OLD").exists())


class TestWithdraw(Setup):
    def test_soft_deletes_and_keeps_the_answers(self):
        player = enrolment.save(self.ana, self.edition, self.skills, validate(good(), self.skills, False))

        self.assertEqual(enrolment.withdraw(self.ana, self.edition), 1)

        player.refresh_from_db()
        self.assertFalse(player.is_active)
        self.assertEqual(player.team_wishes, "Avec Bob")
        self.assertEqual(player.playersport_set.count(), 1)

    def test_withdrawing_twice_or_never_registered_is_fine(self):
        self.assertEqual(enrolment.withdraw(self.ana, self.edition), 0)


class TestPayload(Setup):
    def payload(self, user=None, edition=None, state=None):
        return enrolment.form_payload(
            user or self.ana, edition or self.edition, state or RegistrationState(True)
        )

    def test_the_form(self):
        Relay.objects.create(edition=self.edition)
        self.edition.registration_intro_fr = "Bienvenue"
        self.edition.skills_month_fr = "août"
        self.edition.save()

        body = self.payload()

        self.assertEqual(body["edition"]["year"], 2027)
        self.assertEqual(body["edition"]["opens"], "2027-01-01")
        self.assertEqual(body["edition"]["closes"], "2027-09-17")  # the day before the start
        self.assertTrue(body["edition"]["dates_confirmed"])
        self.assertEqual(body["state"], {"is_open": True, "reason": ""})
        self.assertEqual(body["intro"], {"fr": "Bienvenue", "en": ""})
        self.assertEqual(body["skills_month"], {"fr": "août", "en": ""})
        self.assertEqual(
            body["skills"],
            [
                {"identifier": "AAA", "name_fr": "AAA fr", "name_en": "AAA en"},
                {"identifier": "BBB", "name_fr": "BBB fr", "name_en": "BBB en"},
            ],
        )
        self.assertEqual([c["value"] for c in body["choices"]["frequency"]],
                         ["rare", "monthly", "hour", "two_hours", "four_hours"])
        self.assertEqual([c["value"] for c in body["choices"]["level"]],
                         ["beginner", "amateur", "club", "competition"])
        self.assertEqual([c["value"] for c in body["choices"]["practice"]],
                         ["no_longer", "occasionally", "regularly"])
        self.assertEqual(body["disciplines"], ["Relay"])
        self.assertIsNone(body["registration"])
        self.assertIsNone(body["suggested"])

    def test_the_email_is_read_only_only_when_usable(self):
        self.assertEqual(self.payload()["email"], {"value": "ana@example.com", "editable": False})
        self.ana.email = "ana@olympicwarriors.com"

        self.assertEqual(self.payload()["email"], {"value": "", "editable": True})

    def test_the_saved_answers_of_a_registered_and_of_a_withdrawn_player(self):
        enrolment.save(self.ana, self.edition, self.skills, validate(good(), self.skills, False))

        registered = self.payload()["registration"]
        enrolment.withdraw(self.ana, self.edition)
        withdrawn = self.payload()["registration"]

        self.assertTrue(registered["registered"])
        self.assertFalse(withdrawn["registered"])
        for answers in (registered, withdrawn):
            self.assertEqual(answers["ratings"], {"AAA": 6, "BBB": 6})
            self.assertEqual(answers["global_level"], 8)
            self.assertEqual(answers["sport_frequency"], "two_hours")
            self.assertEqual(answers["team_wishes"], "Avec Bob")
            self.assertEqual(answers["dietary_restrictions"], "Végane")
            self.assertTrue(answers["attendance_confirmed"])
            self.assertEqual(
                answers["sports"],
                [{"sport": "Judo", "level": "amateur", "practice": "no_longer",
                  "duration_months": 30, "notes": "Ceinture orange"}],
            )

    def test_suggestions_come_from_the_latest_previous_registration_only(self):
        old = make_edition(2026)
        older = make_edition(2025)
        Player.objects.create(
            user=self.ana, edition=older, rating=5, dietary_restrictions="Vieux",
            sport_frequency="rare", team_wishes="x", global_level=3,
        )
        previous = Player.objects.create(
            user=self.ana, edition=old, rating=5, dietary_restrictions="Sans gluten",
            sport_frequency="hour", team_wishes="Avec Bob", global_level=7, attendance_confirmed=True,
        )
        PlayerSport.objects.create(player=previous, sport="Tennis", notes="30/1")

        suggested = self.payload()["suggested"]

        self.assertEqual(
            suggested,
            {
                "year": 2026,
                "sport_frequency": "hour",
                "dietary_restrictions": "Sans gluten",
                "sports": [{"sport": "Tennis", "level": "", "practice": "",
                            "duration_months": None, "notes": "30/1"}],
            },
        )

    def test_no_suggestion_once_registered_in_this_edition(self):
        Player.objects.create(user=self.ana, edition=make_edition(2026), rating=5, sport_frequency="hour")
        enrolment.save(self.ana, self.edition, self.skills, validate(good(), self.skills, False))

        self.assertIsNone(self.payload()["suggested"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_enrolment`
Expected: ERROR `ModuleNotFoundError: olympic_warriors.enrolment`.

- [ ] **Step 3: Implement `enrolment.py`**

```python
"""
The in-app registration: validating an answer, storing it, withdrawing and presenting the
form with the caller's saved answers. Views check who the caller is and whether registration
is open; the rules live here (spec 2026-10-04).
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from .accounts import change_email
from .models import Player, PlayerRating, PlayerSport
from .models.Edition import FALLBACK_EMAIL_DOMAIN
from .models.Player import SportFrequency
from .registration import rate
from .registration_state import closing_date

MAX_SPORTS = 15
MAX_SPORT_NAME = 80
MAX_NOTES = 200
MAX_DURATION_MONTHS = 1200
MAX_WISHES = 1000
MAX_DIETARY = 500


class RegistrationError(ValueError):
    """An answer that cannot be stored: `codes` lists every problem once, in the order found."""

    def __init__(self, codes):
        super().__init__(", ".join(codes))
        self.codes = codes


def usable_email(email):
    """A real address: not blank and not the placeholder the importer generates."""
    email = (email or "").strip().lower()
    return bool(email) and not email.endswith(f"@{FALLBACK_EMAIL_DOMAIN}")


def _is_int_between(value, low, high):
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _text(data, key, limit, fail):
    """A free-text answer, stripped; absent or None is blank."""
    raw = data.get(key)
    if raw is None:
        return ""
    if not isinstance(raw, str):
        fail("invalid_text")
        return ""
    raw = raw.strip()
    if len(raw) > limit:
        fail("too_long")
    return raw


def validate(data, skills, email_editable):
    """
    The cleaned answer for `data` (the request body), or RegistrationError listing every
    problem. `skills` are the edition's active RegistrationSkill rows; `email_editable` is
    True when the account has no usable email, which then must come with the answer.
    """
    errors = []

    def fail(code):
        if code not in errors:
            errors.append(code)

    given = data.get("ratings")
    given = given if isinstance(given, dict) else {}
    ratings = {}
    for skill in skills:
        value = given.get(skill.identifier)
        if value is None:
            fail("missing_rating")
        elif _is_int_between(value, 1, 10):
            ratings[skill.identifier] = value
        else:
            fail("invalid_rating")

    global_level = data.get("global_level")
    if not _is_int_between(global_level, 1, 10):
        fail("invalid_global_level")

    frequency = data.get("sport_frequency")
    if frequency in (None, ""):
        fail("missing_frequency")
    elif frequency not in SportFrequency.values:
        fail("invalid_frequency")

    sports = []
    raw_sports = data.get("sports")
    if raw_sports is None:
        raw_sports = []
    if not isinstance(raw_sports, list):
        fail("invalid_sport")
    elif len(raw_sports) > MAX_SPORTS:
        fail("too_many_sports")
    else:
        for row in raw_sports:
            sports.append(_sport(row, fail))

    wishes = _text(data, "team_wishes", MAX_WISHES, fail)
    dietary = _text(data, "dietary_restrictions", MAX_DIETARY, fail)

    if data.get("attendance_confirmed") is not True:
        fail("attendance_required")

    email = None
    if email_editable:
        raw = data.get("email")
        raw = raw.strip().lower() if isinstance(raw, str) else ""
        if not usable_email(raw):
            fail("no_email")
        else:
            try:
                validate_email(raw)
            except ValidationError:
                fail("invalid_email")
            else:
                email = raw

    if errors:
        raise RegistrationError(errors)
    return {
        "ratings": ratings,
        "global_level": global_level,
        "sport_frequency": frequency,
        "sports": sports,
        "team_wishes": wishes,
        "dietary_restrictions": dietary,
        "email": email,
    }


def _sport(row, fail):
    """One cleaned sports row; a row that is not usable is reported and replaced by {}."""
    if not isinstance(row, dict):
        fail("invalid_sport")
        return {}
    name = row.get("sport")
    name = name.strip() if isinstance(name, str) else ""
    if not name or len(name) > MAX_SPORT_NAME:
        fail("invalid_sport")
    level = row.get("level") or ""
    if level not in ("", *PlayerSport.Level.values):
        fail("invalid_sport")
    practice = row.get("practice") or ""
    if practice not in ("", *PlayerSport.Practice.values):
        fail("invalid_sport")
    months = row.get("duration_months")
    if months is not None and not _is_int_between(months, 0, MAX_DURATION_MONTHS):
        fail("invalid_sport")
    notes = row.get("notes")
    if notes is None:
        notes = ""
    if not isinstance(notes, str):
        fail("invalid_sport")
        notes = ""
    notes = notes.strip()
    if len(notes) > MAX_NOTES:
        fail("too_long")
    return {
        "sport": name,
        "level": level,
        "practice": practice,
        "duration_months": months,
        "notes": notes,
    }


def save(user, edition, skills, cleaned):
    """
    Store a validated answer: the caller's Player of this edition (created, or the existing
    row, reactivated if withdrawn, with its team kept), its PlayerRating per skill, the
    sports replaced as a set, and the account email when one was given. One transaction
    under the user's row lock, so two tabs saving at once cannot create two players.
    """
    weights = {skill.identifier: skill.weight for skill in skills}
    _, global_rating = rate(cleaned["ratings"], weights, cleaned["global_level"])
    fields = {
        "rating": round(global_rating),
        "global_level": cleaned["global_level"],
        "dietary_restrictions": cleaned["dietary_restrictions"],
        "sport_frequency": cleaned["sport_frequency"],
        "team_wishes": cleaned["team_wishes"],
        "attendance_confirmed": True,
        "is_active": True,
    }
    with transaction.atomic():
        locked = get_user_model().objects.select_for_update().get(pk=user.pk)
        if cleaned["email"] is not None:
            change_email(locked, cleaned["email"])
        player = _player(locked, edition)
        if player is None:
            player = Player.objects.create(user=locked, edition=edition, **fields)
        else:
            for name, value in fields.items():
                setattr(player, name, value)
            player.save()
        for skill in skills:
            PlayerRating.objects.update_or_create(
                player=player,
                identifier=skill.identifier,
                defaults={
                    "name": skill.name_en,
                    "rating": cleaned["ratings"][skill.identifier],
                    "is_active": True,
                },
            )
        player.playersport_set.all().delete()
        PlayerSport.objects.bulk_create(
            PlayerSport(player=player, order=index, **row)
            for index, row in enumerate(cleaned["sports"])
        )
    return player


def withdraw(user, edition):
    """Soft-delete the caller's Player of the edition (the answers stay, for a re-registration).
    Returns how many rows were switched off."""
    return Player.objects.filter(user=user, edition=edition, is_active=True).update(is_active=False)


def _player(user, edition):
    """The caller's Player of the edition, an active one first, withdrawn or not."""
    return (
        Player.objects.filter(user=user, edition=edition).order_by("-is_active", "id").first()
    )


def _sport_rows(player):
    return [
        {
            "sport": sport.sport,
            "level": sport.level,
            "practice": sport.practice,
            "duration_months": sport.duration_months,
            "notes": sport.notes,
        }
        for sport in player.playersport_set.all()
    ]


def _answers(player):
    """What the caller saved, with `registered` False once withdrawn (answers are kept)."""
    return {
        "registered": player.is_active,
        "ratings": {
            rating.identifier: int(rating.rating)
            for rating in player.playerrating_set.filter(is_active=True)
        },
        "global_level": player.global_level,
        "sport_frequency": player.sport_frequency,
        "sports": _sport_rows(player),
        "team_wishes": player.team_wishes,
        "dietary_restrictions": player.dietary_restrictions,
        "attendance_confirmed": player.attendance_confirmed,
    }


def _suggested(user, edition):
    """The stable answers of the caller's most recent earlier registration, offered as
    defaults: sports, frequency and dietary restrictions. Never ratings, global level,
    wishes or the tick, which change every year."""
    previous = (
        Player.objects.filter(user=user, edition__year__lt=edition.year)
        .order_by("-edition__year", "-is_active", "-id")
        .first()
    )
    if previous is None:
        return None
    return {
        "year": previous.edition.year,
        "sport_frequency": previous.sport_frequency,
        "dietary_restrictions": previous.dietary_restrictions,
        "sports": _sport_rows(previous),
    }


def _choices(enum):
    return [{"value": value, "label": label} for value, label in enum.choices]


def form_payload(user, edition, state):
    """The GET /registration/ body for `user` and `edition` in registration `state`."""
    skills = edition.registrationskill_set.filter(is_active=True)
    player = _player(user, edition)
    return {
        "edition": {
            "year": edition.year,
            "opens": edition.registration_opens.isoformat() if edition.registration_opens else None,
            "closes": closing_date(edition).isoformat(),
            "start_date": edition.start_date.isoformat(),
            "dates_confirmed": edition.dates_confirmed,
        },
        "state": {"is_open": state.is_open, "reason": state.reason},
        "intro": {"fr": edition.registration_intro_fr, "en": edition.registration_intro_en},
        "skills_month": {"fr": edition.skills_month_fr, "en": edition.skills_month_en},
        "skills": [
            {"identifier": s.identifier, "name_fr": s.name_fr, "name_en": s.name_en}
            for s in skills
        ],
        "disciplines": list(
            edition.discipline_set.filter(is_active=True)
            .order_by("id")
            .values_list("name", flat=True)
        ),
        "choices": {
            "frequency": _choices(SportFrequency),
            "level": _choices(PlayerSport.Level),
            "practice": _choices(PlayerSport.Practice),
        },
        "email": {
            "value": user.email if usable_email(user.email) else "",
            "editable": not usable_email(user.email),
        },
        "registration": _answers(player) if player is not None else None,
        "suggested": _suggested(user, edition) if player is None else None,
    }
```

- [ ] **Step 4: Run the tests and fix mismatches that are test-mechanics only.** Run `docker compose exec -T server python manage.py test olympic_warriors.tests.test_enrolment`. Expected: `OK`. If a test fails for a Django-mechanics reason rather than a real defect, adjust the test minimally and list each adjustment in your report.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/enrolment.py server/olympic_warriors/tests/test_enrolment.py
git commit -m "[FEAT] enrolment: validate, save, withdraw and present a registration

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The `/registration/` API

**Files:**
- Modify: `server/olympic_warriors/views.py`, `urls.py`, `throttling.py`, `config.py`, `settings.py`, `tests/test_permissions.py`
- Test: `server/olympic_warriors/tests/test_registration_api.py`

- [ ] **Step 1: Write the failing tests.** Create `tests/test_registration_api.py`:

```python
"""GET, PUT and DELETE /registration/: the caller's registration for the latest edition."""
from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from olympic_warriors.models import (
    Edition, LateRegistration, Player, PlayerRating, RegistrationSkill, Team, UserProfile,
)
from olympic_warriors.throttling import RegistrationRateThrottle

LIMIT = RegistrationRateThrottle().num_requests
NOT_A_PERSON = {"error": "not_a_person"}

PRIVATE_CACHE = override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "registration-tests",
        }
    }
)


def answer(**changes):
    data = {
        "ratings": {"AAA": 6, "BBB": 6},
        "global_level": 8,
        "sport_frequency": "two_hours",
        "sports": [{"sport": "Judo", "level": "amateur"}],
        "team_wishes": "Avec Bob",
        "dietary_restrictions": "",
        "attendance_confirmed": True,
    }
    data.update(changes)
    return data


@PRIVATE_CACHE
class RegistrationSetup(APITestCase):
    def setUp(self):
        cache.clear()
        self.old = Edition.objects.create(
            year=2026, host="Paris", start_date=date(2026, 9, 19), end_date=date(2026, 9, 20)
        )
        self.edition = Edition.objects.create(
            year=2027, host="Lyon", start_date=date(2027, 9, 18), end_date=date(2027, 9, 19),
            registration_opens=date(2020, 1, 1), registration_closes=date(2999, 1, 1),
        )
        for order, identifier in enumerate(("AAA", "BBB")):
            RegistrationSkill.objects.create(
                edition=self.edition, name_fr=identifier, name_en=identifier,
                identifier=identifier, weight=1, order=order,
            )
        self.ana = self.user("ana", email="ana@example.com")  # a person of 2026
        Player.objects.create(user=self.ana, edition=self.old, rating=5, sport_frequency="hour")
        self.newbie = self.user("newbie", email="newbie@olympicwarriors.com")
        UserProfile.objects.create(user=self.newbie, invited=True)
        self.plain = self.user("plain", email="plain@example.com")

    @staticmethod
    def user(username, **kw):
        return User.objects.create(username=username, first_name=username.title(), **kw)

    def client_of(self, user):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.get_or_create(user=user)[0].key}"
        )
        return client

    def close(self):
        Edition.objects.filter(pk=self.edition.pk).update(registration_closes=date(2020, 1, 2))


class TestAccess(RegistrationSetup):
    def test_a_visitor_is_refused(self):
        for method in ("get", "put", "delete"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)("/registration/").status_code, 401)

    def test_someone_who_cannot_register_gets_404(self):
        client = self.client_of(self.plain)

        for method in ("get", "put", "delete"):
            with self.subTest(method=method):
                response = getattr(client, method)("/registration/")
                self.assertEqual((response.status_code, response.json()), (404, NOT_A_PERSON))

    def test_no_edition_at_all(self):
        UserProfile.objects.filter(user=self.newbie).update(invited=True)
        Edition.objects.all().delete()  # ana, a person of 2026 only, would stop being one

        response = self.client_of(self.newbie).get("/registration/")

        self.assertEqual((response.status_code, response.json()), (404, {"error": "no_edition"}))


class TestGet(RegistrationSetup):
    def test_a_person_gets_the_form_of_the_latest_edition(self):
        body = self.client_of(self.ana).get("/registration/").json()

        self.assertEqual(body["edition"]["year"], 2027)
        self.assertEqual(body["state"], {"is_open": True, "reason": ""})
        self.assertEqual([s["identifier"] for s in body["skills"]], ["AAA", "BBB"])
        self.assertEqual(body["email"], {"value": "ana@example.com", "editable": False})
        self.assertIsNone(body["registration"])
        self.assertEqual(body["suggested"]["year"], 2026)
        self.assertEqual(body["suggested"]["sport_frequency"], "hour")

    def test_an_invited_newcomer_gets_it_with_an_editable_email(self):
        body = self.client_of(self.newbie).get("/registration/").json()

        self.assertEqual(body["email"], {"value": "", "editable": True})
        self.assertIsNone(body["suggested"])

    def test_a_closed_registration_still_answers_with_its_reason(self):
        self.close()

        response = self.client_of(self.ana).get("/registration/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], {"is_open": False, "reason": "closed"})

    def test_a_late_pass_is_reported(self):
        self.close()
        LateRegistration.objects.create(user=self.ana, edition=self.edition)

        state = self.client_of(self.ana).get("/registration/").json()["state"]

        self.assertEqual(state, {"is_open": True, "reason": "late_pass"})

    def test_no_store(self):
        response = self.client_of(self.ana).get("/registration/")

        self.assertIn("no-store", response["Cache-Control"])


class TestPut(RegistrationSetup):
    def put(self, user=None, **changes):
        return self.client_of(user or self.ana).put("/registration/", answer(**changes), format="json")

    def test_registers_and_returns_the_form_with_the_saved_answers(self):
        response = self.put()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["registration"]["registered"])
        self.assertEqual(body["registration"]["ratings"], {"AAA": 6, "BBB": 6})
        player = Player.objects.get(user=self.ana, edition=self.edition)
        self.assertEqual(player.rating, 8)
        self.assertEqual(player.global_level, 8)
        self.assertEqual(PlayerRating.objects.filter(player=player).count(), 2)
        self.assertEqual(player.playersport_set.count(), 1)

    def test_an_edit_keeps_the_team(self):
        self.put()
        team = Team.objects.create(name="Red", edition=self.edition)
        Player.objects.filter(user=self.ana, edition=self.edition).update(team=team)

        self.put(team_wishes="Plutôt seule")

        player = Player.objects.get(user=self.ana, edition=self.edition)
        self.assertEqual((player.team, player.team_wishes), (team, "Plutôt seule"))

    def test_an_invited_newcomer_becomes_a_person(self):
        self.assertFalse(self.client_of(self.newbie).get("/me/").json()["is_person"])

        response = self.put(user=self.newbie, email="Real@Example.com")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client_of(self.newbie).get("/me/").json()["is_person"])
        self.newbie.refresh_from_db()
        self.assertEqual(self.newbie.email, "real@example.com")

    def test_a_newcomer_without_a_usable_email_must_give_one(self):
        response = self.put(user=self.newbie)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"errors": ["no_email"]})
        self.assertFalse(Player.objects.filter(user=self.newbie).exists())

    def test_a_usable_email_is_never_overwritten_by_the_form(self):
        self.put(email="hijack@example.com")

        self.ana.refresh_from_db()
        self.assertEqual(self.ana.email, "ana@example.com")

    def test_refusals_list_every_code(self):
        response = self.put(ratings={}, global_level=0, attendance_confirmed=False)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"errors": ["missing_rating", "invalid_global_level", "attendance_required"]},
        )
        self.assertFalse(Player.objects.filter(user=self.ana, edition=self.edition).exists())

    def test_an_unreadable_body_is_a_400_not_a_500(self):
        response = self.client_of(self.ana).put(
            "/registration/", "{not json", content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_closed_registration_answers_409_with_its_reason(self):
        self.close()

        response = self.put()

        self.assertEqual((response.status_code, response.json()), (409, {"error": "closed"}))
        self.assertFalse(Player.objects.filter(user=self.ana, edition=self.edition).exists())

    def test_not_configured_and_not_yet_open(self):
        Edition.objects.filter(pk=self.edition.pk).update(registration_opens=date(2999, 1, 1))
        self.assertEqual(self.put().json(), {"error": "not_yet_open"})
        RegistrationSkill.objects.all().delete()
        self.assertEqual(self.put().json(), {"error": "not_configured"})

    def test_a_late_pass_opens_a_closed_registration(self):
        self.close()
        LateRegistration.objects.create(user=self.ana, edition=self.edition)

        self.assertEqual(self.put().status_code, 200)
        self.assertEqual(self.put(user=self.newbie, email="n@example.com").status_code, 409)

    def test_every_put_counts_against_the_throttle(self):
        for _ in range(LIMIT):
            self.put(ratings={})  # refused, still counted

        response = self.put()

        self.assertEqual(response.status_code, 429)
        # A GET is never limited.
        self.assertEqual(self.client_of(self.ana).get("/registration/").status_code, 200)


class TestDelete(RegistrationSetup):
    def test_withdrawing_keeps_the_answers_and_a_new_put_restores_them(self):
        client = self.client_of(self.ana)
        client.put("/registration/", answer(), format="json")

        self.assertEqual(client.delete("/registration/").status_code, 204)

        player = Player.objects.get(user=self.ana, edition=self.edition)
        self.assertFalse(player.is_active)
        body = client.get("/registration/").json()
        self.assertFalse(body["registration"]["registered"])
        self.assertEqual(body["registration"]["team_wishes"], "Avec Bob")
        client.put("/registration/", answer(), format="json")
        player.refresh_from_db()
        self.assertTrue(player.is_active)

    def test_withdrawing_without_a_registration_is_a_no_op(self):
        self.assertEqual(self.client_of(self.ana).delete("/registration/").status_code, 204)

    def test_withdrawing_after_the_close_is_refused_without_a_pass(self):
        client = self.client_of(self.ana)
        client.put("/registration/", answer(), format="json")
        self.close()

        response = client.delete("/registration/")

        self.assertEqual((response.status_code, response.json()), (409, {"error": "closed"}))
        self.assertTrue(Player.objects.get(user=self.ana, edition=self.edition).is_active)

        LateRegistration.objects.create(user=self.ana, edition=self.edition)
        self.assertEqual(client.delete("/registration/").status_code, 204)
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_registration_api`
Expected: ERROR `ImportError: cannot import name 'RegistrationRateThrottle'`.

- [ ] **Step 3: Throttle and config.** In `throttling.py` add after `PasswordCheckThrottle`:

```python
class RegistrationRateThrottle(UserRateThrottle):
    """Registration saves per user, at the "registration" rate (REGISTRATION_THROTTLE_RATE,
    30/hour by default): every PUT counts, refused or not. PUT only (a function view has one
    throttle list for all its methods, hence the method check, as in PhotoRateThrottle)."""

    scope = "registration"

    def allow_request(self, request, view):
        if request.method != "PUT":
            return True
        return super().allow_request(request, view)
```

Update the module docstring's list of throttled requests. In `config.py`, next to `PASSWORD_THROTTLE_RATE`, add `REGISTRATION_THROTTLE_RATE: str = "30/hour"` with a one-line comment; in `settings.py`'s `DEFAULT_THROTTLE_RATES` add `'registration': settings.REGISTRATION_THROTTLE_RATE,`.

- [ ] **Step 4: The view.** In `views.py`, add imports (next to the existing ones): `from . import enrolment`, `from .enrolment import RegistrationError, usable_email`, `from .models import latest_edition` (if not already imported), `from .registration_state import registration_state`, `from .throttling import RegistrationRateThrottle` (extend the existing throttling import). Add after `deactivateMe`:

```python
@extend_schema(
    methods=["GET"],
    summary="The registration form of the latest edition, with the caller's saved answers",
    responses={
        "200": OpenApiResponse(description="The form, its state, and the caller's answers"),
        "404": OpenApiResponse(description="Not a person nor invited, or no edition"),
    },
)
@extend_schema(
    methods=["PUT"],
    summary="Register for the latest edition, or edit the registration",
    responses={
        "200": OpenApiResponse(description="The form as GET returns it, with the saved answers"),
        "400": OpenApiResponse(description='{"errors": [codes]}, see enrolment.validate'),
        "409": OpenApiResponse(
            description='{"error": "closed" | "not_yet_open" | "not_configured"}'
        ),
        "429": OpenApiResponse(description="Too many saves (REGISTRATION_THROTTLE_RATE)"),
    },
)
@extend_schema(
    methods=["DELETE"],
    summary="Withdraw the registration (the answers are kept)",
    responses={"204": OpenApiResponse(description="Withdrawn, or there was none")},
)
@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])  # 404 unless a person or an invited newcomer
@throttle_classes([RegistrationRateThrottle])  # the PUT only, per user
@parser_classes([JSONParser])
def myRegistration(request):
    refusal = _not_an_account_owner(request.user)
    if refusal:
        return refusal
    edition = latest_edition()
    if edition is None:
        return Response({"error": "no_edition"}, status=404)
    state = registration_state(edition, request.user)
    if request.method == "GET":
        response = Response(enrolment.form_payload(request.user, edition, state))
        response["Cache-Control"] = "private, no-store"
        return response
    if not state.is_open:
        return Response({"error": state.reason}, status=409)
    if request.method == "DELETE":
        enrolment.withdraw(request.user, edition)
        return Response(status=204)
    skills = list(edition.registrationskill_set.filter(is_active=True))
    try:
        cleaned = enrolment.validate(
            _account_body(request), skills, not usable_email(request.user.email)
        )
    except RegistrationError as error:
        return Response({"errors": error.codes}, status=400)
    enrolment.save(request.user, edition, skills, cleaned)
    response = Response(enrolment.form_payload(request.user, edition, state))
    response["Cache-Control"] = "private, no-store"
    return response
```

(`state` is reused in the PUT response: it was open when checked, and `form_payload` then reports it as such.) Add `path("registration/", views.myRegistration),` to `urls.py` next to the `me/` routes, and `"registration/",` to the `PLAYER` set in `tests/test_permissions.py` (extend its comment: « the caller's registration »).

- [ ] **Step 5: Run the tests**

```bash
docker compose exec -T server python manage.py test olympic_warriors.tests.test_registration_api olympic_warriors.tests.test_permissions olympic_warriors.tests.test_routes olympic_warriors.tests.test_config
```

Expected: `OK`. Two spots where a plan test may need a mechanical fix (list each in your report): the unreadable-body test (DRF may answer 400 through `ParseError` before the view, which is what is asserted; if `_account_body` instead returns `{}` the answer is a 400 with codes, also fine, so loosen only the body assertion, never the status), and `Cache-Control` (DRF Response headers are read as `response["Cache-Control"]`).

- [ ] **Step 6: Commit**

```bash
git add server/olympic_warriors/views.py server/olympic_warriors/urls.py server/olympic_warriors/throttling.py server/olympic_warriors/config.py server/olympic_warriors/settings.py server/olympic_warriors/tests/test_registration_api.py server/olympic_warriors/tests/test_permissions.py
git commit -m "[FEAT] /registration/: read, save and withdraw a registration

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Admin: opening registration and the late pass

**Files:**
- Modify: `server/olympic_warriors/admin.py`
- Test: `server/olympic_warriors/tests/test_late_pass_admin.py`

- [ ] **Step 1: Write the failing tests.** Create `tests/test_late_pass_admin.py`:

```python
"""Opening registration from the Edition page and granting late passes."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from olympic_warriors.models import (
    Edition, LateRegistration, Player, RegistrationSkill, UserProfile,
)

EDITIONS = "/admin/olympic_warriors/edition/"
PLAYERS = "/admin/olympic_warriors/player/"
PROFILES = "/admin/olympic_warriors/userprofile/"
LATE = "/admin/olympic_warriors/lateregistration/"


def make_edition(year, **kw):
    return Edition.objects.create(
        year=year, host="Paris", start_date=date(year, 9, 18), end_date=date(year, 9, 19), **kw
    )


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class AdminSetup(TestCase):
    def setUp(self):
        self.orga = User.objects.create_superuser("admin", "a@b.c", "pw")
        self.client.force_login(self.orga)
        self.old = make_edition(2026)
        self.edition = make_edition(2027)
        self.ana = User.objects.create(username="ana", first_name="Ana", last_name="Lopez")
        self.bob = User.objects.create(username="bob", first_name="Bob", last_name="Martin")
        self.player = Player.objects.create(user=self.ana, edition=self.old, rating=5)

    def act(self, url, action, *ids):
        response = self.client.post(
            url, {"action": action, "_selected_action": list(ids), "index": 0}, follow=True
        )
        return [str(m) for m in response.context["messages"]]


class TestEditionPage(AdminSetup):
    def test_the_window_and_texts_are_edited_and_the_status_is_shown(self):
        response = self.client.get(f"{EDITIONS}{self.edition.pk}/change/")

        self.assertEqual(response.status_code, 200)
        for field in (
            "registration_opens", "registration_closes", "registration_intro_fr",
            "registration_intro_en", "skills_month_fr", "skills_month_en",
        ):
            self.assertContains(response, f'name="{field}"')
        self.assertContains(response, "Fermée")  # no questionnaire, no opening date yet

    def test_the_status_reads_open_once_configured(self):
        RegistrationSkill.objects.create(
            edition=self.edition, name_fr="C", name_en="C", identifier="CARD", weight=1
        )
        Edition.objects.filter(pk=self.edition.pk).update(
            registration_opens=date(2020, 1, 1), registration_closes=date(2999, 1, 1)
        )

        response = self.client.get(f"{EDITIONS}{self.edition.pk}/change/")

        self.assertContains(response, "Ouverte")

    def test_the_add_page_renders(self):
        self.assertEqual(self.client.get(f"{EDITIONS}add/").status_code, 200)


class TestGrantLatePass(AdminSetup):
    def test_from_the_player_list(self):
        messages = self.act(PLAYERS, "grant_late_pass", self.player.pk)

        pass_ = LateRegistration.objects.get()
        self.assertEqual((pass_.user, pass_.edition, pass_.granted_by), (self.ana, self.edition, self.orga))
        self.assertEqual(messages, ["Inscription tardive accordée pour 2027 à : Ana Lopez (ana)."])

    def test_from_the_profile_list_and_for_a_user_with_no_player(self):
        profile = UserProfile.objects.create(user=self.bob, invited=True)

        self.act(PROFILES, "grant_late_pass", profile.pk)

        self.assertTrue(LateRegistration.objects.filter(user=self.bob, edition=self.edition).exists())

    def test_a_second_grant_is_reported_not_duplicated(self):
        self.act(PLAYERS, "grant_late_pass", self.player.pk)

        messages = self.act(PLAYERS, "grant_late_pass", self.player.pk)

        self.assertEqual(LateRegistration.objects.count(), 1)
        self.assertEqual(messages, ["Inscription tardive déjà accordée à : Ana Lopez (ana)."])

    def test_it_targets_the_latest_edition(self):
        make_edition(2028)

        self.act(PLAYERS, "grant_late_pass", self.player.pk)

        self.assertEqual(LateRegistration.objects.get().edition.year, 2028)


class TestLateRegistrationAdmin(AdminSetup):
    def test_lists_and_revokes_but_never_adds(self):
        late = LateRegistration.objects.create(user=self.ana, edition=self.edition, granted_by=self.orga)

        self.assertContains(self.client.get(LATE), "ana")
        self.assertEqual(self.client.get(f"{LATE}add/").status_code, 403)
        self.client.post(f"{LATE}{late.pk}/delete/", {"post": "yes"})
        self.assertEqual(LateRegistration.objects.count(), 0)
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_late_pass_admin`
Expected: FAILURES (no registration fields on the Edition page, no `grant_late_pass` action).

- [ ] **Step 3: Implement in `admin.py`.** Add imports: `LateRegistration` to the models import, and

```python
from .models import latest_edition  # alongside the models import block
from .registration_state import CLOSED, NOT_CONFIGURED, NOT_YET_OPEN, registration_state
```

(`latest_edition` is exported by `olympic_warriors.models`; add it to the existing models import list rather than a second statement.) Add the action next to the other actions:

```python
def _who(users):
    return ", ".join(f"{user.get_full_name() or user.username} ({user.username})" for user in users)


@action(description="Autoriser l'inscription tardive", permissions=["change"])
def grant_late_pass(modeladmin, request, queryset):
    """Let the selected people register for the latest edition whatever the window says,
    until the edition's end. Works on players and on profiles (invited newcomers)."""
    edition = latest_edition()
    if edition is None:
        modeladmin.message_user(request, "Aucune édition.", messages.ERROR)
        return
    granted, already, seen = [], [], set()
    for row in queryset.select_related("user"):
        user = row.user
        if user.pk in seen:
            continue
        seen.add(user.pk)
        _, created = LateRegistration.objects.get_or_create(
            user=user, edition=edition, defaults={"granted_by": request.user}
        )
        (granted if created else already).append(user)
    if granted:
        modeladmin.message_user(
            request, f"Inscription tardive accordée pour {edition.year} à : {_who(granted)}."
        )
    if already:
        modeladmin.message_user(
            request, f"Inscription tardive déjà accordée à : {_who(already)}.", messages.WARNING
        )
```

Add `grant_late_pass` to the `actions` of `PlayerAdmin` and `UserProfileAdmin` (keep their existing actions). In `EditionAdmin`: extend `fields` with the registration group and a read-only status:

```python
    fields = (
        "year", "host", "start_date", "end_date", "dates_confirmed", "photos_url",
        "registration_form", "is_active",
        "registration_status", "registration_opens", "registration_closes",
        "registration_intro_fr", "registration_intro_en", "skills_month_fr", "skills_month_en",
    )
    readonly_fields = ["registration_status"]

    @display(description="Inscription en ligne")
    def registration_status(self, obj):
        """Open or why not, as an anonymous visitor sees it (a late pass is per person)."""
        if obj.pk is None:
            return "—"
        state = registration_state(obj)
        if state.is_open:
            return "Ouverte"
        return "Fermée : " + {
            NOT_CONFIGURED: "questionnaire ou date d'ouverture manquant",
            NOT_YET_OPEN: "pas encore ouverte",
            CLOSED: "terminée",
        }[state.reason]
```

Add the admin class and registration:

```python
class LateRegistrationAdmin(ModelAdmin):
    """The late passes: listed and revoked here, granted by the « Autoriser l'inscription
    tardive » action."""

    list_display = ["user", "edition", "granted_at", "granted_by"]
    list_filter = ["edition"]
    search_fields = ["user__username", "user__first_name", "user__last_name"]
    list_select_related = ["user", "edition", "granted_by"]
    readonly_fields = ["user", "edition", "granted_at", "granted_by"]

    def has_add_permission(self, request):
        return False
```

and `site.register(LateRegistration, LateRegistrationAdmin)` with the other registrations.

- [ ] **Step 4: Run**

```bash
docker compose exec -T server python manage.py test olympic_warriors.tests.test_late_pass_admin olympic_warriors.tests.test_registration_admin olympic_warriors.tests.test_player_admin olympic_warriors.tests.test_user_profile_admin
```

Expected: `OK`. Mechanical adjustments you may make to the plan's tests (list each): the exact wording of the `registration_status` text asserted by `assertContains("Fermée")` (Django escapes nothing here), and the `delete` flow's redirect.

- [ ] **Step 5: Commit**

```bash
git add server/olympic_warriors/admin.py server/olympic_warriors/tests/test_late_pass_admin.py
git commit -m "[FEAT] admin: open registration from the edition, grant late passes

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Invitations

**Files:**
- Create: `server/olympic_warriors/invitations.py`, `server/olympic_warriors/templates/admin/olympic_warriors/userprofile/invite.html`, `server/olympic_warriors/templates/admin/olympic_warriors/userprofile/change_list.html`
- Modify: `server/olympic_warriors/admin.py`
- Test: `server/olympic_warriors/tests/test_invitations.py`, `server/olympic_warriors/tests/test_invite_admin.py`

Look at `templates/admin/olympic_warriors/badge/change_list.html` first: it is the precedent for a changelist template override in this repo.

- [ ] **Step 1: Write the failing logic tests.** Create `tests/test_invitations.py`:

```python
"""The bulk invite: who is created, who is reused, who is refused."""
from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.utils import timezone

from olympic_warriors.invitations import (
    CONFLICT, CREATED, DUPLICATE, MALFORMED, REUSED, invite, parse_lines,
)
from olympic_warriors.models import Edition, LateRegistration, Player, UserProfile

PUBLIC = override_settings(PUBLIC_URL="https://ow.example")


def make_edition(year=2027):
    return Edition.objects.create(
        year=year, host="Paris", start_date=date(year, 9, 18), end_date=date(year, 9, 19)
    )


class TestParseLines(TestCase):
    def test_name_and_email_per_line(self):
        entries, problems = parse_lines(
            "Léa Martin, lea@example.com\n\n  Jean  Dupont ,JEAN@Example.com \nAdrien, a@example.com"
        )

        self.assertEqual(problems, [])
        self.assertEqual(
            [(e.line, e.first_name, e.last_name, e.email) for e in entries],
            [
                (1, "Léa", "Martin", "lea@example.com"),
                (3, "Jean", "Dupont", "jean@example.com"),
                (4, "Adrien", "", "a@example.com"),
            ],
        )

    def test_malformed_lines_are_reported_with_their_number(self):
        entries, problems = parse_lines(
            "no comma here\nLéa, not-an-email\n, lea@example.com\nOk Name, ok@example.com\n"
            "Ola, x@olympicwarriors.com"
        )

        self.assertEqual([e.email for e in entries], ["ok@example.com"])
        self.assertEqual([p.line for p in problems], [1, 2, 3, 5])


@PUBLIC
class TestInvite(TestCase):
    def run_invite(self, text, **kw):
        entries, problems = parse_lines(text)
        return invite(entries, problems, **kw)

    def test_a_newcomer_is_created_invited_with_a_claim_link(self):
        [result] = self.run_invite("Léa Martin, lea@example.com")

        user = User.objects.get(username="léamartin")
        self.assertEqual(result.status, CREATED)
        self.assertEqual((user.first_name, user.last_name, user.email), ("Léa", "Martin", "lea@example.com"))
        self.assertTrue(user.has_usable_password())  # a random one nobody receives
        self.assertTrue(UserProfile.objects.get(user=user).invited)
        self.assertTrue(result.link.startswith("https://ow.example/claim/"))
        self.assertEqual(result.warning, "")

    def test_a_returning_player_is_matched_by_a_real_email(self):
        user = User.objects.create(username="whatever", email="lea@example.com")
        Player.objects.create(user=user, edition=make_edition(2026), rating=5)

        [result] = self.run_invite("Léa Martin, LEA@example.com")

        self.assertEqual((result.status, result.user_id), (REUSED, user.pk))
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(UserProfile.objects.filter(user=user, invited=True).exists())  # a person already

    def test_a_placeholder_account_is_matched_by_username_and_gets_the_real_email(self):
        user = User.objects.create(username="léamartin", email="léamartin@olympicwarriors.com")

        [result] = self.run_invite("Léa Martin, lea@example.com")

        user.refresh_from_db()
        self.assertEqual((result.status, user.email), (REUSED, "lea@example.com"))
        self.assertTrue(UserProfile.objects.get(user=user).invited)  # not a person: needs the flag

    def test_a_username_taken_by_another_real_email_is_a_conflict(self):
        User.objects.create(username="léamartin", email="other@example.com")

        [result] = self.run_invite("Léa Martin, lea@example.com")

        self.assertEqual(result.status, CONFLICT)
        self.assertEqual(result.link, "")
        self.assertEqual(User.objects.count(), 1)

    def test_two_accounts_with_the_same_email_are_a_conflict(self):
        User.objects.create(username="a", email="lea@example.com")
        User.objects.create(username="b", email="LEA@example.com")

        [result] = self.run_invite("Léa Martin, lea@example.com")

        self.assertEqual(result.status, CONFLICT)

    def test_staff_and_deactivated_accounts_are_conflicts(self):
        User.objects.create(username="boss", email="boss@example.com", is_staff=True)
        User.objects.create(username="gone", email="gone@example.com", is_active=False)

        results = self.run_invite("Big Boss, boss@example.com\nGone Away, gone@example.com")

        self.assertEqual([r.status for r in results], [CONFLICT, CONFLICT])
        self.assertEqual([r.link for r in results], ["", ""])

    def test_an_already_activated_account_gets_a_link_with_a_warning(self):
        user = User.objects.create(username="lea", email="lea@example.com")
        Player.objects.create(user=user, edition=make_edition(2026), rating=5)
        UserProfile.objects.create(user=user, claimed_at=timezone.now())

        [result] = self.run_invite("Léa Martin, lea@example.com")

        self.assertEqual(result.status, REUSED)
        self.assertTrue(result.link.startswith("https://ow.example/claim/"))
        self.assertIn("réinitialise", result.warning)

    def test_duplicates_inside_the_paste_are_skipped(self):
        results = self.run_invite("Léa Martin, lea@example.com\nLea Other, lea@example.com\nLéa Martin, b@example.com")

        self.assertEqual([r.status for r in results], [CREATED, DUPLICATE, DUPLICATE])
        self.assertEqual(User.objects.count(), 1)

    def test_malformed_lines_are_reported_and_the_rest_is_processed(self):
        results = self.run_invite("garbage\nLéa Martin, lea@example.com")

        self.assertEqual([(r.line, r.status) for r in results], [(1, MALFORMED), (2, CREATED)])

    def test_the_late_pass_checkbox_grants_a_pass_to_everyone_invited(self):
        edition = make_edition()
        existing = User.objects.create(username="bob", email="bob@example.com")
        Player.objects.create(user=existing, edition=make_edition(2026), rating=5)
        orga = User.objects.create(username="orga", is_staff=True)

        results = self.run_invite(
            "Léa Martin, lea@example.com\nBob X, bob@example.com\nBad Line",
            grant_late_pass=True, granted_by=orga,
        )

        self.assertEqual(LateRegistration.objects.filter(edition=edition).count(), 2)
        self.assertEqual(LateRegistration.objects.first().granted_by, orga)
        self.assertEqual([r.late_pass for r in results], [True, True, False])

    def test_without_a_public_url_nothing_is_created(self):
        with override_settings(PUBLIC_URL=""), self.assertRaises(ImproperlyConfigured):
            self.run_invite("Léa Martin, lea@example.com")

        self.assertEqual(User.objects.count(), 0)

    def test_the_late_pass_needs_an_edition(self):
        with self.assertRaises(LookupError):
            self.run_invite("Léa Martin, lea@example.com", grant_late_pass=True)

        self.assertEqual(User.objects.count(), 0)
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_invitations`
Expected: ERROR `ModuleNotFoundError: olympic_warriors.invitations`.

- [ ] **Step 3: Implement `invitations.py`**

```python
"""
The bulk invite (spec 2026-10-04): an organiser pastes `Prénom Nom, email` lines, and each
becomes an account the person can claim (a newcomer is created and marked invited) or a
returning account that is reused, and gets a claim link, optionally with a late pass.
Nothing here is logged: the links travel only in the admin's messages.
"""
from dataclasses import dataclass

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils.crypto import get_random_string

from .claims import Unclaimable, claim_link, public_url
from .enrolment import usable_email
from .models import LateRegistration, UserProfile, latest_edition
from .registration import parse_name

CREATED = "created"
REUSED = "reused"
CONFLICT = "conflict"
MALFORMED = "malformed"
DUPLICATE = "duplicate"


@dataclass(frozen=True)
class Invite:
    """A well-formed line of the paste. `username` is derived as the registration import
    derives it (every token joined, lower-cased, accents kept)."""

    line: int
    first_name: str
    last_name: str
    email: str
    username: str


@dataclass(frozen=True)
class Problem:
    """A line that cannot be read."""

    line: int
    text: str
    reason: str


@dataclass(frozen=True)
class InviteResult:
    """What became of one line: `status` is one of the constants above."""

    line: int
    name: str
    status: str
    detail: str = ""
    link: str = ""
    warning: str = ""
    user_id: int | None = None
    late_pass: bool = False


def parse_lines(text):
    """Split the paste into (entries, problems). A line is `Prénom Nom, email`, split at its
    last comma; blank lines are ignored; the email is lower-cased and must be a real one."""
    entries, problems = [], []
    for number, raw in enumerate(text.splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        name, _, email = raw.rpartition(",")
        email = email.strip().lower()
        try:
            first_name, last_name, username = parse_name(name)
        except ValueError:
            problems.append(Problem(number, raw, "nom manquant"))
            continue
        try:
            validate_email(email)
        except ValidationError:
            problems.append(Problem(number, raw, "email invalide"))
            continue
        if not usable_email(email):
            problems.append(Problem(number, raw, "adresse générique, pas un vrai email"))
            continue
        entries.append(Invite(number, first_name, last_name, email, username))
    return entries, problems


def _match(entry):
    """(user, how) for the account this line is, (None, None) when it is a newcomer, or
    (None, reason) for a conflict."""
    by_email = list(User.objects.filter(email__iexact=entry.email))
    if len(by_email) > 1:
        return None, "plusieurs comptes ont cette adresse"
    if by_email:
        return by_email[0], "email"
    existing = User.objects.filter(username=entry.username).first()
    if existing is None:
        return None, None
    current = existing.email.strip().lower()
    if not usable_email(current) or current == entry.email:
        return existing, "identifiant"
    return None, (
        f"l'identifiant « {entry.username} » appartient à un compte avec une autre adresse"
    )


def invite(entries, problems, grant_late_pass=False, granted_by=None):
    """
    Process a parsed paste and return one InviteResult per line, in line order.

    :raises ImproperlyConfigured: without a usable PUBLIC_URL, before anything is created.
    :raises LookupError: a late pass was asked for but there is no edition, likewise.
    """
    public_url()
    edition = None
    if grant_late_pass:
        edition = latest_edition()
        if edition is None:
            raise LookupError("no edition")
    results = {p.line: InviteResult(p.line, p.text, MALFORMED, p.reason) for p in problems}
    seen = set()
    for entry in entries:
        name = f"{entry.first_name} {entry.last_name}".strip()
        keys = {entry.email, entry.username}
        if seen & keys:
            results[entry.line] = InviteResult(
                entry.line, name, DUPLICATE, "déjà présent plus haut dans la liste"
            )
            continue
        seen |= keys
        results[entry.line] = _one(entry, name, edition, granted_by)
    return [results[line] for line in sorted(results)]


def _one(entry, name, edition, granted_by):
    with transaction.atomic():
        user, how = _match(entry)
        if user is None and how is not None:
            return InviteResult(entry.line, name, CONFLICT, how)
        if user is not None:
            if user.is_staff or user.is_superuser:
                return InviteResult(entry.line, name, CONFLICT, "compte d'organisateur")
            if not user.is_active:
                return InviteResult(entry.line, name, CONFLICT, "compte désactivé")
            status = REUSED
            if not usable_email(user.email):
                user.email = entry.email
                user.save(update_fields=["email"])
        else:
            user = User.objects.create_user(
                username=entry.username,
                first_name=entry.first_name,
                last_name=entry.last_name,
                email=entry.email,
                password=get_random_string(length=12),
            )
            status = CREATED
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if status == CREATED or not user.player_set.exists():
            if not profile.invited:
                profile.invited = True
                profile.save(update_fields=["invited", "updated_at"])
        if edition is not None:
            LateRegistration.objects.get_or_create(
                user=user, edition=edition, defaults={"granted_by": granted_by}
            )
        try:
            link = claim_link(user)
        except Unclaimable as error:
            return InviteResult(entry.line, name, CONFLICT, f"pas de lien ({error.reason})")
        warning = ""
        if profile.claimed_at is not None:
            warning = "compte déjà activé : ce lien réinitialise le mot de passe qu'il a choisi"
        return InviteResult(
            entry.line, name, status, link=link, warning=warning, user_id=user.pk,
            late_pass=edition is not None,
        )
```

- [ ] **Step 4: Run the logic tests**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_invitations`
Expected: `OK`. Mechanical fixes you may make (list each): the `Unclaimable` branch inside `_one` is unreachable for the cases above (a user that reached it is not staff, is active and can register) and needs no test; the `late_pass` flags in `test_the_late_pass_checkbox...` follow the rule that conflicts and malformed lines get no pass.

- [ ] **Step 5: Write the failing admin-page tests.** Create `tests/test_invite_admin.py`:

```python
"""The invite page of the admin: a button on the profile list, a form, links in messages."""
from datetime import date

from django.contrib.auth.models import Permission, User
from django.test import TestCase, override_settings

from olympic_warriors.models import Edition, LateRegistration, UserProfile

INVITE = "/admin/olympic_warriors/userprofile/invite/"
PROFILES = "/admin/olympic_warriors/userprofile/"


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
    PUBLIC_URL="https://ow.example",
)
class TestInviteAdmin(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@b.c", "pw"))
        self.edition = Edition.objects.create(
            year=2027, host="Paris", start_date=date(2027, 9, 18), end_date=date(2027, 9, 19)
        )

    def post(self, **data):
        return self.client.post(INVITE, data, follow=True)

    def messages(self, response):
        return [str(m) for m in response.context["messages"]]

    def test_the_profile_list_links_to_the_page(self):
        self.assertContains(self.client.get(PROFILES), INVITE)

    def test_the_page_renders(self):
        response = self.client.get(INVITE)

        self.assertContains(response, 'name="lines"')
        self.assertContains(response, 'name="late_pass"')

    def test_a_paste_creates_accounts_and_reports_each_line_with_its_link(self):
        response = self.post(lines="Léa Martin, lea@example.com\nbad line")

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="léamartin")
        self.assertTrue(UserProfile.objects.get(user=user).invited)
        text = "\n".join(self.messages(response))
        self.assertIn("Léa Martin", text)
        self.assertIn("https://ow.example/claim/", text)
        self.assertIn("bad line", text)

    def test_the_single_user_fields_work_like_a_one_line_paste(self):
        self.post(first_name="Jean", last_name="Dupont", email="jean@example.com")

        self.assertTrue(User.objects.filter(username="jeandupont", email="jean@example.com").exists())

    def test_the_late_pass_checkbox(self):
        response = self.post(lines="Léa Martin, lea@example.com", late_pass="on")

        self.assertEqual(LateRegistration.objects.count(), 1)
        self.assertIn("/register", "\n".join(self.messages(response)))

    def test_an_empty_submission_is_refused_on_the_form(self):
        response = self.post()

        self.assertEqual(User.objects.filter(is_superuser=False).count(), 0)
        self.assertContains(response, "Saisissez")

    def test_without_a_public_url_one_error_and_nothing_created(self):
        with override_settings(PUBLIC_URL=""):
            response = self.post(lines="Léa Martin, lea@example.com")

        self.assertEqual(User.objects.filter(is_superuser=False).count(), 0)
        self.assertTrue(any("PUBLIC_URL" in m for m in self.messages(response)))

    def test_a_view_only_organiser_cannot_use_it(self):
        viewer = User.objects.create_user("viewer", password="pw", is_staff=True)
        viewer.user_permissions.add(
            Permission.objects.get(content_type__app_label="olympic_warriors", codename="view_userprofile")
        )
        self.client.force_login(viewer)

        self.assertEqual(self.client.get(INVITE).status_code, 403)
        self.assertEqual(self.client.post(INVITE, {"lines": "A B, a@example.com"}).status_code, 403)
```

- [ ] **Step 6: Run to verify it fails**

Run: `docker compose exec -T server python manage.py test olympic_warriors.tests.test_invite_admin`
Expected: FAIL (404 on the invite URL).

- [ ] **Step 7: Implement the page.** In `admin.py`, add `from django import forms`, `from django.core.exceptions import PermissionDenied`, `from django.shortcuts import redirect`, `from django.template.response import TemplateResponse`, `from django.urls import path, reverse`, and `from .invitations import CONFLICT, CREATED, DUPLICATE, MALFORMED, REUSED, invite, parse_lines`, `Entry`-less (use `parse_lines`' output). Add:

```python
class InviteForm(forms.Form):
    """One person (three fields) or a paste of `Prénom Nom, email` lines, or both."""

    first_name = forms.CharField(label="Prénom", required=False)
    last_name = forms.CharField(label="Nom", required=False)
    email = forms.EmailField(label="Email", required=False)
    lines = forms.CharField(
        label="Une personne par ligne : Prénom Nom, email",
        widget=forms.Textarea(attrs={"rows": 10, "cols": 70}),
        required=False,
    )
    late_pass = forms.BooleanField(
        label="Inscription tardive (même hors période d'inscription)", required=False
    )

    def clean(self):
        data = super().clean()
        single = [data.get(k) for k in ("first_name", "last_name", "email")]
        if any(single) and not (data.get("first_name") and data.get("email")):
            raise forms.ValidationError("Pour une personne seule : prénom et email sont requis.")
        if not any(single) and not (data.get("lines") or "").strip():
            raise forms.ValidationError("Saisissez une personne ou collez une liste.")
        return data

    def text(self):
        """The paste, with the single person appended as one more line."""
        lines = (self.cleaned_data.get("lines") or "").strip()
        if self.cleaned_data.get("first_name"):
            name = f"{self.cleaned_data['first_name']} {self.cleaned_data.get('last_name', '')}"
            lines = (lines + "\n" if lines else "") + f"{name.strip()}, {self.cleaned_data['email']}"
        return lines
```

In `UserProfileAdmin` add:

```python
    change_list_template = "admin/olympic_warriors/userprofile/change_list.html"

    def get_urls(self):
        custom = [
            path(
                "invite/",
                self.admin_site.admin_view(self.invite_view),
                name="olympic_warriors_userprofile_invite",
            )
        ]
        return custom + super().get_urls()

    def invite_view(self, request):
        """Create or reuse accounts from a paste and show each person's claim link (in
        messages only, never logged). Needs the right to add and to change users: a link
        sets a password and the page creates users."""
        if not request.user.has_perms(["auth.add_user", "auth.change_user"]):
            raise PermissionDenied
        form = InviteForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            entries, problems = parse_lines(form.text())
            try:
                results = invite(
                    entries, problems, form.cleaned_data["late_pass"], granted_by=request.user
                )
            except ImproperlyConfigured:
                self.message_user(
                    request,
                    "PUBLIC_URL n'est pas configurée : aucun compte créé, aucun lien généré.",
                    messages.ERROR,
                )
            except LookupError:
                self.message_user(request, "Aucune édition : aucun compte créé.", messages.ERROR)
            else:
                self._report(request, results)
                return redirect(reverse("admin:olympic_warriors_userprofile_invite"))
        context = {**self.admin_site.each_context(request), "form": form, "title": "Inviter des joueurs", "opts": self.model._meta}
        return TemplateResponse(request, "admin/olympic_warriors/userprofile/invite.html", context)

    def _report(self, request, results):
        for result in results:
            head = f"Ligne {result.line} : {result.name}"
            if result.status == CREATED or result.status == REUSED:
                verb = "créé" if result.status == CREATED else "compte existant réutilisé"
                text = f"{head} ({verb}) : {result.link}"
                if result.late_pass:
                    text += " (inscription tardive : envoyer aussi l'adresse /register)"
                if result.warning:
                    self.message_user(request, f"{text} — ATTENTION : {result.warning}", messages.WARNING)
                else:
                    self.message_user(request, text)
            else:
                label = {CONFLICT: "conflit", MALFORMED: "ligne illisible", DUPLICATE: "doublon"}[result.status]
                self.message_user(request, f"{head} : {label}, {result.detail}", messages.WARNING)
```

(`ImproperlyConfigured` and `messages` are already imported in `admin.py`.) Create `templates/admin/olympic_warriors/userprofile/change_list.html`, modelled on the Badge changelist override:

```django
{% extends "admin/change_list.html" %}
{% block object-tools-items %}
  <li><a href="{% url 'admin:olympic_warriors_userprofile_invite' %}" class="addlink">Inviter des joueurs</a></li>
  {{ block.super }}
{% endblock %}
```

and `invite.html`:

```django
{% extends "admin/base_site.html" %}
{% block content %}
<div id="content-main">
  <p>Crée un compte (ou réutilise celui d'un joueur existant) et fournit un lien d'activation à envoyer à la personne. Les liens ne sont affichés qu'ici, une seule fois.</p>
  <form method="post">
    {% csrf_token %}
    {{ form.non_field_errors }}
    {{ form.as_p }}
    <input type="submit" value="Inviter" class="default">
  </form>
</div>
{% endblock %}
```

Check that `UserProfileAdmin` does not already set `change_list_template` and that Django finds the app's `templates/` directory (the Badge override proves it does).

- [ ] **Step 8: Run**

```bash
docker compose exec -T server python manage.py test olympic_warriors.tests.test_invite_admin olympic_warriors.tests.test_invitations olympic_warriors.tests.test_user_profile_admin olympic_warriors.tests.test_claims
```

Expected: `OK`. Mechanical adjustments you may make (list each): how messages are escaped in `assertContains`/context (assert on `str(message)`, as the plan does), and the exact empty-submission wording.

- [ ] **Step 9: Commit**

```bash
git add server/olympic_warriors/invitations.py server/olympic_warriors/admin.py server/olympic_warriors/templates server/olympic_warriors/tests/test_invitations.py server/olympic_warriors/tests/test_invite_admin.py
git commit -m "[FEAT] admin: invite players in bulk, with claim links and late passes

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Documentation and final verification

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Document slice 2.** In `CLAUDE.md`, replace the sentence at the end of the « Registration questionnaire » paragraph that begins `Not built yet (slices 2 and 3):` with the text below, and add the new paragraph after it:

Replace with: `Not built yet (slice 3): the SvelteKit pages (`/register`, the header link, the hub call to action, the claim redirect and the account page for invited users).`

New paragraph, after the questionnaire paragraph:

```markdown
**In-app registration** (spec `2026-10-04-in-app-registration-design.md`, slice 2): `Edition.registration_opens`/`registration_closes`, FR/EN `registration_intro_*` and `skills_month_*`, `UserProfile.invited` and `LateRegistration` (`user`, `edition`, `granted_at`, `granted_by`, unique on user and edition, not exported). `registration_state.registration_state(edition, user)` is the one open/closed rule: closed `not_configured` without an active `RegistrationSkill` (a late pass does not bypass that) or without `registration_opens`, `not_yet_open`, `closed` once past `registration_closes` (inclusive; the day before `start_date` when blank, Paris dates); a holder of a `LateRegistration` is open (`late_pass`) through the edition's `end_date`. `claims.can_register(user)` is a person or an invited newcomer: `unclaimable_reason`, `unresettable_reason`, `complete_claim` and `views._not_an_account_owner` (`/me/email/`, `/me/password/`, `/me/deactivate/`) use it, `/me/photo/` and `/me/showcase/` stay for people, and `/me/` carries `can_register` from the profile row it already joins (`ME_QUERIES` unchanged). `GET`/`PUT`/`DELETE /registration/` (`myRegistration`, `IsAuthenticated`, in `test_permissions.py`'s `PLAYER` list, 404 `not_a_person` unless `can_register`, 404 `no_edition`, always the latest edition, `private, no-store`): GET returns the form (`enrolment.form_payload`: state with its reason, intro and month texts, skills, the active disciplines, the choice lists, the email as `{value, editable}`, the saved `registration` (kept, with `registered: false`, after a withdrawal) and `suggested` stable answers of the latest earlier registration while there is none); PUT validates (`enrolment.validate`, `{"errors": [codes]}` with `missing_rating`, `invalid_rating`, `invalid_global_level`, `missing_frequency`, `invalid_frequency`, `invalid_sport`, `too_many_sports`, `too_long`, `invalid_text`, `attendance_required`, `no_email`, `invalid_email`), 409 `{"error": reason}` when closed, then `enrolment.save` in one transaction under the user's row lock (the Player created or reactivated with its team kept, ratings through `registration.rate` with the questionnaire weights, sports replaced as a set, the email saved only when the account had no usable one, an `@olympicwarriors.com` address counting as none); DELETE soft-deletes the Player and keeps the answers, 409 when closed. `RegistrationRateThrottle` (scope `registration`, `REGISTRATION_THROTTLE_RATE`, `30/hour` per user, PUT only, every PUT counting). `accounts.deactivate` now clears the private answers and deletes the `PlayerSport` rows. Admin: the Edition page edits the window and texts and shows « Inscription en ligne » (open, or why not, for an anonymous visitor); « Autoriser l'inscription tardive » on the Player and UserProfile lists grants a pass on the latest edition (`LateRegistration` admin lists and revokes); « Inviter des joueurs » (button on the profile list, `invitations.py`, needs `auth.add_user` and `auth.change_user`) takes one person or a paste of `Prénom Nom, email` lines: a real-email match is reused, else a username match is reused only when its email is a placeholder or equal, a username held by another real email, a staff or a deactivated account is a conflict (skipped, reported), a newcomer is created `invited`, and every created or reused account gets a claim link in the admin's messages (a warning on one already activated: the link resets its password), optionally with a late pass; no `PUBLIC_URL` means nothing is created.
```

- [ ] **Step 2: Run every check CI runs**

```bash
docker compose exec -T server python manage.py makemigrations --check --dry-run
docker compose exec -T server python manage.py test
cd front && npm test
```

Expected: `No changes detected`; the whole Django suite `OK`; Vitest unchanged and passing (this slice touches no front file).

- [ ] **Step 3: Commit and hand over**

```bash
git add CLAUDE.md
git commit -m "[DOCS] document the in-app registration API

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Report to Hugo: the branch (`feat/registration-api`, cut from `feat/registration-foundations`), the test results, and the deploy order: slice 1 first, then this slice (`migrate` to `0043`, rebuild the server image), the front last. Do not open the PR or touch `dev`/`main` unasked.

---

## Self-review (spec coverage for slice 2)

| Spec requirement | Task |
|---|---|
| `Edition` window and text fields; open only with `registration_opens`, questionnaire; default close the day before the start; inclusive | 1, 2 |
| `UserProfile.invited`; claim accepts invited (and, found while planning, reset and the `claimed_at` stamp) | 1, 3 |
| `LateRegistration` with `granted_by`, valid until `end_date`, no bypass of `not_configured` | 1, 2 |
| `/me/` `can_register` at the same query count | 3 |
| `/registration/` GET/PUT/DELETE, codes, throttle, keeps team, email rule, `suggested`, withdraw keeps answers | 5, 6 |
| Deletion clears the private answers | 4 |
| Admin: window fields and status, `LateRegistration` admin, late-pass action | 7 |
| Invite: matching rules, conflicts, claimed warning, late-pass checkbox, `PUBLIC_URL`, permissions | 8 |
| Privacy walks for `/registration/` | covered by `test_permissions.py` (route listed) and Task 6 (`no-store`); nothing public changes |
| Front pages, claim redirect, header link, hub call to action | slice 3 |

Deliberate choices not in the spec text: the invite page lives on the **UserProfile** changelist (the auth `User` admin is Django's, not ours); a holder of a pass reports `late_pass` even inside the window; the validation reports codes as `{"errors": [...]}` (a list), like the claim and password endpoints.

Names used across tasks: `registration_state`, `RegistrationState(is_open, reason)`, `NOT_CONFIGURED/NOT_YET_OPEN/CLOSED/LATE_PASS`, `closing_date` (Task 2, used by Task 5); `can_register` (Task 3, used by Tasks 6 and 8's flow); `enrolment.validate/save/withdraw/form_payload`, `RegistrationError(codes)`, `usable_email` (Task 5, used by Tasks 6 and 8); `RegistrationRateThrottle` (Task 6); `grant_late_pass` (Task 7); `invitations.parse_lines/invite`, `CREATED/REUSED/CONFLICT/MALFORMED/DUPLICATE`, `InviteResult` (Task 8).
