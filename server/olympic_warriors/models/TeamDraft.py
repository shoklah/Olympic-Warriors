from django.contrib.auth.models import User
from django.db import models

from .Edition import Edition


class TeamDraft(models.Model):
    """
    The organisers' working state of the team builder for an edition: confirmed name links,
    the proposed teams and the locked players, as the browser keeps them. The server only
    checks its shape (olympic_warriors.builder); nothing here touches Team or Player.team
    until the draft is applied. Private, never exported.
    """

    edition = models.OneToOneField(Edition, on_delete=models.CASCADE, related_name="team_draft")
    document = models.JSONField(default=dict)
    updated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Team draft {self.edition.year}"
