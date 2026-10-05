"""
The bulk invite (spec 2026-10-04): an organiser pastes `Prénom Nom, email` lines, and each
becomes an account the person can claim (a newcomer is created and marked invited) or a
returning account that is reused, and gets a claim link, optionally with a late pass.
Nothing here is logged: the links travel only in the admin's messages.
"""
import re
from dataclasses import dataclass

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils.crypto import get_random_string

from .claims import Unclaimable, claim_link, public_url
from .enrolment import usable_email
from .models import LateRegistration, UserProfile, latest_edition
from .registration import parse_name

CREATED = "created"
REUSED = "reused"
STAFF = "staff"  # an organiser: flagged invited, never given a link
CONFLICT = "conflict"
MALFORMED = "malformed"
DUPLICATE = "duplicate"


@dataclass(frozen=True)
class Invite:
    """A well-formed line of the paste. `username` is derived as the registration import
    derives it (every token joined, lower-cased, accents kept)."""

    line: int
    first_name: str
    last_name: str
    email: str
    username: str


@dataclass(frozen=True)
class Problem:
    """A line that cannot be read."""

    line: int
    text: str
    reason: str


@dataclass(frozen=True)
class InviteResult:
    """What became of one line: `status` is one of the constants above."""

    line: int
    name: str
    status: str
    detail: str = ""
    link: str = ""
    warning: str = ""
    user_id: int | None = None
    late_pass: bool = False


# Django's own username rule (UnicodeUsernameValidator), and its length limit.
USERNAME_PATTERN = re.compile(r"^[\w.@+-]+\Z")
MAX_USERNAME = 150


def parse_lines(text):
    """Split the paste into (entries, problems). A line is `Prénom Nom, email` with an
    optional third column, `identifiant`, that sets the username instead of deriving it
    (two people sharing a name); blank lines are ignored; the email is lower-cased and must
    be a real one."""
    entries, problems = [], []
    for number, raw in enumerate(text.splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        parts = [part.strip() for part in raw.split(",")]
        if not 2 <= len(parts) <= 3:
            problems.append(Problem(number, raw, "format : Prénom Nom, email[, identifiant]"))
            continue
        name, email = parts[0], parts[1].lower()
        try:
            first_name, last_name, username = parse_name(name)
        except ValueError:
            problems.append(Problem(number, raw, "nom manquant"))
            continue
        if len(parts) == 3:
            username = parts[2].lower()
            if not USERNAME_PATTERN.match(username) or len(username) > MAX_USERNAME:
                problems.append(Problem(number, raw, "identifiant invalide"))
                continue
        try:
            validate_email(email)
        except ValidationError:
            problems.append(Problem(number, raw, "email invalide"))
            continue
        if not usable_email(email):
            problems.append(Problem(number, raw, "adresse générique, pas un vrai email"))
            continue
        entries.append(Invite(number, first_name, last_name, email, username))
    return entries, problems


def _match(entry):
    """(user, how) for the account this line is, (None, None) when it is a newcomer, or
    (None, reason) for a conflict."""
    by_email = list(User.objects.filter(email__iexact=entry.email))
    if len(by_email) > 1:
        return None, "plusieurs comptes ont cette adresse"
    if by_email:
        return by_email[0], "email"
    existing = User.objects.filter(username=entry.username).first()
    if existing is None:
        return None, None
    current = existing.email.strip().lower()
    if not usable_email(current) or current == entry.email:
        return existing, "identifiant"
    return None, (
        f"l'identifiant « {entry.username} » appartient à un compte avec une autre adresse : "
        f"ajoutez un identifiant en 3e colonne, par exemple {entry.username}2"
    )


def invite(entries, problems, grant_late_pass=False, granted_by=None):
    """
    Process a parsed paste and return one InviteResult per line, in line order.

    :raises ImproperlyConfigured: without a usable PUBLIC_URL, before anything is created.
    :raises LookupError: a late pass was asked for but there is no edition, likewise.
    """
    public_url()
    edition = None
    if grant_late_pass:
        edition = latest_edition()
        if edition is None:
            raise LookupError("no edition")
    results = {p.line: InviteResult(p.line, p.text, MALFORMED, p.reason) for p in problems}
    seen = set()
    for entry in entries:
        name = f"{entry.first_name} {entry.last_name}".strip()
        keys = {entry.email, entry.username}
        if seen & keys:
            results[entry.line] = InviteResult(
                entry.line, name, DUPLICATE, "déjà présent plus haut dans la liste"
            )
            continue
        seen |= keys
        results[entry.line] = _one(entry, name, edition, granted_by)
    return [results[line] for line in sorted(results)]


def _one(entry, name, edition, granted_by):
    with transaction.atomic():
        user, how = _match(entry)
        if user is None and how is not None:
            return InviteResult(entry.line, name, CONFLICT, how)
        if user is not None:
            if not user.is_active:
                return InviteResult(entry.line, name, CONFLICT, "compte désactivé")
            status = REUSED
            if not usable_email(user.email):
                user.email = entry.email
                user.save(update_fields=["email"])
        else:
            user = User.objects.create_user(
                username=entry.username,
                first_name=entry.first_name,
                last_name=entry.last_name,
                email=entry.email,
                password=get_random_string(length=12),
            )
            status = CREATED
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if status == CREATED or not user.player_set.exists():
            if not profile.invited:
                profile.invited = True
                profile.save(update_fields=["invited", "updated_at"])
        if edition is not None:
            LateRegistration.objects.get_or_create(
                user=user, edition=edition, defaults={"granted_by": granted_by}
            )
        if user.is_staff or user.is_superuser:
            # An organiser keeps their own password: flagged so they may register, never a
            # claim link (a link must not hand over an account with admin rights).
            return InviteResult(
                entry.line, name, STAFF, "organisateur : se connecter puis ouvrir /register",
                user_id=user.pk, late_pass=edition is not None,
            )
        try:
            link = claim_link(user)
        except Unclaimable as error:
            return InviteResult(entry.line, name, CONFLICT, f"pas de lien ({error.reason})")
        warning = ""
        if profile.claimed_at is not None:
            warning = "compte déjà activé : ce lien réinitialise le mot de passe qu'il a choisi"
        return InviteResult(
            entry.line, name, status, link=link, warning=warning, user_id=user.pk,
            late_pass=edition is not None,
        )
