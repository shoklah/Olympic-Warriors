from rest_framework.test import APIClient, APITestCase

from olympic_warriors.models import Discipline, Edition


class TestPublicEndpoints(APITestCase):
    """
    Editions and disciplines are decorated with AllowAny and must be readable
    without a token, despite the global staff-only default.
    """

    def setUp(self):
        self.client = APIClient()  # no credentials on purpose
        self.edition = Edition.objects.create(
            year=2022,
            host="Qatar",
            start_date="2022-11-21",
            end_date="2022-12-18",
            is_active=True,
        )
        self.discipline = Discipline.objects.create(
            name="Fair",
            edition=self.edition,
            pairing_system=Discipline.PairingSystem.NONE,
        )

    def test_get_editions_unauthenticated(self):
        response = self.client.get("/editions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_get_edition_unauthenticated(self):
        response = self.client.get(f"/edition/{self.edition.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["year"], 2022)

    def test_get_disciplines_unauthenticated(self):
        response = self.client.get("/disciplines/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_get_discipline_unauthenticated(self):
        response = self.client.get(f"/discipline/{self.discipline.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Fair")

    def test_get_disciplines_by_edition_unauthenticated(self):
        response = self.client.get(f"/disciplines/{self.edition.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
