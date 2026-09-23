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
    score1 = models.IntegerField(
        default=0, verbose_name="score 1", validators=[MinValueValidator(0)]
    )
    team2 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team2")
    score2 = models.IntegerField(
        default=0, verbose_name="score 2", validators=[MinValueValidator(0)]
    )
    referees = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="referees")
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    is_played = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.discipline.name + ": " + self.team1.name + " vs " + self.team2.name

    def league_points(self, team_id):
        """
        League points of a team in this game's discipline: 3 per win, 1 per draw, over the
        discipline's active, played games. Unplayed games count for nothing.
        """
        games = Game.objects.filter(discipline=self.discipline, is_active=True, is_played=True)
        points = 0
        for game in games.filter(team1_id=team_id):
            points += 3 if game.score1 > game.score2 else (1 if game.score1 == game.score2 else 0)
        for game in games.filter(team2_id=team_id):
            points += 3 if game.score2 > game.score1 else (1 if game.score1 == game.score2 else 0)
        return points

    def save(self, *args, **kwargs):
        """
        Save, then recompute the league points of every team the game touches (its current
        teams, and its previous ones when a team was changed) from the played games.
        """
        team_ids = {self.team1_id, self.team2_id}
        if self.pk:
            previous = Game.objects.filter(pk=self.pk).values_list("team1_id", "team2_id").first()
            if previous:
                team_ids.update(previous)

        super().save(*args, **kwargs)

        for team_id in team_ids:
            TeamResult.objects.filter(team_id=team_id, discipline=self.discipline).update(
                points=self.league_points(team_id)
            )


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
        Override save method to register the teams of the edition and schedule games matching
        the pairing system. Games are scheduled when the discipline is created with a pairing
        system, or when a pairing system is set later on a discipline that has no round yet.
        """
        previous_pairing_system = None
        if self.pk is not None:
            previous_pairing_system = (
                Discipline.objects.filter(pk=self.pk)
                .values_list("pairing_system", flat=True)
                .first()
            )
        is_new = previous_pairing_system is None

        super().save(*args, **kwargs)

        if is_new:
            self.register_teams()

        if (
            self.pairing_system != self.PairingSystem.NONE
            and self.pairing_system != previous_pairing_system
            and not self.rounds.filter(is_active=True).exists()
        ):
            if not is_new:
                # Teams may have joined the edition since the discipline was created
                self.register_teams()
            if self.result_type == ResultTypes.POINTS:
                # A bye team gets no game, so Game.save() would never zero its points, and
                # the Swiss pairing (ordered by points, nulls last in Postgres) would treat
                # a still-null result as the strongest team.
                TeamResult.objects.filter(discipline=self, points__isnull=True).update(points=0)
            self.schedule_games()

    def register_teams(self) -> None:
        """
        Create a result entry for every active team of the edition that does not have one yet.
        """
        teams = Team.objects.filter(edition=self.edition, is_active=True)
        for team in teams:
            TeamResult.objects.get_or_create(
                team=team,
                discipline=self,
                defaults={
                    # A discipline with games computes its points from them (0 before any is
                    # played); one without keeps None until an organiser enters a value, and a
                    # time is None until entered, so "no result yet" is a null, never a zero.
                    "points": (
                        0
                        if self.result_type == ResultTypes.POINTS
                        and self.pairing_system != self.PairingSystem.NONE
                        else None
                    ),
                    "time": None,
                }
            )

    def schedule_games(self) -> None:
        """
        Schedule the games of the discipline according to its pairing system.
        """
        match self.pairing_system:
            case self.PairingSystem.ROUND_ROBIN:
                schedule_round_robin_games(self.id)
            case self.PairingSystem.SWISS:
                schedule_swiss_games(self.id)
            case self.PairingSystem.NONE:
                pass

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
