"""
Models for Blindtest discipline
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from .Discipline import Discipline
from .Team import Team, TeamResult


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
        teams = Team.objects.filter(edition=self.edition, is_active=True)
        for team in teams:
            TeamResult.objects.create(
                team=team, discipline=self, result_type=TeamResult.TeamResultTypes.POINTS, points=0
            )


class BlindtestRound(models.Model):
    """
    A round of a blindtest
    """

    blindtest = models.ForeignKey(Blindtest, on_delete=models.CASCADE, related_name='blindtest')
    order = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    is_active = models.BooleanField(default=True)

    def __str__(self):
        """
        String representation of the object
        """
        return f'{self.blindtest}: {str(self.order)}'


class BlindtestGuess(models.Model):
    """
    A team guessing a song name and artist
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='team')
    blindtest_round = models.ForeignKey(
        BlindtestRound, on_delete=models.CASCADE, related_name='blindtest_round'
    )
    artist = models.CharField(max_length=255)
    song = models.CharField(max_length=255)
    is_artist_correct = models.BooleanField(default=False)
    is_song_correct = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        """
        String representation of the object
        """
        return f'{self.team}: {self.artist} - {self.song}'

    def _update_points(self, points):
        """
        Update team result points
        """
        team_result = TeamResult.objects.get(team=self.team, discipline=self.blindtest)
        team_result.points += points
        team_result.save()

    def save(self, *args, **kwargs):
        """
        Override save method to update team result points if needed
        """
        if self.pk:
            old_guess = BlindtestGuess.objects.get(pk=self.pk)
            if old_guess.is_artist_correct and not self.is_artist_correct:
                self._update_points(-1)
            elif not old_guess.is_artist_correct and self.is_artist_correct:
                self._update_points(1)

            if old_guess.is_song_correct and not self.is_song_correct:
                self._update_points(-1)
            elif not old_guess.is_song_correct and self.is_song_correct:
                self._update_points(1)
        else:
            if self.is_artist_correct:
                self._update_points(1)

            if self.is_song_correct:
                self._update_points(1)

        super().save(*args, **kwargs)
