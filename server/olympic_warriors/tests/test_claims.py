"""
Claim links: an organiser generates one in the admin for a person (a user with an active
Player in an active edition, active, not staff) and sends it however they like; the person
opens it, sees their username, and chooses a password, which ends every older session and
the link itself.

GET /claim/<uidb64>/<token>/ answers the first name and username, POST sets the password
and answers a fresh DRF token. Every refusal of the link is the same 404, so the endpoint
tells nobody who exists. Only the POST counts against the login throttle, in the same
per-IP bucket as /auth/token/ and the admin login.
"""

import datetime
import os
import re
import threading
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from olympic_warriors import claims
from olympic_warriors.claims import (
    Unclaimable,
    check_claim,
    claim_link,
    complete_claim,
    is_claimable,
)
from olympic_warriors.config import DevConfig, ProdConfig
from olympic_warriors.models import Edition, Player, Team, UserProfile
from olympic_warriors.throttling import LoginRateThrottle

LIMIT = LoginRateThrottle().num_requests
INVALID = {"error": "invalid_link"}
GOOD = "violet-harbour-lantern"
# The link parts the front accepts before calling the API.
LINK_PART = r"^[A-Za-z0-9_-]{1,128}$"

PRIVATE_CACHE = override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "claim-tests",
        }
    }
)


def parts(user):
    """A fresh link's uidb64 and token for `user`."""
    return urlsafe_base64_encode(force_bytes(user.pk)), default_token_generator.make_token(user)


def path(uidb64, token):
    return f"/claim/{uidb64}/{token}/"


class ClaimSetup:
    """Léa is a person in 2026 (and was in 2024); the others each miss one condition."""

    def setUp(self):
        self.y2024 = Edition.objects.create(
            year=2024, host="Nantes", start_date="2024-09-21", end_date="2024-09-22"
        )
        self.y2026 = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.old = Edition.objects.create(
            year=2019, host="Lyon", start_date="2019-09-21", end_date="2019-09-22",
            is_active=False,
        )
        self.mxm = Team.objects.create(name="MxM", edition=self.y2026)
        self.lea = self.person(
            "leamartin", "Léa", "Martin", self.y2026, self.y2024, password="old-password"
        )
        self.staff = self.person("ana", "Ana", "Lopez", self.y2026, is_staff=True)
        self.boss = self.person("boss", "Big", "Boss", self.y2026, is_superuser=True)
        self.gone = self.person("gone", "Gaël", "Durand", self.y2026, is_active=False)
        self.retired = self.person("retired", "Rémi", "Petit", self.old)
        self.benched = self.person("benched", "Bea", "Roux")
        Player.objects.create(user=self.benched, edition=self.y2026, rating=5, is_active=False)
        self.stranger = self.person("stranger", "Sam", "Blanc")

    def person(self, username, first, last, *editions, password=None, **flags):
        """A user with an active Player in each of `editions` (no usable password unless
        given, like the users the registration import creates, and faster to hash)."""
        user = User.objects.create_user(
            username=username, first_name=first, last_name=last, password=password, **flags
        )
        for edition in editions:
            Player.objects.create(
                user=user,
                edition=edition,
                rating=5,
                team=self.mxm if edition == self.y2026 else None,
            )
        return user


class TestClaimable(ClaimSetup, TestCase):
    """Who a link is for, and what it looks like."""

    def test_only_an_active_non_staff_person_is_claimable(self):
        self.assertTrue(is_claimable(self.lea))
        for user in (self.staff, self.boss, self.gone, self.retired, self.benched, self.stranger):
            with self.subTest(user=user.username):
                self.assertFalse(is_claimable(user))

    @override_settings(PUBLIC_URL="https://ow.example/")
    def test_the_link_is_the_front_claim_page(self):
        link = claim_link(self.lea)
        match = re.fullmatch(r"https://ow\.example/claim/([^/]+)/([^/]+)", link)
        self.assertIsNotNone(match, link)
        uidb64, token = match.groups()
        self.assertRegex(uidb64, LINK_PART)
        self.assertRegex(token, LINK_PART)
        self.assertEqual(check_claim(uidb64, token), self.lea)

    def test_no_link_for_an_unclaimable_user(self):
        for user, reason in (
            (self.staff, "staff"),
            (self.boss, "staff"),
            (self.gone, "inactive"),
            (self.retired, "not_a_person"),
            (self.benched, "not_a_person"),
            (self.stranger, "not_a_person"),
        ):
            with self.subTest(user=user.username):
                with self.assertRaises(Unclaimable) as raised:
                    claim_link(user)
                self.assertEqual(raised.exception.reason, reason)
                self.assertIsInstance(raised.exception, ValueError)

    def test_no_link_without_a_usable_public_url(self):
        for base in ("", "   ", "ow.example", "/claim", "ftp://ow.example", "https://"):
            with self.subTest(base=base), override_settings(PUBLIC_URL=base):
                with self.assertRaises(ImproperlyConfigured):
                    claim_link(self.lea)

    def test_the_links_last_a_week(self):
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 7 * 24 * 3600)


