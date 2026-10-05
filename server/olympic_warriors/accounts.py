"""
What a logged-in person does to their own account (spec 2026-10-02): change email or
password after proving the current password, or deactivate. Views check who the caller is
and throttle; the rules live here.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.views.decorators.debug import sensitive_variables
from rest_framework.authtoken.models import Token

from .avatars import remove_photo
from .models import Player, PlayerSport, UserProfile


@sensitive_variables("password")
def password_ok(user, password):
    """Whether `password` is the user's current one (a non-string never is)."""
    return isinstance(password, str) and user.check_password(password)


def change_email(user, email):
    """Store the address, stripped and lower-cased. Raises ValidationError(code
    `invalid_email`) for anything that is not an email."""
    email = email.strip().lower() if isinstance(email, str) else ""
    try:
        validate_email(email)
    except ValidationError as error:
        raise ValidationError("invalid email", code="invalid_email") from error
    user.email = email
    user.save(update_fields=["email"])


@sensitive_variables("password")
def change_password(user, password):
    """Set a new password (django's ValidationError with the validators' codes when it is
    refused), replace the DRF token so every older session ends, and return the new key."""
    validate_password(password, user)
    with transaction.atomic():
        user.set_password(password)
        user.save(update_fields=["password"])
        Token.objects.filter(user=user).delete()
        return Token.objects.create(user=user).key


def deactivate(user):
    """Turn the account off and mask the person: no login, no photo, no pins, anonymized,
    and the private registration answers cleared. Player rows stay, so places and badges
    remain on the public site."""
    with transaction.atomic():
        locked = get_user_model().objects.select_for_update().get(pk=user.pk)
        profile, _ = UserProfile.objects.get_or_create(user=locked)
        remove_photo(profile)
        profile.refresh_from_db()
        profile.showcase = []
        profile.anonymized = True
        profile.save(update_fields=["showcase", "anonymized", "updated_at"])
        locked.is_active = False
        # A reactivation must not revive the old password, nor any older reset or claim link
        # (the token hashes the password).
        locked.set_unusable_password()
        locked.save(update_fields=["is_active", "password"])
        Token.objects.filter(user=locked).delete()
        # The registration answers are private personal data: they go with the account. The
        # Player rows stay (rating, team), so places and badges remain.
        Player.objects.filter(user=locked).update(
            global_level=None,
            dietary_restrictions="",
            sport_frequency="",
            team_wishes="",
            attendance_confirmed=False,
        )
        PlayerSport.objects.filter(player__user=locked).delete()
