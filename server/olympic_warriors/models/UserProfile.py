from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db import models

from .Badge import Badge


class UserProfile(models.Model):
    """
    What a person adds to their public profile, and how organisers moderate it (see the
    player profile customization design spec under docs/superpowers/specs/).

    The row is created lazily, with get_or_create on the first claim or edit: no signal and
    no backfill, and a missing row reads as no photo, the automatic showcase and an
    unclaimed account. It has no is_active: it is a one-to-one satellite of User, not
    soft-deleted data of an edition, so its admin does not call request_only_active (which
    would filter its changelist on a field it lacks). The files behind photo and
    photo_small are written and deleted by olympic_warriors.avatars, never by save(). It
    is not in an edition export (transfer.NOT_EXPORTED): it lives on prod only.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    # Two WebP squares from the same upload: 512 px for the profile header, 128 px
    # everywhere else. Fresh names per upload, so a URL never changes content.
    photo = models.ImageField(upload_to="avatars/", blank=True)
    photo_small = models.ImageField(upload_to="avatars/", blank=True)
    # Set by an organiser: no more uploads (the person can still delete their photo).
    photo_locked = models.BooleanField(default=False)
    # The pinned badge codes, in the person's order; empty means the automatic showcase.
    showcase = ArrayField(
        models.CharField(max_length=32, choices=Badge.Codes.choices),
        size=3,
        default=list,
        blank=True,
    )
    # When the person set a password through a claim link.
    claimed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username
