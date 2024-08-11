from copy import deepcopy
from django.db import models
from datetime import datetime

from django.core.validators import FileExtensionValidator, MinValueValidator

from .Team import Team
from .Edition import Edition
from .Player import Player


class TeamSportRound(models.Model):
    """
    A team sport round is a round of a team sport discipline, used to schedule games.
    """

    discipline = models.ForeignKey("Discipline", on_delete=models.CASCADE)
    order = models.IntegerField()
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.discipline.name + " - Round " + str(self.order)


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


class Discipline(models.Model):
    """
    A Discipline is a competition that takes place in an edition of the Olympic Warriors.
    """

    name = models.CharField(max_length=100)
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

    def __str__(self) -> str:
        return self.name + " - " + str(self.edition.year)

    def schedule_games(self):
        """
        Schedule round-robin games for the discipline, including teams refereeing.
        Applicable to team sports.
        """
        teams = Team.objects.filter(edition=self.edition, is_active=True)
        simultaneous_games = len(teams) // 3
        iteration_per_round = (len(teams) // 2) // simultaneous_games
        max_rounds = len(teams) - 1
        team_ids = {team.id for team in teams}

        l1 = teams[: len(teams) // 2]
        l2 = teams[len(teams) // 2 :]
        l2.reverse()

        for round_index in range(max_rounds):
            game_round = TeamSportRound.objects.create(discipline=self, order=round_index)
            game_index = 0
            for iteration_index in range(iteration_per_round):
                games_without_referees = []
                leftover_team_ids = deepcopy(team_ids)

                while game_index < simultaneous_games * (iteration_index + 1):
                    games_without_referees.append(
                        Game.objects.create(
                            discipline=self,
                            round=game_round,
                            team1=l1[game_index],
                            team2=l2[game_index],
                            referees=l1[game_index],
                            edition=self.edition,
                        )
                    )
                    leftover_team_ids.remove(l1[game_index].id)
                    leftover_team_ids.remove(l2[game_index].id)
                    game_index += 1

                for game in games_without_referees:
                    game.referees = Team.objects.get(id=leftover_team_ids.pop())
                    game.save()

            l2.append(l1.pop())
            l1.insert(1, l2.pop(0))


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
