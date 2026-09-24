"""
Claim links: how a person gets an account (see the player profile customization design spec
under docs/superpowers/specs/). Nothing sends email: an organiser generates a link in the
admin and sends it however they like; the person opens it, sees their username, and chooses
a password.

The rules:
- a user is claimable when they are a person (an active Player in an active edition, the
  profiles' definition), active, and neither staff nor superuser: organisers keep their own
  passwords, and a link must never hand over an account with admin rights;
- a link is <PUBLIC_URL>/claim/<uidb64>/<token>, the token from Django's
  default_token_generator: a hash of the password hash, last_login, email and a timestamp,
  so nothing is stored, a link expires after PASSWORD_RESET_TIMEOUT (a week), and every
  link of a person dies once any of them sets the password. PUBLIC_URL is optional, so a
  deploy never fails on it, but no link is made without an absolute http(s) address:
  a relative one would reach nobody;
- a link that fails for any reason (unreadable, nobody, not claimable, bad or expired
  token) fails the same way, so the endpoint tells nobody who exists;
- completing a claim re-checks the link under the user's row lock, so two uses of one link
  racing each other set one password, and a user made staff or deactivated since the link
  was read is refused; it then sets the password, replaces the DRF token (every older
  session ends: the old token is deleted, and Django sessions check the password hash) and
  stamps UserProfile.claimed_at.
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.debug import sensitive_variables
from rest_framework.authtoken.models import Token

from .models import UserProfile
from .profiles import is_person

# Why a user cannot be claimed (the admin words them).
STAFF = "staff"
INACTIVE = "inactive"
NOT_A_PERSON = "not_a_person"


class Unclaimable(ValueError):
    """No claim link for this user; `reason` is STAFF, INACTIVE or NOT_A_PERSON."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


# auth_user.id is a 32-bit serial: a larger number names nobody, so it never reaches a query.
MAX_USER_ID = 2**31 - 1


def unclaimable_reason(user):
    """STAFF, INACTIVE or NOT_A_PERSON, checked in that order, or None for a claimable
    user. One query, for the person check, and only when the flags pass."""
    if user.is_staff or user.is_superuser:
        return STAFF
    if not user.is_active:
        return INACTIVE
    if not is_person(user):
        return NOT_A_PERSON
    return None


def is_claimable(user):
    """A person, active, neither staff nor superuser: the only users a claim link is for."""
    return unclaimable_reason(user) is None


def public_url():
    """PUBLIC_URL without its trailing slash, or ImproperlyConfigured unless it is an
    absolute http(s) address: empty or relative, a link would lead nowhere."""
    base = settings.PUBLIC_URL.strip().rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ImproperlyConfigured("PUBLIC_URL must be the site's absolute http(s) address")
    return base


def claim_link(user):
    """The front's claim page for `user`. Raises ImproperlyConfigured without a usable
    PUBLIC_URL, then Unclaimable when no link is for this user."""
    base = public_url()
    reason = unclaimable_reason(user)
    if reason is not None:
        raise Unclaimable(reason)
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{base}/claim/{uidb64}/{token}"


def _user(uidb64):
    """The user a link's uidb64 names, or None. Only the canonical spelling of an id, the one
    claim_link() writes, is read, so no other text reaches the database."""
    try:
        pk = int(urlsafe_base64_decode(uidb64).decode("ascii"))
    except ValueError:  # not base64, not ASCII (UnicodeDecodeError), not a number
        return None
    if not 0 < pk <= MAX_USER_ID or urlsafe_base64_encode(force_bytes(pk)) != uidb64:
        return None
    return get_user_model().objects.filter(pk=pk).first()


def check_claim(uidb64, token):
    """The claimable user a valid, unexpired link is for, else None whatever went wrong."""
    user = _user(uidb64)
    if user is None or not default_token_generator.check_token(user, token):
        return None
    if not is_claimable(user):
        return None
    return user


@sensitive_variables("password")  # never in an error report
def complete_claim(user, token, password):
    """
    Set the password chosen through the link (`user` from check_claim(), `token` the link's
    token) and return the user's new DRF token key. Raises django's ValidationError when the
    password fails AUTH_PASSWORD_VALIDATORS; returns None, changing nothing, when the link
    no longer holds once the user's row is locked (used meanwhile, or the user is no longer
    claimable).
    """
    validate_password(password, user)
    with transaction.atomic():
        locked = get_user_model().objects.select_for_update().filter(pk=user.pk).first()
        if locked is None or not default_token_generator.check_token(locked, token):
            return None
        if not is_claimable(locked):
            return None
        locked.set_password(password)
        locked.save(update_fields=["password"])
        Token.objects.filter(user=locked).delete()
        key = Token.objects.create(user=locked).key
        profile, _ = UserProfile.objects.get_or_create(user=locked)
        profile.claimed_at = timezone.now()
        profile.save(update_fields=["claimed_at", "updated_at"])
    return key
