"""
User endpoints: /users/ and /user/<id>/ expose login names and emails, so they are
organisers only. /user/current/ stays open to any token: the front resolves is_staff with it.
"""

from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase


class TestUserEndpoints(APITestCase):

    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", password="x", email="staff@example.com", is_staff=True
        )
        self.player = User.objects.create_user(
            username="player", password="x", email="player@example.com"
        )

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_need_a_token(self):
        client = APIClient()
        self.assertEqual(client.get("/users/").status_code, 401)
        self.assertEqual(client.get(f"/user/{self.staff.id}/").status_code, 401)

    def test_refuse_a_player(self):
        client = self.as_user(self.player)
        response = client.get("/users/")
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(b"staff@example.com", response.content)
        self.assertEqual(client.get(f"/user/{self.staff.id}/").status_code, 403)
        self.assertEqual(client.get(f"/user/{self.player.id}/").status_code, 403)

    def test_refuse_a_player_before_looking_the_user_up(self):
        # 403, not 404: a player cannot probe which ids exist.
        self.assertEqual(self.as_user(self.player).get("/user/999/").status_code, 403)

    def test_list_all_users_for_an_organiser(self):
        response = self.as_user(self.staff).get("/users/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {(row["username"], row["email"]) for row in response.data},
            {("staff", "staff@example.com"), ("player", "player@example.com")},
        )
        self.assertNotIn("password", response.data[0])

    def test_get_one_user_for_an_organiser(self):
        client = self.as_user(self.staff)
        response = client.get(f"/user/{self.player.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "player")
        self.assertEqual(client.get("/user/999/").status_code, 404)

    def test_current_user_stays_open_to_any_token(self):
        self.assertEqual(APIClient().get("/user/current/").status_code, 401)
        response = self.as_user(self.player).get("/user/current/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "player")
        self.assertFalse(response.data["is_staff"])
