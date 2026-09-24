"""
The caller's own account (see the player profile customization design spec under
docs/superpowers/specs/, §5): GET /me/ answers any logged-in user, organisers who never
played included, and runs on every page the front renders, so it stays at ME_QUERIES and
never creates a profile row; PUT and DELETE /me/photo/ and PUT /me/showcase/ act on a
person's own profile only (404 for anyone else). A photo upload is throttled per user
(PhotoRateThrottle), a body too big to be a photo is refused before it is read, and a
person can always take their photo down, locked or not.
"""

import os
import re
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
from rest_framework.authtoken.models import Token
from rest_framework.parsers import MultiPartParser
from rest_framework.test import APIClient, APITestCase

from olympic_warriors.avatars import MAX_BYTES
from olympic_warriors.badges import badge_stats, profile_badges, showcase
from olympic_warriors.config import DevConfig, ProdConfig
from olympic_warriors.models import Badge, Edition, Player, Team, UserProfile
from olympic_warriors.profiles import person_ids
from olympic_warriors.tests.test_avatars import (
    MediaRootTestCase,
    encode,
    gif_claiming,
    picture,
    png_claiming,
)
from olympic_warriors.throttling import PhotoRateThrottle
from olympic_warriors.views import MULTIPART_ALLOWANCE

C = Badge.Codes

# The token (with its user), then the user's profile row and person flag in one query: no
# badge, standings or leaderboard work, since the front calls /me/ on every page.
ME_QUERIES = 2
# The token, the person check, the caller's badges, the profile row read then its showcase
# written, then the rarity counts (the people, then their badges). The first save instead
# creates the row: a savepoint around its insert, then the showcase written as before.
SHOWCASE_PUT_QUERIES = 7

LIMIT = PhotoRateThrottle().num_requests
NOT_A_PERSON = {"error": "not_a_person"}
INVALID_SHOWCASE = {"error": "invalid_showcase"}

PRIVATE_CACHE = override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "me-tests",
        }
    }
)


