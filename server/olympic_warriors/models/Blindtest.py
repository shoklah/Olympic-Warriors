from django.db import models

from .Discipline import Discipline
from .Team import Team


class Blindtest(Discipline):
    """
    Blindtest is a discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to Blindtest
        """
        self.name = 'Blindtest'
        super().save(*args, **kwargs)


class BlindtestGuess(models.Model):
    """
    A team guessing a song name and artist
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='team')
    answer = models.CharField(max_length=100)
    is_valid = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
