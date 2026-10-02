"""
Lost password (spec 2026-10-02): a person gives their email and, if exactly one claimable
person has it, gets a link to the front's /reset page, valid like a claim link. The caller
never learns whether anyone matched, so every outcome here is silent.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail

from .claims import Unclaimable, claim_link

logger = logging.getLogger(__name__)

SUBJECT = "Olympic Warriors : réinitialisation de votre mot de passe"
BODY = (
    "Bonjour {name},\n\n"
    "Vous avez demandé à réinitialiser votre mot de passe. Ouvrez ce lien pour en choisir un "
    "nouveau (valable 7 jours) :\n\n{link}\n\n"
    "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : rien ne change.\n"
)


def user_for_email(email):
    """The one user whose email is `email` (case-insensitive), else None: no match, or
    several, which would let one address reset another person's account."""
    users = list(get_user_model().objects.filter(email__iexact=email.strip())[:2])
    return users[0] if len(users) == 1 else None


def send_reset(email):
    """Mail the reset link when `email` names exactly one claimable person. Returns whether a
    mail was sent; logs, never raises, on a missing PUBLIC_URL or a mail failure."""
    if not isinstance(email, str) or not email.strip():
        return False
    user = user_for_email(email)
    if user is None:
        return False
    try:
        link = claim_link(user, route="reset")
    except Unclaimable:
        return False
    except ImproperlyConfigured:
        logger.error("Password reset requested but PUBLIC_URL is not set: no mail sent")
        return False
    try:
        send_mail(
            SUBJECT,
            BODY.format(name=user.first_name or user.username, link=link),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
    except Exception:  # pylint: disable=broad-except  # SMTP down: the caller must not learn it
        logger.exception("Password reset mail failed")
        return False
    return True
