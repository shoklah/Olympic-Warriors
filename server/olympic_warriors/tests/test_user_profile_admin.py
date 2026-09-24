"""
The UserProfile admin, where organisers moderate photos: a thumbnail per person, the lock
edited from the list, filters on the lock, the photo and the claim, and two actions that
take photos down (the second also locks). Organisers never upload a photo, so no form of
it has a file input, and the model has no is_active, so its changelist is not filtered on
one.
"""

import datetime

from django.contrib.auth.models import User
from django.test import override_settings

from olympic_warriors.avatars import store_photo
from olympic_warriors.models import Badge, UserProfile
from olympic_warriors.tests.test_avatars import MediaRootTestCase, encode, picture, upload

PROFILES = "/admin/olympic_warriors/userprofile/"


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class TestUserProfileAdmin(MediaRootTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser("admin", "a@b.c", "pw"))
        self.ana = self.profile("ana", "Ana", "Lopez", photo=True)
        self.bob = self.profile("bob", "Bob", "Martin", claimed=True)
        self.cleo = self.profile("cleo", "Cléo", "Durand", photo=True, claimed=True)

    @staticmethod
    def profile(username, first, last, photo=False, claimed=False):
        """A person's profile, with a stored photo and a claim date when asked."""
        user = User.objects.create(username=username, first_name=first, last_name=last)
        profile = UserProfile.objects.create(
            user=user,
            claimed_at=datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)
            if claimed
            else None,
        )
        if photo:
            store_photo(profile, upload(encode(picture(), "JPEG")))
            profile.refresh_from_db()
        return profile

    def listed(self, **params):
        """The profiles a changelist request lists, in order."""
        response = self.client.get(PROFILES, params)
        self.assertEqual(response.status_code, 200)
        return list(response.context["cl"].result_list)

    def act(self, name, *profiles):
        """Run the changelist action `name` on `profiles`, on-commit callbacks included,
        and return the messages shown after it."""
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                PROFILES,
                {"action": name, "_selected_action": [p.pk for p in profiles], "index": 0},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        return [str(message) for message in response.context["messages"]]

    def test_the_changelist_shows_every_profile_with_its_thumbnail(self):
        response = self.client.get(PROFILES)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.listed(), [self.cleo, self.ana, self.bob]  # by last name: Durand, Lopez, Martin
        )
        self.assertContains(response, f'<img src="{self.ana.photo_small.url}"')
        self.assertContains(response, f'<img src="{self.cleo.photo_small.url}"')
        self.assertContains(response, "Ana Lopez")
        self.assertNotIn("is_active__exact", response.wsgi_request.GET)

    def test_the_lock_is_edited_from_the_list(self):
        response = self.client.get(PROFILES)
        editable = response.context["cl"].formset.forms[0].fields
        self.assertEqual(set(editable), {"photo_locked", "id"})

        form = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "3",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-id": self.cleo.pk,
            "form-1-id": self.ana.pk,
            "form-1-photo_locked": "on",
            "form-2-id": self.bob.pk,
            "_save": "Enregistrer",
        }
        saved = self.client.post(PROFILES, form)

        self.assertEqual(saved.status_code, 302)
        self.assertEqual(
            list(UserProfile.objects.filter(photo_locked=True)), [self.ana]
        )

    def test_the_search_matches_names_and_usernames(self):
        self.assertEqual(self.listed(q="Lopez"), [self.ana])
        self.assertEqual(self.listed(q="Cléo"), [self.cleo])
        self.assertEqual(self.listed(q="bob"), [self.bob])

    def test_the_filters(self):
        UserProfile.objects.filter(pk=self.bob.pk).update(photo_locked=True)

        self.assertEqual(self.listed(has_photo="1"), [self.cleo, self.ana])
        self.assertEqual(self.listed(has_photo="0"), [self.bob])
        self.assertEqual(self.listed(claimed="1"), [self.cleo, self.bob])
        self.assertEqual(self.listed(claimed="0"), [self.ana])
        self.assertEqual(self.listed(photo_locked__exact="1"), [self.bob])
        self.assertEqual(self.listed(photo_locked__exact="0"), [self.cleo, self.ana])

    def test_the_actions_are_the_moderation_ones(self):
        response = self.client.get(PROFILES)

        choices = [name for name, _ in response.context["action_form"].fields["action"].choices]
        self.assertEqual(choices, ["", "remove_photos", "remove_and_lock"])

    def test_removing_the_photos_of_a_selection(self):
        files = [self.ana.photo.name, self.ana.photo_small.name, self.cleo.photo.name]

        messages = self.act("remove_photos", self.ana, self.bob, self.cleo)

        self.assertEqual(messages, ["Photo(s) retirée(s) : 2 sur 3 profil(s) sélectionné(s)."])
        self.assertEqual(self.avatar_files(), [])
        for profile in (self.ana, self.bob, self.cleo):
            profile.refresh_from_db()
            self.assertEqual((profile.photo.name, profile.photo_small.name), ("", ""))
            self.assertFalse(profile.photo_locked)
        self.assertFalse(any(self.exists(path) for path in files))

    def test_removing_and_locking(self):
        messages = self.act("remove_and_lock", self.ana, self.bob)

        self.assertEqual(
            messages, ["Photo(s) retirée(s) : 1 ; profil(s) verrouillé(s) : 2."]
        )
        for profile in (self.ana, self.bob):
            profile.refresh_from_db()
            self.assertFalse(profile.photo)
            self.assertTrue(profile.photo_locked)
        self.cleo.refresh_from_db()
        self.assertTrue(self.cleo.photo)
        self.assertFalse(self.cleo.photo_locked)
        self.assertEqual(len(self.avatar_files()), 2)  # Cléo's

    def test_the_change_form_shows_the_photo_but_offers_no_upload(self):
        UserProfile.objects.filter(pk=self.ana.pk).update(
            showcase=[Badge.Codes.GOAT, Badge.Codes.CHAMPION]
        )

        response = self.client.get(f"{PROFILES}{self.ana.pk}/change/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'type="file"')
        self.assertContains(response, f'href="{self.ana.photo.url}"')
        self.assertContains(response, f'<img src="{self.ana.photo_small.url}"')
        self.assertContains(response, "G.O.A.T, Champion")
        form = response.context["adminform"].form
        self.assertEqual(list(form.fields), ["photo_locked"])

    def test_the_change_form_only_changes_the_lock(self):
        url = f"{PROFILES}{self.ana.pk}/change/"
        photo = self.ana.photo.name

        response = self.client.post(
            url,
            {"photo_locked": "on", "showcase": "goat", "user": self.bob.user_id, "photo": ""},
        )

        self.assertEqual(response.status_code, 302)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.photo_locked)
        self.assertEqual(self.ana.showcase, [])
        self.assertEqual(self.ana.user_id, User.objects.get(username="ana").id)
        self.assertEqual(self.ana.photo.name, photo)

    def test_deleting_a_person_through_the_user_admin_deletes_their_files(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/admin/auth/user/{self.ana.user_id}/delete/", {"post": "yes"}
            )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username="ana").exists())
        self.assertEqual(len(self.avatar_files()), 2)  # Cléo's
        self.assertFalse(self.exists(self.ana.photo.name))
        self.assertFalse(self.exists(self.ana.photo_small.name))

    def test_deleting_a_profile_from_its_page_deletes_its_files(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f"{PROFILES}{self.cleo.pk}/delete/", {"post": "yes"})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(UserProfile.objects.filter(pk=self.cleo.pk).exists())
        self.assertEqual(len(self.avatar_files()), 2)  # Ana's
        self.assertFalse(self.exists(self.cleo.photo.name))

    def test_profiles_are_not_added_by_hand(self):
        response = self.client.get(f"{PROFILES}add/")

        self.assertEqual(response.status_code, 403)