class MeSetup:
    """
    Léa, Bob and Chloé (staff, and a player too) are people of 2025. Olga is an organiser
    who never played, Rémi played only in an inactive edition and Bea's only player row is
    inactive: none of the three is a person.
    """

    def setUp(self):
        super().setUp()
        self.y2025 = Edition.objects.create(
            year=2025, host="Lyon", start_date="2025-09-20", end_date="2025-09-21"
        )
        self.old = Edition.objects.create(
            year=2019, host="Brest", start_date="2019-09-21", end_date="2019-09-22",
            is_active=False,
        )
        self.loups = Team.objects.create(name="Loups", edition=self.y2025)
        self.lea = self.user("leamartin", "Léa", "Martin", self.y2025)
        self.bob = self.user("bobpetit", "Bob", "Petit", self.y2025)
        self.chloe = self.user("chloe", "Chloé", "Dupont", self.y2025, is_staff=True)
        self.olga = self.user("olga", "Olga", "Rousseau", is_staff=True)
        self.remi = self.user("remi", "Rémi", "Petit", self.old)
        self.bea = self.user("bea", "Bea", "Roux")
        Player.objects.create(user=self.bea, edition=self.y2025, rating=5, is_active=False)

    def user(self, username, first_name, last_name, *editions, **flags):
        user = User.objects.create_user(
            username=username, first_name=first_name, last_name=last_name,
            email=f"{username}@mail.example", **flags,
        )
        for edition in editions:
            team = self.loups if edition == self.y2025 else None
            Player.objects.create(user=user, edition=edition, rating=5, team=team)
        return user

    def login(self, user):
        """Send the user's own token, through the real token authentication."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.get(user=user).key}")

    def me(self):
        response = self.client.get("/me/")
        self.assertEqual(response.status_code, 200)
        return response.data


class TestMe(MeSetup, APITestCase):
    def test_a_token_is_needed(self):
        self.assertEqual(self.client.get("/me/").status_code, 401)

    def test_a_person_without_a_profile_row(self):
        self.login(self.lea)

        self.assertEqual(
            self.me(),
            {
                "id": self.lea.id,
                "first_name": "Léa",
                "last_name": "Martin",
                "username": "leamartin",
                "is_staff": False,
                "is_person": True,
                "photo": None,
                "photo_locked": False,
                "showcase": {"auto": True, "codes": []},
            },
        )

    def test_reading_creates_no_profile_row(self):
        for user in (self.lea, self.olga):
            self.login(user)
            self.me()

        self.assertFalse(UserProfile.objects.exists())

    def test_a_person_with_a_photo_a_lock_and_pins(self):
        base = f"avatars/{self.lea.id}-0123456789ab"
        UserProfile.objects.create(
            user=self.lea, photo=f"{base}.webp", photo_small=f"{base}-sm.webp",
            photo_locked=True, showcase=[C.GOAT, C.CHAMPION],
        )
        self.login(self.lea)

        data = self.me()

        self.assertEqual(
            data["photo"],
            {"large": f"/media/{base}.webp", "small": f"/media/{base}-sm.webp"},
        )
        self.assertTrue(data["photo_locked"])
        # The stored pins, earned or not: the showcase shown is computed on the profile.
        self.assertEqual(data["showcase"], {"auto": False, "codes": [C.GOAT, C.CHAMPION]})

    def test_a_row_without_a_photo_reads_as_none(self):
        UserProfile.objects.create(user=self.lea)
        self.login(self.lea)

        data = self.me()

        self.assertIsNone(data["photo"])
        self.assertFalse(data["photo_locked"])
        self.assertEqual(data["showcase"], {"auto": True, "codes": []})

    def test_an_organiser_who_never_played(self):
        self.login(self.olga)

        data = self.me()

        self.assertEqual((data["id"], data["username"]), (self.olga.id, "olga"))
        self.assertEqual((data["is_staff"], data["is_person"]), (True, False))
        self.assertIsNone(data["photo"])

    def test_an_organiser_who_plays(self):
        self.login(self.chloe)

        data = self.me()

        self.assertEqual((data["is_staff"], data["is_person"]), (True, True))

    def test_a_player_of_an_inactive_edition_or_an_inactive_player_is_not_a_person(self):
        for user in (self.remi, self.bea):
            with self.subTest(user=user.username):
                self.login(user)
                data = self.me()
                self.assertEqual((data["is_staff"], data["is_person"]), (False, False))

    def test_a_fixed_number_of_queries_badges_or_not(self):
        Badge.objects.create(user=self.lea, code=C.CHAMPION, edition=self.y2025)
        self.login(self.lea)
        with self.assertNumQueries(ME_QUERIES):
            self.me()

        UserProfile.objects.create(user=self.lea, photo="avatars/x.webp", showcase=[C.CHAMPION])
        with self.assertNumQueries(ME_QUERIES):
            self.me()

    def test_the_email_stays_out(self):
        self.login(self.lea)

        content = self.client.get("/me/").content

        self.assertNotIn(b"email", content)
        self.assertNotIn(b"mail.example", content)


def photo_upload(data=None, name="photo.jpg"):
    """An uploaded file: a small JPEG by default."""
    return SimpleUploadedFile(name, encode(picture(), "JPEG") if data is None else data)


@PRIVATE_CACHE
class TestMyPhoto(MeSetup, MediaRootTestCase):
    """Every upload counts against the photo throttle: a private local-memory cache, so the
    runs of this module never share the configured file cache's counts (the user ids repeat
    from run to run, and an hour's budget is only ten)."""

    client_class = APIClient

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def put(self, **fields):
        return self.client.put("/me/photo/", fields, format="multipart")

    def put_body(self, body):
        """A PUT of a ready-made multipart body."""
        return self.client.generic("PUT", "/me/photo/", body, content_type=MULTIPART_CONTENT)

    def test_an_upload_answers_its_two_urls_and_stores_both_files(self):
        self.login(self.lea)

        response = self.put(photo=photo_upload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {"photo"})
        large, small = response.data["photo"]["large"], response.data["photo"]["small"]
        match = re.fullmatch(rf"/media/avatars/{self.lea.id}-([0-9a-f]{{12}})\.webp", large)
        self.assertIsNotNone(match, large)
        self.assertEqual(small, f"/media/avatars/{self.lea.id}-{match.group(1)}-sm.webp")
        profile = UserProfile.objects.get(user=self.lea)  # created by the first upload
        self.assertEqual((profile.photo.url, profile.photo_small.url), (large, small))
        self.assertTrue(self.exists(profile.photo.name))
        self.assertTrue(self.exists(profile.photo_small.name))
        self.assertEqual(self.me()["photo"], {"large": large, "small": small})

    def test_a_new_upload_replaces_the_old_files(self):
        self.login(self.lea)
        with self.captureOnCommitCallbacks(execute=True):
            first = self.put(photo=photo_upload()).data["photo"]
        with self.captureOnCommitCallbacks(execute=True):
            second = self.put(photo=photo_upload()).data["photo"]

        self.assertNotEqual(first, second)
        self.assertEqual(
            self.avatar_files(),
            sorted(os.path.basename(url) for url in second.values()),
        )

    def test_a_missing_photo(self):
        self.login(self.lea)

        for fields in ({}, {"photo": "not a file"}, {"picture": photo_upload()}):
            with self.subTest(fields=list(fields)):
                response = self.put(**fields)
                self.assertEqual((response.status_code, response.data), (400, {"error": "missing"}))

    def test_a_refused_upload_creates_no_row(self):
        self.login(self.lea)
        over = self.body_of(MAX_BYTES + MULTIPART_ALLOWANCE)
        for name, send, code in (
            ("missing", lambda: self.put(), "missing"),
            ("a file too large", lambda: self.put(photo=photo_upload(b"\xff" * (MAX_BYTES + 1))),
             "too_large"),
            ("a body too large", lambda: self.put_body(over), "too_large"),
            ("bad format", lambda: self.put(photo=photo_upload(b"hello", "photo.txt")),
             "bad_format"),
            ("too many pixels",
             lambda: self.put(photo=photo_upload(png_claiming(5000, 5000), "photo.png")),
             "too_many_pixels"),
        ):
            with self.subTest(upload=name):
                response = send()
                self.assertEqual((response.status_code, response.data), (400, {"error": code}))
                self.assertFalse(UserProfile.objects.exists())
        self.assertEqual(self.avatar_files(), [])

    def test_a_refused_upload_leaves_an_existing_row_as_it_was(self):
        base = f"avatars/{self.lea.id}-0123456789ab"
        UserProfile.objects.create(
            user=self.lea, photo=f"{base}.webp", photo_small=f"{base}-sm.webp",
            showcase=[C.GOAT],
        )
        self.login(self.lea)

        response = self.put(photo=photo_upload(b"hello", "photo.txt"))

        self.assertEqual(response.status_code, 400)
        profile = UserProfile.objects.get(user=self.lea)
        self.assertEqual((profile.photo.name, profile.showcase), (f"{base}.webp", [C.GOAT]))

    def test_a_format_other_than_jpeg_png_or_webp(self):
        self.login(self.lea)

        for data, name in ((gif_claiming(10, 10), "photo.gif"), (b"hello", "photo.txt")):
            with self.subTest(name=name):
                response = self.put(photo=photo_upload(data, name))
                self.assertEqual(
                    (response.status_code, response.data), (400, {"error": "bad_format"})
                )

    def test_too_many_pixels(self):
        self.login(self.lea)

        response = self.put(photo=photo_upload(png_claiming(5000, 5000), "photo.png"))

        self.assertEqual((response.status_code, response.data), (400, {"error": "too_many_pixels"}))

    def body_of(self, size):
        """A multipart body carrying a `size`-byte photo, as the test client encodes it."""
        return encode_multipart(BOUNDARY, {"photo": photo_upload(b"\xff" * size)})

    def test_a_body_over_the_limit_is_refused_before_it_is_read(self):
        self.login(self.lea)
        limit = MAX_BYTES + MULTIPART_ALLOWANCE
        envelope = len(self.body_of(0))
        at_limit, over = self.body_of(limit - envelope), self.body_of(limit - envelope + 1)
        self.assertEqual((len(at_limit), len(over)), (limit, limit + 1))
        parse = MultiPartParser.parse

        with mock.patch.object(MultiPartParser, "parse", autospec=True, side_effect=parse) as spy:
            refused = self.put_body(over)
            spy.assert_not_called()
            read = self.put_body(at_limit)
            spy.assert_called_once()

        self.assertEqual((refused.status_code, refused.data), (400, {"error": "too_large"}))
        # Read, then refused by store_photo on the file's own size (MAX_BYTES + 1 and more).
        self.assertEqual((read.status_code, read.data), (400, {"error": "too_large"}))
        self.assertEqual(self.avatar_files(), [])

    def test_a_locked_profile_is_refused(self):
        UserProfile.objects.create(user=self.lea, photo_locked=True)
        self.login(self.lea)

        response = self.put(photo=photo_upload())

        self.assertEqual((response.status_code, response.data), (403, {"error": "photo_locked"}))
        self.assertEqual(self.avatar_files(), [])

    def test_a_locked_profile_is_refused_before_the_body_is_read(self):
        UserProfile.objects.create(user=self.lea, photo_locked=True)
        self.login(self.lea)

        with mock.patch.object(MultiPartParser, "parse", autospec=True) as spy:
            response = self.put_body(self.body_of(MAX_BYTES + MULTIPART_ALLOWANCE))

        self.assertEqual((response.status_code, response.data), (403, {"error": "photo_locked"}))
        spy.assert_not_called()

    def test_delete_takes_the_photo_down(self):
        self.login(self.lea)
        self.put(photo=photo_upload())

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete("/me/photo/")

        self.assertEqual((response.status_code, response.content), (204, b""))
        self.assertEqual(self.avatar_files(), [])
        profile = UserProfile.objects.get(user=self.lea)
        self.assertFalse(profile.photo or profile.photo_small)
        self.assertIsNone(self.me()["photo"])

    def test_delete_works_when_locked(self):
        self.login(self.lea)
        self.put(photo=photo_upload())
        UserProfile.objects.filter(user=self.lea).update(photo_locked=True)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete("/me/photo/")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.avatar_files(), [])
        profile = UserProfile.objects.get(user=self.lea)
        self.assertFalse(profile.photo)
        self.assertTrue(profile.photo_locked)

    def test_delete_without_a_photo_or_a_row(self):
        self.login(self.lea)

        self.assertEqual(self.client.delete("/me/photo/").status_code, 204)
        self.assertFalse(UserProfile.objects.exists())

        UserProfile.objects.create(user=self.lea)
        self.assertEqual(self.client.delete("/me/photo/").status_code, 204)

    def test_someone_who_is_not_a_person_gets_404_and_no_row(self):
        for user in (self.olga, self.remi, self.bea):
            self.login(user)
            with self.subTest(user=user.username):
                put = self.put(photo=photo_upload())
                self.assertEqual((put.status_code, put.data), (404, NOT_A_PERSON))
                delete = self.client.delete("/me/photo/")
                self.assertEqual((delete.status_code, delete.data), (404, NOT_A_PERSON))

        self.assertFalse(UserProfile.objects.exists())
        self.assertEqual(self.avatar_files(), [])

    def test_a_token_is_needed(self):
        self.assertEqual(self.put(photo=photo_upload()).status_code, 401)
        self.assertEqual(self.client.delete("/me/photo/").status_code, 401)