class TestConfig(TestCase):
    """PUBLIC_URL, the base of every link: the Vite dev server in dev, empty (links refused,
    the rest of the site unaffected) in production until it is set."""

    # The values every config requires.
    BASE = {
        "SECRET_KEY": "k", "DEBUG": False, "DB_HOST": "h", "DB_NAME": "n", "DB_USER": "u",
        "DB_PASS": "p", "DB_PORT": 5432,
    }

    def setUp(self):
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        os.environ.pop("PUBLIC_URL", None)

    def test_dev_defaults_to_the_local_front(self):
        self.assertEqual(DevConfig(_env_file=None, **self.BASE).PUBLIC_URL, "http://localhost:5173")

    def test_prod_defaults_to_empty_so_a_deploy_never_fails_on_it(self):
        self.assertEqual(ProdConfig(_env_file=None, **self.BASE).PUBLIC_URL, "")
        config = ProdConfig(_env_file=None, PUBLIC_URL="https://ow.example", **self.BASE)
        self.assertEqual(config.PUBLIC_URL, "https://ow.example")


@PRIVATE_CACHE
class TestClaimLink(ClaimSetup, APITestCase):
    """GET: who the link is for, or the one 404."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def test_a_valid_link_gives_the_first_name_and_username(self):
        response = self.client.get(path(*parts(self.lea)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"first_name": "Léa", "username": "leamartin"})

    def assert_invalid(self, url):
        response = self.client.get(url)
        self.assertEqual((response.status_code, response.json()), (404, INVALID))

    def test_a_bad_user_id_is_refused(self):
        _, token = parts(self.lea)
        for uidb64 in (
            "x",  # not base64
            urlsafe_base64_encode(b"abc"),  # not a number
            urlsafe_base64_encode(b"\xff\xfe"),  # not even text
            urlsafe_base64_encode(force_bytes(10**6)),  # nobody
            urlsafe_base64_encode(force_bytes(10**30)),  # beyond any id
            urlsafe_base64_encode(force_bytes(f"+{self.lea.pk}")),  # Léa, not canonical
            urlsafe_base64_encode(force_bytes(f"0{self.lea.pk}")),
            urlsafe_base64_encode(force_bytes(self.staff.pk)),  # someone else
        ):
            with self.subTest(uidb64=uidb64):
                self.assert_invalid(path(uidb64, token))

    def test_a_bad_token_is_refused(self):
        uidb64, token = parts(self.lea)
        other = parts(self.stranger)[1]
        tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
        for bad in ("x", other, tampered, token + "0", "-".join(["zzzzzzzzzzzzzz", "0" * 32])):
            with self.subTest(token=bad):
                self.assert_invalid(path(uidb64, bad))

    def test_a_link_expires_after_a_week(self):
        uidb64, token = parts(self.lea)
        now = datetime.datetime.now()
        for age, status in (
            (datetime.timedelta(days=6, hours=23), 200),
            (datetime.timedelta(days=7, seconds=1), 404),
        ):
            with self.subTest(age=age):
                clock = mock.patch.object(
                    PasswordResetTokenGenerator, "_now", return_value=now + age
                )
                with clock:
                    self.assertEqual(self.client.get(path(uidb64, token)).status_code, status)

    def test_an_unclaimable_user_is_refused_even_with_a_valid_token(self):
        for user in (self.staff, self.boss, self.gone, self.retired, self.benched, self.stranger):
            with self.subTest(user=user.username):
                self.assert_invalid(path(*parts(user)))

    def test_a_link_dies_when_its_user_stops_being_claimable(self):
        link = path(*parts(self.lea))
        self.lea.is_staff = True
        self.lea.save()
        self.assert_invalid(link)

    def test_every_refusal_is_the_same_response(self):
        _, token = parts(self.lea)
        urls = (
            path("x", token),
            path(urlsafe_base64_encode(force_bytes(10**6)), token),
            path(parts(self.lea)[0], "x"),
            path(*parts(self.staff)),
            path(*parts(self.stranger)),
            path(*parts(self.gone)),
        )
        answers = {(r.status_code, r.content) for r in (self.client.get(url) for url in urls)}
        self.assertEqual(len(answers), 1)

    def test_a_token_header_plays_no_part(self):
        # The link is the credential: a stale token cookie forwarded by the front must not
        # turn the claim page into a 401.
        self.client.credentials(HTTP_AUTHORIZATION="Token not-a-real-token")
        self.assertEqual(self.client.get(path(*parts(self.lea))).status_code, 200)


@PRIVATE_CACHE
class TestClaimPassword(ClaimSetup, APITestCase):
    """POST: the password is checked, set, and every older session ends."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.old_key = Token.objects.get(user=self.lea).key
        self.link = path(*parts(self.lea))

    def claim(self, body, link=None):
        # Not about the throttle (TestClaimThrottle is): every attempt gets a fresh budget.
        cache.clear()
        return self.client.post(link or self.link, body, format="json")

    def assert_refused(self, body, codes):
        response = self.claim(body)
        self.assertEqual((response.status_code, response.json()), (400, {"errors": codes}))

    def test_a_weak_password_gives_its_validator_codes(self):
        self.assert_refused({"password": "Zx9!q"}, ["password_too_short"])
        self.assert_refused(
            {"password": "12345678"}, ["password_too_common", "password_entirely_numeric"]
        )
        self.assert_refused({"password": "leamartin1"}, ["password_too_similar"])

    def test_a_missing_password_is_its_own_code(self):
        for body in ({}, {"password": ""}, {"password": "   "}, {"password": None},
                     {"password": 12345678}, {"password": ["x"]}):
            with self.subTest(body=body):
                self.assert_refused(body, ["password_missing"])

    def test_a_refused_password_changes_nothing(self):
        self.claim({"password": "12345678"})
        self.lea.refresh_from_db()
        self.assertTrue(self.lea.check_password("old-password"))
        self.assertEqual(Token.objects.get(user=self.lea).key, self.old_key)
        self.assertFalse(UserProfile.objects.filter(user=self.lea).exists())
        self.assertEqual(self.client.get(self.link).status_code, 200)

    def test_an_invalid_link_is_a_404_before_the_password_is_looked_at(self):
        response = self.claim({"password": "123"}, link=path(*parts(self.staff)))
        self.assertEqual((response.status_code, response.json()), (404, INVALID))
        response = self.claim({"password": GOOD}, link=path(parts(self.lea)[0], "x"))
        self.assertEqual((response.status_code, response.json()), (404, INVALID))

    def test_success_answers_a_fresh_token_and_the_user_id(self):
        before = timezone.now()
        response = self.claim({"password": GOOD})

        self.assertEqual(response.status_code, 200)
        new_key = Token.objects.get(user=self.lea).key
        self.assertEqual(response.json(), {"token": new_key, "user_id": self.lea.pk})
        self.assertNotEqual(new_key, self.old_key)
        self.assertNotIn(GOOD, response.content.decode())
        self.lea.refresh_from_db()
        self.assertTrue(self.lea.check_password(GOOD))
        self.assertGreaterEqual(self.lea.profile.claimed_at, before)

    def test_the_old_token_stops_working_and_the_new_one_works(self):
        new_key = self.claim({"password": GOOD}).json()["token"]
        player_route = "/games/"  # IsAuthenticated: any token
        old = APIClient()
        old.credentials(HTTP_AUTHORIZATION=f"Token {self.old_key}")
        new = APIClient()
        new.credentials(HTTP_AUTHORIZATION=f"Token {new_key}")
        self.assertEqual(old.get(player_route).status_code, 401)
        self.assertEqual(new.get(player_route).status_code, 200)

    def test_the_new_password_logs_in(self):
        self.claim({"password": GOOD})
        response = self.client.post(
            "/auth/token/", {"username": "leamartin", "password": GOOD}, format="json"
        )
        self.assertEqual(response.status_code, 200)

    def test_a_link_works_once(self):
        other_link = path(*parts(self.lea))  # issued before the claim: dies with it
        self.assertEqual(self.claim({"password": GOOD}).status_code, 200)
        for link in (self.link, other_link):
            with self.subTest(link=link):
                self.assertEqual(self.client.get(link).status_code, 404)
                response = self.claim({"password": "another-long-phrase"}, link=link)
                self.assertEqual((response.status_code, response.json()), (404, INVALID))
        self.lea.refresh_from_db()
        self.assertTrue(self.lea.check_password(GOOD))

    def test_a_new_link_reclaims_and_keeps_the_profile(self):
        self.claim({"password": GOOD})
        profile = UserProfile.objects.get(user=self.lea)
        profile.photo_locked = True
        profile.save()
        self.lea.refresh_from_db()  # a link is made from the current password hash
        response = self.claim({"password": "another-long-phrase"}, link=path(*parts(self.lea)))
        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertTrue(profile.photo_locked)
        self.assertEqual(UserProfile.objects.filter(user=self.lea).count(), 1)


