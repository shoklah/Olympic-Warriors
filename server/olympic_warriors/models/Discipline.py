from datetime import datetime

from django.db import models
from django.core.validators import FileExtensionValidator, MinValueValidator

from olympic_warriors.schedule import schedule_round_robin_games, schedule_swiss_games
from .Team import Team, TeamResult
from .Edition import Edition
from .Player import Player
from .ResultTypes import ResultTypes


class TeamSportRound(models.Model):
    """
    A team sport round is a round of a team sport discipline, used to schedule games.
    """

    discipline = models.ForeignKey(
        "Discipline", on_delete=models.CASCADE, related_name="rounds")
    order = models.IntegerField()
    is_over = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.discipline.name + " - Round " + str(self.order)

    def save(self, *args, **kwargs):
        """
        Override save method.
        """
        if self.pk is not None:
            old_round = TeamSportRound.objects.get(pk=self.pk)
            if self.discipline.pairing_system == "SW" and self.is_over and not old_round.is_over:
                schedule_swiss_games(self.discipline.id)
        super().save(*args, **kwargs)


class Game(models.Model):
    """
    A game is a competition between two teams that takes place
    in an edition of the Olympic Warriors.
    """

    discipline = models.ForeignKey(
        "Discipline", on_delete=models.CASCADE, related_name="discipline"
    )
    round = models.ForeignKey(TeamSportRound, on_delete=models.CASCADE, related_name="round")
    team1 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team1")
    score1 = models.IntegerField(MinValueValidator(0), default=0)
    team2 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team2")
    score2 = models.IntegerField(MinValueValidator(0), default=0)
    referees = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="referees")
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.discipline.name + ": " + self.team1.name + " vs " + self.team2.name

    def _update_points(self, team1_points=None, team2_points=None):
        """
        Update team results with the points of the game.
        """
        team1_result = TeamResult.objects.get(team=self.team1, discipline=self.discipline)
        team2_result = TeamResult.objects.get(team=self.team2, discipline=self.discipline)
        team1_result.points += team1_points
        team2_result.points += team2_points
        team1_result.save()
        team2_result.save()

    def save(self, *args, **kwargs):
        """
        Override save method to update team result if score is updated.
        """
        if self.pk:
            old_game = Game.objects.get(pk=self.pk)
            score_changed = self.score1 != old_game.score1 or self.score2 != old_game.score2

            if score_changed:
                if self.score1 > self.score2:
                    if old_game.score1 == old_game.score2:
                        self._update_points(team1_points=+2, team2_points=-1)
                    elif old_game.score1 < old_game.score2:
                        self._update_points(team1_points=+3, team2_points=-3)
                elif self.score1 < self.score2:
                    if old_game.score1 == old_game.score2:
                        self._update_points(team2_points=+2, team1_points=-1)
                    elif old_game.score1 > old_game.score2:
                        self._update_points(team2_points=+3, team1_points=-3)
                else:  # self.score1 == self.score2
                    if old_game.score1 > old_game.score2:
                        self._update_points(team1_points=-2, team2_points=+1)
                    elif old_game.score1 < old_game.score2:
                        self._update_points(team2_points=-2, team1_points=+1)

        else:
            if self.score1 > self.score2:
                self._update_points(team1_points=+3, team2_points=0)
            elif self.score1 < self.score2:
                self._update_points(team2_points=+3, team1_points=0)
            else:  # self.score1 == self.score2
                self._update_points(team1_points=+1, team2_points=+1)

        super().save(*args, **kwargs)


class Discipline(models.Model):
    """
    A Discipline is a competition that takes place in an edition of the Olympic Warriors.
    """

    class PairingSystem(models.TextChoices):
        ROUND_ROBIN = "RR", "Round Robin"
        SWISS = "SW", "Swiss"
        NONE = "NO", "None"

    name = models.CharField(max_length=100, blank=True)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    teams = models.ManyToManyField(Team, through='TeamResult')
    rules = models.FileField(
        upload_to="rules/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
        verbose_name="rules",
    )
    result_type = models.CharField(
        max_length=3,
        choices=ResultTypes.choices,
        blank=True,
        verbose_name="result type",
    )
    reveal_score = models.BooleanField(default=False)

    max_rounds = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
        verbose_name="max rounds"
    )
    pairing_system = models.CharField(
        max_length=2,
        choices=PairingSystem.choices,
        default=PairingSystem.NONE,
        verbose_name="pairing system",
    )

    def __str__(self) -> str:
        return self.name + " - " + str(self.edition.year)

    def save(self, *args, **kwargs):
        """
        Override save method to schedule games matching the pairing system.
        """
        if self.pk is None:
            super().save(*args, **kwargs)
            teams = Team.objects.filter(edition=self.edition, is_active=True)
            for team in teams:
                TeamResult.objects.get_or_create(
                    team=team,
                    discipline=self,
                    defaults={
                        "points": 0 if self.result_type == ResultTypes.POINTS else None,
                        "time": "00:00:00" if self.result_type == ResultTypes.TIME else None,
                    }
                )

            match self.pairing_system:
                case self.PairingSystem.ROUND_ROBIN:
                    schedule_round_robin_games(self.id)
                case self.PairingSystem.SWISS:
                    schedule_swiss_games(self.id)
                case self.PairingSystem.NONE:
                    pass
        else:
            super().save(*args, **kwargs)

    def get_ranking(self, team_id: int) -> int:
        """
        Get the ranking of a team in the discipline.

        @param team_id: id of the team to search for

        @return: ranking of the team in the discipline
        """
        pass

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