@PRIVATE_CACHE
class TestPhotoThrottle(MeSetup, MediaRootTestCase):
    """PHOTO_THROTTLE_RATE uploads per user (10/hour by default), whatever they answer;
    taking a photo down is never counted nor refused."""

    client_class = APIClient

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def put(self, ip="203.0.113.7"):
        """An upload without a file: cheap, and counted like any other."""
        return self.client.put("/me/photo/", {}, format="multipart", HTTP_X_FORWARDED_FOR=ip)

    def exhaust(self):
        for _ in range(LIMIT):
            self.assertEqual(self.put().status_code, 400)

    def test_the_upload_past_the_limit_gets_429(self):
        self.login(self.lea)
        self.exhaust()

        response = self.put()

        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    def test_deletes_are_neither_counted_nor_refused(self):
        self.login(self.lea)
        for _ in range(LIMIT * 2):
            self.assertEqual(self.client.delete("/me/photo/").status_code, 204)
        self.exhaust()
        self.assertEqual(self.put().status_code, 429)

        self.assertEqual(self.client.delete("/me/photo/").status_code, 204)

    def test_the_budget_is_the_users_whatever_the_address(self):
        self.login(self.lea)
        self.exhaust()
        self.assertEqual(self.put(ip="198.51.100.4").status_code, 429)

        self.login(self.bob)
        self.assertEqual(self.put().status_code, 400)

    def test_the_rate_is_ten_an_hour_by_default(self):
        required = {
            "SECRET_KEY": "k", "DEBUG": False, "DB_HOST": "h", "DB_NAME": "n", "DB_USER": "u",
            "DB_PASS": "p", "DB_PORT": 5432,
        }
        with mock.patch.dict(os.environ):
            os.environ.pop("PHOTO_THROTTLE_RATE", None)
            for config in (DevConfig, ProdConfig):
                with self.subTest(config=config.__name__):
                    self.assertEqual(
                        config(_env_file=None, **required).PHOTO_THROTTLE_RATE, "10/hour"
                    )


