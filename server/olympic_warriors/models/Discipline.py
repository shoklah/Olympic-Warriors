from django.db import models
from datetime import datetime

from django.core.validators import FileExtensionValidator, MinValueValidator

from .Team import Team
from .Edition import Edition
from .Player import Player


class Discipline(models.Model):
    """
    A Discipline is a competition that takes place in an edition of the Olympic Warriors.
    """

    name = models.CharField(max_length=100)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    teams = models.ManyToManyField(Team, through='TeamResult')
    rules = models.FileField(
        upload_to="manuals/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
        verbose_name="rules",
    )

    def __str__(self) -> str:
        return self.name + " - " + str(self.edition.year)


class Game(models.Model):
    """
    A game is a competition between two teams that takes place
    in an edition of the Olympic Warriors.
    """

    discipline = models.ForeignKey(Discipline, on_delete=models.CASCADE, related_name="discipline")
    team1 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team1")
    score1 = models.IntegerField(MinValueValidator(0), default=0)
    team2 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team2")
    score2 = models.IntegerField(MinValueValidator(0), default=0)
    referees = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="referees")
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    date = models.DateField()
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.discipline.name + ": " + self.team1.name + " vs " + self.team2.name


class GameEvent(models.Model):
    """
    A game event is something happening in a game that we need to log to process score and stats.
    """

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="game")
    player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="player1")
    player2 = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="player2", null=True, blank=True
    )
    time = models.DateTimeField(default=datetime.now, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return (
            self.game.discipline.name + ": " + self.player1.user.first_name + " - " + str(self.time)
        )


class TeamResult(models.Model):
    """
    Team's score for an Discipline.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='registered_team')
    discipline = models.ForeignKey(
        Discipline, on_delete=models.CASCADE, related_name='registered_to'
    )
    score = models.IntegerField()
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.team.name + " - " + self.discipline
