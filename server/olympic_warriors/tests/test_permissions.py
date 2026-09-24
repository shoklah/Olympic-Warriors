"""
Who may call each API route. The API is staff-only by default (IsOrganiser is
DEFAULT_PERMISSION_CLASSES), so a view opens only on purpose: to anyone when its route is in
PUBLIC (with @permission_classes([AllowAny]), or a class view's own permissions), to any
logged-in user, such as a player, when it is in PLAYER (with IsAuthenticated). The tests walk
every route of urls.py, so a new view is closed to players and visitors until it is added to
one of the two lists, and a view opened without being listed fails here too.

The walk enters every include() but the admin's (Django's own site, behind its own staff
login) and calls each route with every method its view handles, OPTIONS included, with a
sample value for each converter and no body. Each sample URL must resolve to its route's own
view, so a shadowed route cannot pass on Django's 404. A view that lets a call through may
answer 400 or 404, never 401, 403 or a 500. No call changes anything: the database holds
only the two users and their tokens, so no id matches a row, and neither user is a person
(no Player row), so a view acting on the caller's own records has none to act on: the photo
and showcase writes answer 404 before touching anything, and no call creates the caller's
UserProfile row (checked after each walk).

The Swagger page is called without OPTIONS: drf-spectacular renders the OPTIONS metadata
through its HTML template, whose {% include template_name_js %} then has no name to include
(TemplateDoesNotExist, a 500 whoever calls).
"""

import re

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from django.urls import URLResolver, include, path, resolve
from django.urls.converters import IntConverter, StringConverter
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from olympic_warriors import urls
from olympic_warriors.models import UserProfile

# Open to anyone, token or not.
PUBLIC = {
    # the OpenAPI schema and its two viewers (drf-spectacular's SERVE_PERMISSIONS)
    "api/schema/",
    "api/schema/swagger/",
    "api/schema/redoc/",
    # the login itself (DRF's ObtainAuthToken: no permission, LoginRateThrottle)
    "auth/token/",
    # a claim link: the link is the credential (its POST shares the login throttle)
    "claim/<str:uidb64>/<str:token>/",
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

# Open to any token, a player's included: the caller's own account (/me/ answers anyone
# logged in; the photo and the showcase answer 404 to someone who is not a person), and the
# game, round and result reads, which apply the reveal rule of the summary (scores null until
# the discipline is revealed, except for staff), so they carry nothing the public summary
# does not.
PLAYER = {
    "me/",
    "me/photo/",
    "me/showcase/",
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

# Routes called with their own methods but not OPTIONS (see the module docstring).
NO_OPTIONS = {"api/schema/swagger/"}

# A value for each converter type the routes use; a new type fails the walk until it has one.
SAMPLES = {IntConverter: "1", StringConverter: "x"}

REFUSED = (401, 403)


def sample_url(route, converters):
    """The route as a path, each converter replaced by a sample value of its type."""
    return "/" + re.sub(
        r"<(?:\w+:)?(\w+)>", lambda match: SAMPLES[type(converters[match.group(1)])], route
    )


def routes(patterns=None, prefix="", converters=None):
    """
    (route, url, methods, view) for every view `patterns` routes (urls.py by default), through
    every include() but the admin's, the route and its converters carrying the include's.
    """
    found = []
    for pattern in urls.urlpatterns if patterns is None else patterns:
        route = prefix + str(pattern.pattern)
        known = {**(converters or {}), **pattern.pattern.converters}
        if isinstance(pattern, URLResolver):
            if pattern.app_name != "admin":  # every AdminSite's urls carry this app name
                found.extend(routes(pattern.url_patterns, route, known))
            continue
        if pattern.callback.__module__ == "django.views.static":
            continue  # the media files, served by Django in dev only (no permission layer)
        view_class = getattr(pattern.callback, "cls", None)
        methods = sorted(
            method
            for method in getattr(view_class, "http_method_names", [])
            if hasattr(view_class, method) and not (method == "options" and route in NO_OPTIONS)
        )
        found.append((route, sample_url(route, known), methods, pattern.callback))
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

    def assert_answers(self, client, method, url):
        """Let through, and answered: neither refused nor a server error."""
        status = self.status(client, method, url)
        self.assertNotIn(status, REFUSED)
        self.assertLess(status, 500)

    def test_the_walk_finds_every_route(self):
        found = {route: (url, methods, view) for route, url, methods, view in routes()}
        self.assertGreater(len(found), 60)
        self.assertIn("auth/token/", found)
        self.assertIn("api/schema/", found)
        for route, (url, methods, view) in found.items():
            with self.subTest(route=route):
                self.assertTrue(hasattr(view, "cls"), "not a DRF view: no permission check")
                self.assertIs(resolve(url).func, view, f"{url} reaches another view")
                self.assertEqual("options" in methods, route not in NO_OPTIONS)
                self.assertGreater(len(methods), 0 if route in NO_OPTIONS else 1)

    def test_the_walk_enters_every_include_but_the_admin(self):
        view = next(view for route, _, _, view in routes() if route == "users/")
        found = routes(
            [
                path("admin/", admin.site.urls),
                path("extra/<int:edition_id>/", include([path("more/<str:code>/", view)])),
            ]
        )
        self.assertEqual(
            [(route, url, methods) for route, url, methods, _ in found],
            [("extra/<int:edition_id>/more/<str:code>/", "/extra/1/more/x/", ["get", "options"])],
        )

    def test_the_lists_name_routes(self):
        found = {route for route, _, _, _ in routes()}
        self.assertEqual(PUBLIC - found, set(), "PUBLIC lists a route urls.py does not have")
        self.assertEqual(PLAYER - found, set(), "PLAYER lists a route urls.py does not have")
        self.assertEqual(NO_OPTIONS - found, set(), "NO_OPTIONS lists a route urls.py lacks")
        self.assertEqual(PUBLIC & PLAYER, set())

    def test_public_routes_answer_without_a_token(self):
        for route, method, url in self.calls(lambda route: route in PUBLIC):
            with self.subTest(route=route, method=method):
                self.assert_answers(self.anonymous, method, url)

    def test_player_routes_answer_a_player_token(self):
        for route, method, url in self.calls(lambda route: route in PLAYER):
            with self.subTest(route=route, method=method):
                self.assert_answers(self.player, method, url)
        self.assertFalse(UserProfile.objects.exists())

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
                self.assert_answers(self.staff, method, url)
        self.assertFalse(UserProfile.objects.exists())
