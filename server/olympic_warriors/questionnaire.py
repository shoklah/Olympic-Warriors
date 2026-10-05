"""
The per-edition registration questionnaire: its skills are data (RegistrationSkill), so
organisers copy them from the previous edition, the skill set freezes once players have
answered, and stored ratings are recomputed on demand after a weight change.
"""
from dataclasses import dataclass

from django.db import transaction

from .models import Edition, Player, PlayerRating, RegistrationSkill
from .registration import rate


class QuestionnaireError(ValueError):
    """An organiser action that cannot apply; the message is French, for the admin."""


def skills_locked(edition):
    """True once any player of the edition has a rating: adding, deleting or renaming the
    identifier of a skill would leave existing answers incomplete or orphaned."""
    return PlayerRating.objects.filter(player__edition=edition).exists()


@transaction.atomic
def copy_skills(edition):
    """
    Copy the active skills of the closest earlier edition that has any into an edition
    that has none.

    :return: (source year, number of skills copied).
    :raises QuestionnaireError: the edition already has skills, or no earlier edition does.
    """
    if edition.registrationskill_set.exists():
        raise QuestionnaireError("cette édition a déjà un questionnaire.")
    previous = (
        Edition.objects.filter(
            year__lt=edition.year, is_active=True, registrationskill__is_active=True
        )
        .order_by("-year")
        .distinct()
        .first()
    )
    if previous is None:
        raise QuestionnaireError("aucune édition précédente n'a de questionnaire.")
    skills = list(previous.registrationskill_set.filter(is_active=True))
    RegistrationSkill.objects.bulk_create(
        RegistrationSkill(
            edition=edition,
            name_fr=skill.name_fr,
            name_en=skill.name_en,
            identifier=skill.identifier,
            weight=skill.weight,
            order=skill.order,
        )
        for skill in skills
    )
    return previous.year, len(skills)


@dataclass(frozen=True)
class RecomputeReport:
    """What recompute_ratings did, for the admin message."""

    updated: int
    unchanged: int
    no_global_level: int  # skipped: the raw global answer was never stored (older editions)
    incomplete: int  # skipped: no stored rating for one of the active skills
    has_questionnaire: bool  # False: the edition has no active skill, nothing was touched


def recompute_ratings(edition):
    """
    Recompute Player.rating of the edition's active players from their stored raw skill
    ratings and global level, with the current active skills and weights. Idempotent. A
    player without a stored global level (every edition imported before the in-app
    registration) or without a rating for each active skill is skipped and counted.
    """
    weights = {
        skill.identifier: skill.weight
        for skill in edition.registrationskill_set.filter(is_active=True)
    }
    if not weights:
        return RecomputeReport(0, 0, 0, 0, False)
    players = Player.objects.filter(edition=edition, is_active=True).prefetch_related(
        "playerrating_set"
    )
    changed, unchanged, no_global_level, incomplete = [], 0, 0, 0
    for player in players:
        if player.global_level is None:
            no_global_level += 1
            continue
        ratings = {r.identifier: r.rating for r in player.playerrating_set.all() if r.is_active}
        if not set(weights) <= set(ratings):
            incomplete += 1
            continue
        _, global_rating = rate(ratings, weights, player.global_level)
        rating = round(global_rating)
        if rating == player.rating:
            unchanged += 1
        else:
            player.rating = rating
            changed.append(player)
    Player.objects.bulk_update(changed, ["rating"])
    return RecomputeReport(len(changed), unchanged, no_global_level, incomplete, True)
