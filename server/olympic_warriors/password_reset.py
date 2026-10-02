"""
Lost password (spec 2026-10-02): a person gives their email and, if exactly one claimable
person has it, gets a link to the front's /reset page, valid like a claim link. The caller
never learns whether anyone matched, so every outcome here is silent.
"""

import logging
import threading

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
    "nouveau (valable {validity}) :\n\n{link}\n\n"
    "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : rien ne change.\n"
)


def validity():
    """How long a link lives, in French whole days (at least one), from
    PASSWORD_RESET_TIMEOUT."""
    days = max(1, -(-settings.PASSWORD_RESET_TIMEOUT // 86400))
    return f"{days} jour{'s' if days > 1 else ''}"


def dispatch(func, *args):
    """Run `func(*args)` on a daemon thread, so the request answers in the same time whether
    or not a mail goes out. Failures are logged, never raised."""

    def run():
        try:
            func(*args)
        except Exception:  # pylint: disable=broad-except  # SMTP down: nobody to tell
            logger.exception("Password reset mail failed")

    threading.Thread(target=run, daemon=True).start()


def user_for_email(email):
    """The one user whose email is `email` (case-insensitive), else None: no match, or
    several, which would let one address reset another person's account."""
    users = list(get_user_model().objects.filter(email__iexact=email.strip())[:2])
    return users[0] if len(users) == 1 else None


def send_reset(email):
    """Mail the reset link when `email` names exactly one claimable person. Returns whether a
    mail was dispatched (it leaves on a thread, so timing never tells a match); logs, never
    raises, on a missing PUBLIC_URL, a missing EMAIL_HOST or a mail failure."""
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
    if not settings.EMAIL_HOST and settings.EMAIL_BACKEND.endswith("smtp.EmailBackend"):
        logger.error("Password reset requested but EMAIL_HOST is not set: no mail sent")
        return False
    dispatch(
        send_mail,
        SUBJECT,
        BODY.format(name=user.first_name or user.username, link=link, validity=validity()),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    return True
