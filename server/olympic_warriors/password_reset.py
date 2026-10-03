"""
Lost password (spec 2026-10-02): a person or an organiser gives their email and, if exactly
one active user of that kind has it, gets a link to the front's /reset page, valid like a
claim link. The caller never learns whether anyone matched, so every outcome is silent for
them; the server log says what happened (by user id, never by address).
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


def _lookup(email):
    """(user, None) for the one active user whose email is `email` (case-insensitive), else
    (None, reason), the reason being worded for the log: no account, or several (which would
    let one address reset another person's account). A deactivated account keeps its email
    but is never looked up: it can reset nothing, and counting it would block the live
    account sharing its address."""
    users = list(
        get_user_model().objects.filter(is_active=True, email__iexact=email.strip())[:2]
    )
    if not users:
        return None, "no account has that address"
    if len(users) > 1:
        return None, "several accounts share that address"
    return users[0], None


def user_for_email(email):
    """The one active user whose email is `email`, else None (see `_lookup`)."""
    return _lookup(email)[0]


def _send(user_id, *mail_args):
    """Hand the mail to the SMTP server (on the dispatch thread) and log the outcome by user
    id, never by address, so a missing mail can be told from a refused one."""
    send_mail(*mail_args)
    logger.info("Password reset: mail for user %s accepted by the mail server", user_id)


def send_reset(email):
    """Mail the reset link when `email` names exactly one user who may reset (claims.unresettable_reason: an active person or organiser). Returns whether a
    mail was dispatched (it leaves on a thread, so timing never tells a match). The caller is
    never told why nothing went out, but the server log is: every silent outcome logs its
    reason at INFO, by user id and never by address, and a missing PUBLIC_URL or EMAIL_HOST
    or a mail failure logs an error."""
    if not isinstance(email, str) or not email.strip():
        logger.info("Password reset skipped: no usable email in the request")
        return False
    user, reason = _lookup(email)
    if user is None:
        logger.info("Password reset skipped: %s", reason)
        return False
    try:
        link = claim_link(user, route="reset")
    except Unclaimable as refusal:
        logger.info("Password reset skipped: user %s cannot reset its password (%s)", user.pk, refusal.reason)
        return False
    except ImproperlyConfigured:
        logger.error("Password reset requested but PUBLIC_URL is not set: no mail sent")
        return False
    if not settings.EMAIL_HOST and settings.EMAIL_BACKEND.endswith("smtp.EmailBackend"):
        logger.error("Password reset requested but EMAIL_HOST is not set: no mail sent")
        return False
    logger.info("Password reset: mail for user %s queued", user.pk)
    dispatch(
        _send,
        user.pk,
        SUBJECT,
        BODY.format(name=user.first_name or user.username, link=link, validity=validity()),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    return True
