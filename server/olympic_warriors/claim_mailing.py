"""
Mail every person who has no account yet their claim link (spec 2026-10-04): the one-off
rollout behind `manage.py send_claim_links`. The link is the same `claims.claim_link` an
organiser makes in the admin; only the sending is new, and it is a batch run from the host,
never a request.

Who gets one: an active person (claims.unclaimable_reason), not yet claimed, whose email is
a valid address that is not the organisers' own olympicwarriors.com (subdomains included).
Several eligible users may share an address: each is mailed their own link, and the plan
reports the address, since self-service reset matches nobody when an address is shared.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, get_connection
from django.core.validators import validate_email
from django.conf import settings

from .claims import claim_link, unclaimable_reason
from .password_reset import validity
from .profiles import person_players

logger = logging.getLogger(__name__)

INTERNAL_DOMAIN = "olympicwarriors.com"

SUBJECT = "Olympic Warriors : activez votre compte"
BODY = (
    "Bonjour {name},\n\n"
    "Vous avez désormais accès à votre compte Olympic Warriors : votre profil, vos badges "
    "et votre photo. Ouvrez ce lien pour choisir votre mot de passe (valable {validity}) :\n\n"
    "{link}\n\n"
    "Identifiant : {username}\n\n"
    "Si le lien a expiré, rendez-vous sur {forgot} avec cette adresse e-mail pour en "
    "recevoir un nouveau.\n"
)


@dataclass
class Plan:
    recipients: list = field(default_factory=list)
    skipped: dict = field(default_factory=lambda: defaultdict(list))  # reason -> users
    shared: dict = field(default_factory=dict)  # lower-cased address -> users sharing it


def is_internal(email):
    domain = email.rpartition("@")[2].lower()
    return domain == INTERNAL_DOMAIN or domain.endswith("." + INTERNAL_DOMAIN)


def _email_problem(email):
    if not email:
        return "no_email"
    try:
        validate_email(email)
    except ValidationError:
        return "invalid_email"
    return "internal" if is_internal(email) else None


def plan():
    """Who would be mailed and who is left out (reason -> users), over the people: users with
    an active player in an active edition."""
    users = (
        get_user_model()
        .objects.filter(pk__in=person_players().values("user"))
        .select_related("profile")
        .order_by("username")
    )
    result = Plan()
    by_address = defaultdict(list)
    for user in users:
        reason = unclaimable_reason(user)
        if reason is None and getattr(user, "profile", None) and user.profile.claimed_at:
            reason = "claimed"
        if reason is None:
            reason = _email_problem(user.email.strip())
        if reason is not None:
            result.skipped[reason].append(user)
            continue
        result.recipients.append(user)
        by_address[user.email.strip().lower()].append(user)
    result.shared = {a: u for a, u in by_address.items() if len(u) > 1}
    return result


def message(user):
    link = claim_link(user)
    forgot = link.rsplit("/claim/", 1)[0] + "/forgot"
    body = BODY.format(
        name=user.first_name or user.username,
        validity=validity(),
        link=link,
        username=user.username,
        forgot=forgot,
    )
    return EmailMessage(SUBJECT, body, settings.DEFAULT_FROM_EMAIL, [user.email.strip()])


def send(recipients):
    """Mail each of `recipients` their link; a failure is logged (by user id) and counted, the
    rest still go. Returns (sent, failed)."""
    sent = failed = 0
    with get_connection() as connection:
        for user in recipients:
            try:
                msg = message(user)
                msg.connection = connection
                msg.send()
                sent += 1
            except Exception:  # pylint: disable=broad-except  # SMTP hiccup: keep going
                logger.exception("Claim mail for user %s failed", user.pk)
                failed += 1
    return sent, failed
