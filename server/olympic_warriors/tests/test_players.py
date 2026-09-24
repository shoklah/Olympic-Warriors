from rest_framework.test import APITestCase
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from olympic_warriors.models import Player, Edition


class TestPlayerSetup(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(
            email="johndoe@email.com",
            first_name="John",
            last_name="Doe",
            password="password",
            username="johndoe",
        )

        Edition.objects.create(
            year=2022,
            host="Qatar",
            start_date="2022-11-21",
            end_date="2022-12-18",
            is_active=True,
        )

        Player.objects.create(
            user=self.user,
            edition=Edition.objects.get(year=2022),
            rating=5,
        )


class TestPlayersAPI(TestPlayerSetup):

    def test_get_players_unauthenticated_is_rejected(self):
        response = self.client.get("/players/")
        self.assertEqual(response.status_code, 401)

    def test_get_players(self):
        # Staff-only, like the rest of the API outside the reveal-aware reads.
        orga = User.objects.create_user(username="orga", password="x", is_staff=True)
        self.client.force_authenticate(user=orga)
        response = self.client.get("/players/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["first_name"], "John")
        self.assertEqual(response.data[0]["last_name"], "Doe")
        self.assertEqual(response.data[0]["rating"], 5)