class TestCompleteClaim(ClaimSetup, TestCase):
    """complete_claim() re-checks the link under the user's row lock, so what changed since
    check_claim() read the user wins."""

    def test_it_returns_the_new_token_key(self):
        uidb64, token = parts(self.lea)
        user = check_claim(uidb64, token)
        key = complete_claim(user, token, GOOD)
        self.assertEqual(Token.objects.get(user=self.lea).key, key)

    def test_a_link_used_meanwhile_is_refused(self):
        uidb64, token = parts(self.lea)
        first, second = check_claim(uidb64, token), check_claim(uidb64, token)
        self.assertIsNotNone(complete_claim(first, token, GOOD))
        self.assertIsNone(complete_claim(second, token, "another-long-phrase"))
        self.lea.refresh_from_db()
        self.assertTrue(self.lea.check_password(GOOD))

    def test_a_user_made_staff_meanwhile_is_refused(self):
        uidb64, token = parts(self.lea)
        user = check_claim(uidb64, token)
        User.objects.filter(pk=self.lea.pk).update(is_staff=True)
        old_key = Token.objects.get(user=self.lea).key
        self.assertIsNone(complete_claim(user, token, GOOD))
        self.lea.refresh_from_db()
        self.assertTrue(self.lea.check_password("old-password"))
        self.assertEqual(Token.objects.get(user=self.lea).key, old_key)
        self.assertFalse(UserProfile.objects.filter(user=self.lea).exists())


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class TestCompleteClaimRace(TransactionTestCase):
    """
    One link used twice at the same moment: the user's row lock lets one use set the
    password, and the other, reading the row only once the first has committed, finds the
    link dead. Real transactions, one connection per thread, which the single wrapping
    transaction of a TestCase would not allow.
    """

    def setUp(self):
        edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        self.lea = User.objects.create_user(username="leamartin", first_name="Léa")
        Player.objects.create(user=self.lea, edition=edition, rating=5)

    def test_one_link_used_twice_at_once_sets_one_password(self):
        uidb64, token = parts(self.lea)
        user = check_claim(uidb64, token)
        # Inside the locked section each use waits for the other, for a moment only. Without
        # the lock both get there together and both would claim; with it the second is still
        # blocked on the row when the first stops waiting and commits.
        inside = threading.Barrier(2)
        real_is_claimable = claims.is_claimable

        def meet_then_check(candidate):
            try:
                inside.wait(timeout=0.5)
            except threading.BrokenBarrierError:
                pass
            return real_is_claimable(candidate)

        outcomes = {}

        def use(password):
            try:
                outcomes[password] = complete_claim(user, token, password)
            except Exception as error:  # pylint: disable=broad-exception-caught
                outcomes[password] = error
            finally:
                connections.close_all()  # this thread's own connection

        with mock.patch.object(claims, "is_claimable", meet_then_check):
            threads = [
                threading.Thread(target=use, args=(password,))
                for password in (GOOD, "another-long-phrase")
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(len(outcomes), 2)
        self.assertFalse([o for o in outcomes.values() if isinstance(o, Exception)], outcomes)
        winners = [password for password, key in outcomes.items() if key is not None]
        self.assertEqual(len(winners), 1, outcomes)
        self.assertEqual(
            list(Token.objects.filter(user=self.lea).values_list("key", flat=True)),
            [outcomes[winners[0]]],
        )
        self.lea.refresh_from_db()
        self.assertTrue(self.lea.check_password(winners[0]))


@PRIVATE_CACHE
class TestClaimThrottle(ClaimSetup, APITestCase):
    """The POST is a login attempt: the login bucket, per client IP, shared with /auth/token/
    and the admin login. The GET is not throttled."""

    IP = "203.0.113.7"

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.link = path(*parts(self.lea))

    def claim(self, password="123", link=None, ip=IP):
        return self.client.post(
            link or self.link, {"password": password}, format="json", HTTP_X_FORWARDED_FOR=ip
        )

    def exhaust(self):
        for _ in range(LIMIT):
            self.assertEqual(self.claim().status_code, 400)

    def test_posts_get_429_past_the_limit(self):
        self.exhaust()
        response = self.claim()
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    def test_a_good_password_is_refused_too_once_throttled(self):
        self.exhaust()
        self.assertEqual(self.claim(GOOD).status_code, 429)
        self.lea.refresh_from_db()
        self.assertTrue(self.lea.check_password("old-password"))

    def test_a_dead_links_post_counts_too(self):
        for _ in range(LIMIT):
            self.assertEqual(self.claim(link=path("x", "x")).status_code, 404)
        self.assertEqual(self.claim().status_code, 429)

    def test_gets_do_not_spend_the_post_budget(self):
        for _ in range(LIMIT * 2):
            self.assertEqual(
                self.client.get(self.link, HTTP_X_FORWARDED_FOR=self.IP).status_code, 200
            )
        self.exhaust()
        self.assertEqual(self.claim().status_code, 429)
        # Nor are they throttled once the posts are.
        self.assertEqual(self.client.get(self.link, HTTP_X_FORWARDED_FOR=self.IP).status_code, 200)

    def test_each_client_ip_has_its_own_bucket(self):
        self.exhaust()
        self.assertEqual(self.claim(ip="198.51.100.4").status_code, 400)

    def login(self):
        return self.client.post(
            "/auth/token/", {"username": "ana", "password": "guess"}, format="json",
            HTTP_X_FORWARDED_FOR=self.IP,
        )

    def test_failed_logins_spend_the_claim_budget(self):
        for _ in range(LIMIT):
            self.assertEqual(self.login().status_code, 400)
        self.assertEqual(self.claim().status_code, 429)

    def test_claims_spend_the_login_budget(self):
        self.exhaust()
        self.assertEqual(self.login().status_code, 429)


@override_settings(
    PUBLIC_URL="https://ow.example",
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
)
class TestClaimAdminAction(ClaimSetup, TestCase):
    """« Générer un lien d'activation »: one line per selected user, a link or why not."""

    def setUp(self):
        super().setUp()
        self.client.force_login(
            User.objects.create_superuser("root", "root@example.com", "pw")
        )

    def act(self, changelist, rows):
        response = self.client.post(
            changelist,
            {"action": "generate_claim_links", "_selected_action": [r.pk for r in rows],
             "index": 0},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        return [(message.level_tag, str(message)) for message in response.context["messages"]]

    def assert_link_line(self, line, user, label):
        level, text = line
        self.assertEqual(level, "info")
        prefix = f"{label} ({user.username}) : https://ow.example/claim/"
        self.assertTrue(text.startswith(prefix), text)
        uidb64, token = text[len(prefix):].split("/")
        self.assertEqual(check_claim(uidb64, token), user)

    def test_on_players_one_line_per_user(self):
        rows = Player.objects.filter(
            user__in=[self.lea, self.staff, self.gone, self.retired]
        ).order_by("id")
        self.assertEqual(rows.filter(user=self.lea).count(), 2)  # 2024 and 2026: one line

        lines = self.act("/admin/olympic_warriors/player/", rows)

        self.assertEqual(len(lines), 4)
        # By last name: Durand, Lopez, Martin, Petit.
        self.assertEqual(
            lines[0],
            ("warning", "Gaël Durand (gone) : pas de lien, ce compte est désactivé."),
        )
        self.assertEqual(
            lines[1],
            ("warning", "Ana Lopez (ana) : pas de lien, un organisateur garde son propre "
                        "mot de passe."),
        )
        self.assert_link_line(lines[2], self.lea, "Léa Martin")
        self.assertEqual(
            lines[3],
            ("warning", "Rémi Petit (retired) : pas de lien, aucune participation active "
                        "à une édition active."),
        )

    def test_on_profiles_to_reissue_a_link(self):
        profiles = [
            UserProfile.objects.create(user=self.lea, claimed_at=timezone.now()),
            UserProfile.objects.create(user=self.stranger),
        ]

        lines = self.act("/admin/olympic_warriors/userprofile/", profiles)

        self.assertEqual(len(lines), 2)
        self.assertEqual(
            lines[0],
            ("warning", "Sam Blanc (stranger) : pas de lien, aucune participation active "
                        "à une édition active."),
        )
        self.assert_link_line(lines[1], self.lea, "Léa Martin")

    def test_a_user_without_a_name_is_named_by_username(self):
        nameless = self.person("nameless", "", "", self.y2026)
        lines = self.act("/admin/olympic_warriors/player/", nameless.player_set.all())
        self.assert_link_line(lines[0], nameless, "nameless")

    def test_without_a_usable_public_url_no_link_is_generated(self):
        rows = Player.objects.filter(user__in=[self.lea, self.staff])
        for base in ("", "ow.example", "ftp://ow.example"):
            with self.subTest(base=base), override_settings(PUBLIC_URL=base):
                self.assertEqual(
                    self.act("/admin/olympic_warriors/player/", rows),
                    [
                        (
                            "error",
                            "Aucun lien généré : PUBLIC_URL (l'adresse publique du site) "
                            "n'est pas configuré.",
                        )
                    ],
                )


@override_settings(
    PUBLIC_URL="https://ow.example",
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
)
class TestClaimActionPermission(ClaimSetup, TestCase):
    """A claim link lets whoever opens it set the person's password, so only a staff user
    who may change users (auth.change_user) gets the action, whatever their rights on
    players and profiles."""

    CHANGELISTS = ("/admin/olympic_warriors/player/", "/admin/olympic_warriors/userprofile/")

    def setUp(self):
        super().setUp()
        UserProfile.objects.create(user=self.lea)
        self.orga = User.objects.create_user(username="orga", is_staff=True)
        self.orga.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="olympic_warriors",
                codename__in=[
                    "view_player", "change_player", "view_userprofile", "change_userprofile",
                ],
            )
        )
        self.client.force_login(self.orga)

    def actions(self, changelist):
        response = self.client.get(changelist)
        self.assertEqual(response.status_code, 200)
        form = response.context["action_form"]  # None when no action is allowed at all
        return [] if form is None else [name for name, _ in form.fields["action"].choices]

    def posted_messages(self, changelist, rows):
        response = self.client.post(
            changelist,
            {"action": "generate_claim_links", "_selected_action": [r.pk for r in rows],
             "index": 0},
            follow=True,
        )
        return [str(message) for message in response.context["messages"]]

    def test_without_change_user_the_action_is_not_offered(self):
        for changelist in self.CHANGELISTS:
            with self.subTest(changelist=changelist):
                self.assertNotIn("generate_claim_links", self.actions(changelist))
        lines = self.posted_messages(self.CHANGELISTS[0], self.lea.player_set.all())
        self.assertFalse([line for line in lines if "/claim/" in line], lines)

    def test_with_change_user_it_is(self):
        self.orga.user_permissions.add(
            Permission.objects.get(content_type__app_label="auth", codename="change_user")
        )
        for changelist in self.CHANGELISTS:
            with self.subTest(changelist=changelist):
                self.assertIn("generate_claim_links", self.actions(changelist))
        lines = self.posted_messages(self.CHANGELISTS[0], self.lea.player_set.all())
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("Léa Martin (leamartin) : https://ow.example/claim/"))
