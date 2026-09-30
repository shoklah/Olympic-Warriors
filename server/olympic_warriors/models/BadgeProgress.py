from django.contrib.auth.models import User
from django.db import models
from django.db.models import UniqueConstraint

from .Badge import Badge


class BadgeProgress(models.Model):
    """
    How far a person is toward a badge whose rule is a count, one row per (user, code):
    computed by badges.compute() in the same pass as the badges and stored by
    badges.refresh() (see the badge progress design spec under docs/superpowers/specs/).
    The target is not stored: it follows from the code and the count. Not in the admin: it
    is recomputed at every refresh, and organisers act on the badges, not on the bars.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="badge_progress")
    code = models.CharField(max_length=32, choices=Badge.Codes.choices)
    value = models.PositiveIntegerField(null=True)  # null when out of reach
    best = models.PositiveIntegerField(null=True)  # streaks only: the best run
    reachable = models.BooleanField(default=True)
    discipline = models.CharField(max_length=100, blank=True, default="")
    partner = models.ForeignKey(User, null=True, on_delete=models.CASCADE, related_name="+")
    year = models.PositiveIntegerField(null=True)  # clean-sweep's edition

    class Meta:
        constraints = [UniqueConstraint(fields=("user", "code"), name="progress_unique")]
