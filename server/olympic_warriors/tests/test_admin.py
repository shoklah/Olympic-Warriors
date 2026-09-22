"""
Admin changelists must survive a search: search_fields that name a foreign key
instead of a text column raise FieldError as soon as someone types in the box.
"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase, override_settings


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestAdminChangelistSearch(TestCase):

    def setUp(self):
        User.objects.create_superuser("root", "root@example.com", "pw")
        self.client.force_login(User.objects.get(username="root"))

    def test_every_changelist_accepts_a_search(self):
        failures = []
        for model, model_admin in admin.site._registry.items():
            if not model_admin.search_fields:
                continue
            url = f"/admin/{model._meta.app_label}/{model._meta.model_name}/"
            try:
                response = self.client.get(url, {"q": "x"})
                status = response.status_code
            except Exception as exc:  # pylint: disable=broad-except
                status = f"{type(exc).__name__}: {exc}"
            if status != 200:
                failures.append(f"{model.__name__}: {status}")
        self.assertEqual(failures, [])
