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

    def test_a_staff_line_gets_no_claim_link(self):
        User.objects.create(username="boss", email="boss@example.com", is_staff=True)

        response = self.post(lines="Big Boss, boss@example.com")

        text = "\n".join(self.messages(response))
        self.assertIn("organisateur", text)
        self.assertNotIn("/claim/", text)

    def test_a_view_only_organiser_cannot_use_it(self):
        viewer = User.objects.create_user("viewer", password="pw", is_staff=True)
        viewer.user_permissions.add(
            Permission.objects.get(content_type__app_label="olympic_warriors", codename="view_userprofile")
        )
        self.client.force_login(viewer)

        self.assertEqual(self.client.get(INVITE).status_code, 403)
        self.assertEqual(self.client.post(INVITE, {"lines": "A B, a@example.com"}).status_code, 403)
