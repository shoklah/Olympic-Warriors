"""
Every route of urls.py reaches its view: a function of views.py is wrapped by @api_view
(without it the Response has no renderer and every call 500s) and takes exactly the route's
parameters (a converter named otherwise is a TypeError on every call).
"""

import inspect

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.urls import URLPattern
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from olympic_warriors import urls, views
from olympic_warriors.models import Darts, Edition, Team, TeamResult


def view_routes():
    """(route, parameter names, view) for every route to views.py."""
    return [
        (str(pattern.pattern), set(pattern.pattern.converters), pattern.callback)
        for pattern in urls.urlpatterns
        if isinstance(pattern, URLPattern) and pattern.callback.__module__ == views.__name__
    ]


def wrapped_function(view):
    """The function @api_view wrapped (the free variable of its method handler), or None."""
    for name in view.cls.http_method_names:
        handler = view.cls.__dict__.get(name)
        if inspect.isfunction(handler):
            return inspect.getclosurevars(handler).nonlocals.get("func")
    return None


class TestRoutes(SimpleTestCase):

    def test_routes_are_found(self):
        self.assertGreater(len(view_routes()), 60)

    def test_every_view_is_a_drf_view(self):
        for route, _, view in view_routes():
            with self.subTest(route=route):
                self.assertTrue(hasattr(view, "cls"), f"{view.__name__} lacks @api_view")

    def test_every_view_takes_the_route_parameters(self):
        for route, parameters, view in view_routes():
            view_class = getattr(view, "cls", None)
            if view_class is not None and getattr(views, view_class.__name__, None) is view_class:
                continue  # a class-based view such as the token view: DRF's own signature
            with self.subTest(route=route):
                func = wrapped_function(view) if view_class is not None else None
                self.assertIsNotNone(func, f"{view.__name__}: no @api_view function found")
                arguments = set(list(inspect.signature(func).parameters)[1:])  # after request
                self.assertEqual(arguments, parameters, func.__name__)


class TestTeamResultById(APITestCase):

    def setUp(self):
        edition = Edition.objects.create(
            year=2026, host="Paris", start_date="2026-09-19", end_date="2026-09-20"
        )
        Team.objects.create(name="A", edition=edition)
        self.result = TeamResult.objects.get(discipline=Darts.objects.create(edition=edition))
        user = User.objects.create_user(username="player", password="x")
        self.token = Token.objects.get(user=user).key

    def test_get_result(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")
        response = self.client.get(f"/result/{self.result.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.result.id)

    def test_get_result_needs_a_token(self):
        self.assertEqual(APIClient().get(f"/result/{self.result.id}/").status_code, 401)