class TestMyShowcase(MeSetup, APITestCase):
    """
    Léa's badges, and how many of the leaderboard's people hold each: specialist (tier 2,
    Relay) 1, goat 1 (Rémi and Bea hold it too, but are not people), veteran (tier 1) 2,
    champion 2, rookie 3. Her automatic showcase is therefore specialist (1 holder, the
    higher tier), goat (1), veteran (2, the higher tier). Legend is revoked and homecoming
    is of an inactive edition: neither is earned.
    """

    def setUp(self):
        super().setUp()
        badge = Badge.objects.create
        for user in (self.lea, self.bob, self.chloe):
            badge(user=user, code=C.ROOKIE, edition=self.y2025)
        for user in (self.lea, self.bob):
            badge(user=user, code=C.CHAMPION, edition=self.y2025)
            badge(user=user, code=C.VETERAN, edition=self.y2025, tier=1)
        for user in (self.lea, self.remi, self.bea):
            badge(user=user, code=C.GOAT, edition=self.y2025)
        badge(user=self.lea, code=C.SPECIALIST, edition=self.y2025, tier=2, discipline="Relay")
        badge(user=self.lea, code=C.LEGEND, edition=self.y2025, is_active=False)
        badge(user=self.lea, code=C.HOMECOMING, edition=self.old)
        badge(user=self.bob, code=C.THREEPEAT, edition=self.y2025)
        self.login(self.lea)

    AUTOMATIC = {
        "auto": True,
        "badges": [
            {"code": C.SPECIALIST, "tier": 2, "discipline": "Relay"},
            {"code": C.GOAT, "tier": 0, "discipline": None},
            {"code": C.VETERAN, "tier": 1, "discipline": None},
        ],
    }

    def put(self, codes):
        return self.client.put("/me/showcase/", {"codes": codes}, format="json")

    def stored(self):
        return UserProfile.objects.get(user=self.lea).showcase

    def test_pins_round_trip_in_the_persons_order(self):
        response = self.put([C.CHAMPION, C.SPECIALIST, C.ROOKIE])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "auto": False,
                "badges": [
                    {"code": C.CHAMPION, "tier": 0, "discipline": None},
                    {"code": C.SPECIALIST, "tier": 2, "discipline": "Relay"},
                    {"code": C.ROOKIE, "tier": 0, "discipline": None},
                ],
            },
        )
        self.assertEqual(self.stored(), [C.CHAMPION, C.SPECIALIST, C.ROOKIE])
        self.assertEqual(
            self.me()["showcase"],
            {"auto": False, "codes": [C.CHAMPION, C.SPECIALIST, C.ROOKIE]},
        )

    def test_an_empty_list_is_back_to_automatic(self):
        self.put([C.ROOKIE])

        response = self.put([])

        self.assertEqual((response.status_code, response.data), (200, self.AUTOMATIC))
        self.assertEqual(self.stored(), [])
        self.assertEqual(self.me()["showcase"], {"auto": True, "codes": []})

    def test_rarity_counts_only_the_leaderboards_people(self):
        # Goat has 3 holders in the table but 1 among the people: second, not fourth.
        self.assertEqual(Badge.objects.filter(code=C.GOAT).count(), 3)

        self.assertEqual(self.put([]).data, self.AUTOMATIC)

    def test_a_fixed_number_of_queries(self):
        UserProfile.objects.create(user=self.lea)
        with self.assertNumQueries(SHOWCASE_PUT_QUERIES):
            self.assertEqual(self.put([C.GOAT]).status_code, 200)

        UserProfile.objects.all().delete()
        with self.assertNumQueries(SHOWCASE_PUT_QUERIES + 3):  # the first save creates the row
            self.assertEqual(self.put([C.ROOKIE]).status_code, 200)

    def test_saving_writes_the_pins_only(self):
        """A photo stored while the pins were being checked (through another copy of the
        row) survives the save: it writes the showcase alone."""
        UserProfile.objects.create(user=self.lea)
        base = f"avatars/{self.lea.id}-0123456789ab"
        get_or_create = UserProfile.objects.get_or_create

        def read_then_upload_meanwhile(*args, **kwargs):
            found = get_or_create(*args, **kwargs)
            other = UserProfile.objects.get(user=self.lea)
            other.photo, other.photo_small = f"{base}.webp", f"{base}-sm.webp"
            other.save()
            return found

        with mock.patch.object(
            UserProfile.objects, "get_or_create", side_effect=read_then_upload_meanwhile
        ):
            response = self.put([C.GOAT])

        self.assertEqual(response.status_code, 200)
        profile = UserProfile.objects.get(user=self.lea)
        self.assertEqual(profile.showcase, [C.GOAT])
        self.assertEqual(
            (profile.photo.name, profile.photo_small.name), (f"{base}.webp", f"{base}-sm.webp")
        )

    def test_saving_computes_no_leaderboard(self):
        with mock.patch("olympic_warriors.profiles._load", side_effect=AssertionError):
            response = self.put([C.GOAT])

        self.assertEqual(response.status_code, 200)

    def test_an_invalid_showcase_is_refused_and_leaves_the_pins_alone(self):
        self.put([C.GOAT])
        bodies = {
            "not a list": {"codes": C.CHAMPION},
            "null": {"codes": None},
            "no codes": {},
            "a bare list": [C.CHAMPION],
            "four codes": {"codes": [C.CHAMPION, C.ROOKIE, C.VETERAN, C.GOAT]},
            "a duplicate": {"codes": [C.CHAMPION, C.CHAMPION]},
            "a number": {"codes": [1]},
            "a null code": {"codes": [None]},
            "a nested list": {"codes": [[C.CHAMPION]]},
            "an unknown code": {"codes": ["golden-whistle"]},
            "never earned": {"codes": [C.DYNASTY]},
            "someone else's": {"codes": [C.THREEPEAT]},
            "revoked": {"codes": [C.LEGEND]},
            "of an inactive edition": {"codes": [C.CHAMPION, C.HOMECOMING]},
        }
        for name, body in bodies.items():
            with self.subTest(body=name):
                response = self.client.put("/me/showcase/", body, format="json")
                self.assertEqual((response.status_code, response.data), (400, INVALID_SHOWCASE))
                self.assertEqual(self.stored(), [C.GOAT])

    def test_malformed_json_is_an_invalid_showcase(self):
        response = self.client.generic(
            "PUT", "/me/showcase/", '{"codes": [', content_type="application/json"
        )

        self.assertEqual((response.status_code, response.data), (400, INVALID_SHOWCASE))

    def test_a_pin_that_stops_being_earned_falls_out(self):
        self.put([C.GOAT, C.CHAMPION])
        Badge.objects.filter(user=self.lea, code=C.GOAT).update(is_active=False)

        def current():
            holders = badge_stats(person_ids())["holders"]
            return showcase(profile_badges(self.lea.id), self.stored(), holders)

        self.assertEqual(
            current(),
            {"auto": False, "badges": [{"code": C.CHAMPION, "tier": 0, "discipline": None}]},
        )
        # Nor can it be pinned again, while the stored pins stay as the person left them.
        self.assertEqual(self.put([C.GOAT]).status_code, 400)
        self.assertEqual(self.me()["showcase"], {"auto": False, "codes": [C.GOAT, C.CHAMPION]})

        Badge.objects.filter(user=self.lea, code=C.CHAMPION).delete()
        self.assertTrue(current()["auto"])

    def test_an_organiser_who_plays_may_pin(self):
        self.login(self.chloe)

        response = self.put([C.ROOKIE])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserProfile.objects.get(user=self.chloe).showcase, [C.ROOKIE])

    def test_someone_who_is_not_a_person_gets_404_and_no_row(self):
        for user in (self.olga, self.remi, self.bea):
            self.login(user)
            with self.subTest(user=user.username):
                response = self.put([C.GOAT] if user != self.olga else [])
                self.assertEqual((response.status_code, response.data), (404, NOT_A_PERSON))

        self.assertFalse(UserProfile.objects.exists())

    def test_a_token_is_needed(self):
        self.client.credentials()

        self.assertEqual(self.put([]).status_code, 401)
