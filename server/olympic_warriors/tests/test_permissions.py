"""
Who may call each API route. The API is staff-only by default (IsOrganiser is
DEFAULT_PERMISSION_CLASSES), so a view opens only on purpose: to anyone when its route is in
PUBLIC (with @permission_classes([AllowAny]), or a class view's own permissions), to any
logged-in user, such as a player, when it is in PLAYER (with IsAuthenticated). The tests walk
every route of urls.py, so a new view is closed to players and visitors until it is added to
one of the two lists, and a view opened without being listed fails here too.

Each route is called with every method its view handles, with an id for each converter and
no body. The database holds nothing but the callers, so a view that let a request through
could only answer 200, 400 or 404, never write: only 401 and 403 matter. OPTIONS is left
out: DRF runs the same permission check before it as before the view's own methods, and
drf-spectacular's HTML viewers cannot render it at all (a 500 whoever calls). The admin is
left out too: it is Django's own site, behind its own staff login.
"""

import re

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from django.urls import URLPattern
from django.urls.converters import IntConverter, StringConverter
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from olympic_warriors import urls

# Open to anyone, token or not.
PUBLIC = {
    # the OpenAPI schema and its two viewers (drf-spectacular's SERVE_PERMISSIONS)
    "api/schema/",
    "api/schema/swagger/",
    "api/schema/redoc/",
    # the login itself (DRF's ObtainAuthToken: no permission, LoginRateThrottle)
    "auth/token/",
    # what the front reads: the editions, the summary, the disciplines, the profiles
    "editions/",
    "edition/<int:edition_id>/",
    "edition/year/<int:year>/summary/",
    "discipline/<int:discipline_id>/",
    "disciplines/",
    "disciplines/<int:edition_id>/",
    "profiles/",
    "profile/<int:user_id>/",
}

# Open to any token, a player's included: the game, round and result reads apply the reveal
# rule of the summary (scores null until the discipline is revealed, except for staff), so
# they carry nothing the public summary does not.
PLAYER = {
    "game/<int:game_id>/",
    "games/",
    "games/discipline/<int:discipline_id>/",
    "games/team/<int:team_id>/",
    "games/team/<int:team_id>/played/",
    "games/team/<int:team_id>/refereed/",
    "games/edition/<int:edition_id>/",
    "games/discipline/<int:discipline_id>/team/<int:team_id>/",
    "games/discipline/<int:discipline_id>/team/<int:team_id>/played/",
    "games/discipline/<int:discipline_id>/team/<int:team_id>/refereed/",
    "games/round/<int:round_id>/",
    "round/<int:round_id>/",
    "rounds/",
    "rounds/discipline/<int:discipline_id>/",
    "result/<int:team_result_id>/",
    "results/",
    "results/team/<int:team_id>/",
    "results/discipline/<int:discipline_id>/",
    "results/edition/<int:edition_id>/",
}

# A value for each converter type the routes use; a new type fails the walk until it has one.
SAMPLES = {IntConverter: "1", StringConverter: "x"}

REFUSED = (401, 403)


def sample_url(pattern):
    """The route as a path, each converter replaced by a sample value of its type."""
    converters = pattern.pattern.converters
    return "/" + re.sub(
        r"<(?:\w+:)?(\w+)>",
        lambda match: SAMPLES[type(converters[match.group(1)])],
        str(pattern.pattern),
    )


def routes():
    """(route, url, methods, view) for every route of urls.py but the admin (a resolver)."""
    found = []
    for pattern in urls.urlpatterns:
        if not isinstance(pattern, URLPattern):
            continue
        if pattern.callback.__module__ == "django.views.static":
            continue  # the media files, served by Django in dev only (no permission layer)
        view_class = getattr(pattern.callback, "cls", None)
        methods = sorted(
            method
            for method in getattr(view_class, "http_method_names", [])
            if method != "options" and hasattr(view_class, method)
        )
        found.append((str(pattern.pattern), sample_url(pattern), methods, pattern.callback))
    return found


# A private local-memory cache: /auth/token/ counts every call against the login throttle,
# and the configured cache is a directory in the temp dir that a server in the same
# container shares.
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "permission-tests",
        }
    }
)
class TestPermissions(APITestCase):
    """Every route of urls.py, called without a token, with a player's and with a staff one."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.anonymous = APIClient()
        self.player = self.client_for(User.objects.create_user(username="player", password="x"))
        self.staff = self.client_for(
            User.objects.create_user(username="staff", password="x", is_staff=True)
        )

    @staticmethod
    def client_for(user):
        """A client sending the user's own token, through the real token authentication."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.get(user=user).key}")
        return client

    def calls(self, selected):
        """(route, method, url) for every method of every route `selected(route)` keeps."""
        for route, url, methods, _ in routes():
            if selected(route):
                for method in methods:
                    yield route, method, url

    @staticmethod
    def status(client, method, url):
        return getattr(client, method)(url).status_code

    def test_the_walk_finds_every_route(self):
        found = {route: (methods, view) for route, _, methods, view in routes()}
        self.assertGreater(len(found), 60)
        self.assertIn("auth/token/", found)
        self.assertIn("api/schema/", found)
        for route, (methods, view) in found.items():
            with self.subTest(route=route):
                self.assertTrue(hasattr(view, "cls"), "not a DRF view: no permission check")
                self.assertTrue(methods, "no method to call")

    def test_the_lists_name_routes(self):
        found = {route for route, _, _, _ in routes()}
        self.assertEqual(PUBLIC - found, set(), "PUBLIC lists a route urls.py does not have")
        self.assertEqual(PLAYER - found, set(), "PLAYER lists a route urls.py does not have")
        self.assertEqual(PUBLIC & PLAYER, set())

    def test_public_routes_answer_without_a_token(self):
        for route, method, url in self.calls(lambda route: route in PUBLIC):
            with self.subTest(route=route, method=method):
                self.assertNotIn(self.status(self.anonymous, method, url), REFUSED)

    def test_player_routes_answer_a_player_token(self):
        for route, method, url in self.calls(lambda route: route in PLAYER):
            with self.subTest(route=route, method=method):
                self.assertNotIn(self.status(self.player, method, url), REFUSED)

    def test_player_routes_refuse_an_anonymous_call(self):
        for route, method, url in self.calls(lambda route: route in PLAYER):
            with self.subTest(route=route, method=method):
                self.assertEqual(self.status(self.anonymous, method, url), 401)

    def test_every_other_route_refuses_a_player_token(self):
        for route, method, url in self.calls(lambda route: route not in PUBLIC | PLAYER):
            with self.subTest(route=route, method=method):
                self.assertEqual(self.status(self.player, method, url), 403)

    def test_every_other_route_refuses_an_anonymous_call(self):
        for route, method, url in self.calls(lambda route: route not in PUBLIC | PLAYER):
            with self.subTest(route=route, method=method):
                self.assertEqual(self.status(self.anonymous, method, url), 401)

    def test_staff_reach_every_route(self):
        for route, method, url in self.calls(lambda route: True):
            with self.subTest(route=route, method=method):
                self.assertNotIn(self.status(self.staff, method, url), REFUSED)
