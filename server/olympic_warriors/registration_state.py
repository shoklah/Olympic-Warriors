"""
Whether registration is open for an edition, and for a given user (spec 2026-10-04).

Open only when the edition has an active questionnaire AND either the caller holds a late
pass (valid through the edition's end_date, Paris), or today is within the window:
registration_opens set and reached, registration_closes not passed (inclusive; the day
before start_date when blank). A freshly created edition has no opening date, so it stays
closed until an organiser sets one. The reason names why it is closed, or `late_pass` when
a pass is what opens it.
"""
from dataclasses import dataclass
from datetime import timedelta

from .models import LateRegistration
from .profiles import paris_today

NOT_CONFIGURED = "not_configured"
NOT_YET_OPEN = "not_yet_open"
CLOSED = "closed"
LATE_PASS = "late_pass"


@dataclass(frozen=True)
class RegistrationState:
    """`is_open`, and `reason`: "" when the window is what opens it, LATE_PASS when a pass
    does, else why it is closed (NOT_CONFIGURED, NOT_YET_OPEN or CLOSED)."""

    is_open: bool
    reason: str = ""


def closing_date(edition):
    """The last day of the window: registration_closes, else the day before the start."""
    return edition.registration_closes or edition.start_date - timedelta(days=1)


def registration_state(edition, user=None, today=None):
    """The state for `edition`, for `user` (None: nobody in particular, so no pass)."""
    today = today or paris_today()
    if not edition.registrationskill_set.filter(is_active=True).exists():
        return RegistrationState(False, NOT_CONFIGURED)
    if (
        user is not None
        and today <= edition.end_date
        and LateRegistration.objects.filter(user=user, edition=edition).exists()
    ):
        return RegistrationState(True, LATE_PASS)
    if edition.registration_opens is None:
        return RegistrationState(False, NOT_CONFIGURED)
    if today < edition.registration_opens:
        return RegistrationState(False, NOT_YET_OPEN)
    if today > closing_date(edition):
        return RegistrationState(False, CLOSED)
    return RegistrationState(True)
