from copy import deepcopy
from datetime import datetime

from django.db import models
from django.core.validators import FileExtensionValidator, MinValueValidator

from .Team import Team, TeamResult
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
    reveal_score = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name + " - " + str(self.edition.year)

    def get_ranking(self, team_id: int) -> int:
        """
        Get the ranking of a team in the discipline.

        @param team_id: id of the team to search for

        @return: ranking of the team in the discipline
        """
        pass

    def _get_last_round_as_referee(self, team_id: int) -> int:
        """
        Get the last round order in which a team was a referee.

        @param team_id: id of the team to search for

        @return: order of the last round in which the team was a referee, -1 if never
        """
        last_game_refereed = (
            Game.objects.filter(referees__id=team_id, is_active=True)
            .order_by("-round__order")
            .first()
        )
        if not last_game_refereed:
            return -1
        else:
            return last_game_refereed.round.order

    def _assign_referees(
        self, game_without_referees: list[Game], leftover_team_ids: set[int]
    ) -> None:
        """
        Assign referees to games without referees while ensuring best possible distribution.

        @param game_without_referees: list of games without referees for this round iteration
        @param leftover_team_ids: set of team ids that can be referees for this round iteration
        """
        for game in game_without_referees:
            best_referee_id: int = None
            best_referee_score: int = None
            last_round_best_referee: int = None
            for team_id in leftover_team_ids:
                referee_score = Game.objects.filter(
                    referees__id=team_id, discipline=self, is_active=True
                ).count()

                # Assign the first team as the best referee, or the one with the refereed games
                if not best_referee_id or referee_score < best_referee_score:
                    best_referee_id = team_id
                    best_referee_score = referee_score

                # If the team has refereed the same number of games,
                # pick the one that didn't referee for longer
                elif referee_score == best_referee_score:
                    if not last_round_best_referee:
                        last_round_best_referee = self._get_last_round_as_referee(best_referee_id)

                    if self._get_last_round_as_referee(team_id) < last_round_best_referee:
                        best_referee_id = team_id
                        best_referee_score = referee_score

            game.referees = Team.objects.get(id=best_referee_id)
            game.save()
            leftover_team_ids.remove(best_referee_id)

    def _create_round_iterations(
        self,
        l1: list[Team],
        l2: list[Team],
        leftover_team_ids: set[int],
        game_round: TeamSportRound,
        game_index: int,
        iteration_index: int,
        simultaneous_games: int,
    ) -> int:
        """
        Create round iterations for team sports.

        @param l1: list of teams in the first half of the round
        @param l2: list of teams in the second half of the round
        @param leftover_team_ids: set of team ids that can be referees for this round iteration
        @param game_round: round of the game
        @param game_index: index of the game in the round
        @param iteration_index: index of the iteration in the round
        @param simultaneous_games: number of simultaneous games in the round

        @return: game index
        """
        games_without_referees = []

        # Create games for this iteration, hence the number of simultaneous games for a round
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

        self._assign_referees(games_without_referees, leftover_team_ids)

        return game_index

    def schedule_games(self) -> None:
        """
        Schedule round-robin games for the discipline, including teams refereeing.
        Applicable to team sports.
        """
        teams = Team.objects.filter(edition=self.edition, is_active=True)
        simultaneous_games = len(teams) // 3
        iteration_per_round = (len(teams) // 2) // simultaneous_games
        max_rounds = len(teams) - 1
        team_ids = {team.id for team in teams}

        # Split teams in two halves for round-robin
        l1 = teams[: len(teams) // 2]
        l2 = teams[len(teams) // 2 :]
        l2.reverse()

        for round_index in range(max_rounds):
            game_round = TeamSportRound.objects.create(discipline=self, order=round_index)
            game_index = 0
            for iteration_index in range(iteration_per_round):

                game_index = self._create_round_iterations(
                    l1,
                    l2,
                    deepcopy(team_ids),
                    game_round,
                    game_index,
                    iteration_index,
                    simultaneous_games,
                )

            # Rotate teams for next round
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
