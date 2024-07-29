from django.db import models
from .Player import Player
from .Edition import Edition


class Team(models.Model):
    """
    A team is a group of players that participate in an edition of the Olympic Warriors.
    """

    captain = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="captain")
    name = models.CharField(max_length=100)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)