from functools import cached_property

from django.apps import apps
from django.db import models
from django.db.models import F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from .Edition import Edition
from .ResultTypes import ResultTypes


def annotate_points_difference(queryset):
    """
    Annotate a TeamResult queryset with `points_difference`: over the active, played games
    of the result's discipline, the sum of the team's score minus its opponent's score.
    Teams without any played game get 0.

    Game is fetched from the app registry because Discipline.py imports this module.
    """
    Game = apps.get_model("olympic_warriors", "Game")

    def score_gap(team_field, own_score, other_score):
        games = Game.objects.filter(
            discipline_id=OuterRef("discipline_id"),
            is_active=True,
            is_played=True,
            **{team_field: OuterRef("team_id")},
        )
        total = (
            games.order_by()
            .values(team_field)
            .annotate(gap=Sum(F(own_score) - F(other_score)))
            .values("gap")[:1]
        )
        return Coalesce(Subquery(total, output_field=models.IntegerField()), 0)

    return queryset.annotate(
        points_difference=score_gap("team1", "score1", "score2")
        + score_gap("team2", "score2", "score1")
    )


class TeamResult(models.Model):
    """
    Team's score for an Discipline.
    """

    team = models.ForeignKey("Team", on_delete=models.CASCADE, related_name='registered_team')
    discipline = models.ForeignKey(
        "Discipline", on_delete=models.CASCADE, related_name='registered_to'
    )
    points = models.IntegerField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return (
            self.team.name + " - " + self.discipline.name + ' ' + str(self.discipline.edition.year)
        )

    @property
    def result_type(self) -> str:
        """
        Get the result type of the team in the discipline.
        """
        return self.discipline.result_type

    @cached_property
    def points_difference(self) -> int:
        """
        Sum of the team's score minus its opponent's score over the active games of the
        discipline. 0 when the team has no game.
        """
        if self.pk is None:
            return 0

        return (
            annotate_points_difference(TeamResult.objects.filter(pk=self.pk))
            .values_list("points_difference", flat=True)
            .first()
        )

    @property
    def ranking(self) -> int:
        """
        Get the ranking of the team in the discipline. Points disciplines break ties on
        points difference; teams still tied share a rank.

        @return: ranking of the team in the discipline
        """
        if self.discipline.reveal_score is False:
            return 0

        if self.discipline.result_type == ResultTypes.TIME:
            if self.time is None:
                return 0
            return (
                TeamResult.objects.filter(
                    discipline=self.discipline, time__lt=self.time, is_active=True
                ).count()
                + 1
            )
        elif self.discipline.result_type == ResultTypes.POINTS:
            if self.points is None:
                return 0
            results = annotate_points_difference(
                TeamResult.objects.filter(discipline=self.discipline, is_active=True)
            )
            ahead = results.filter(
                Q(points__gt=self.points)
                | Q(points=self.points, points_difference__gt=self.points_difference)
            )
            return ahead.count() + 1
        else:
            return 0

    @property
    def global_points(self) -> int:
        """
        Get points of the team from ranking to process global ranking.

        @return: points of the team from ranking
        """
        ranking = self.ranking
        if ranking == 0:
            # Hidden scores or a discipline without a result type: nothing to reward.
            return 0

        registered_teams_count = TeamResult.objects.filter(
            discipline=self.discipline, is_active=True
        ).count()
        points = registered_teams_count - ranking + 1
        if ranking == 1:
            points += 2
        elif ranking <= 3:
            points += 1

        return points


class Team(models.Model):
    """
    A team is a group of players that participate in an edition of the Olympic Warriors.
    """

    name = models.CharField(max_length=100)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        """
        String representation of the object
        """
        return str(self.name)

    @property
    def total_points(self) -> int:
        """
        Get the total global points of the team
        """
        points = 0
        team_results = TeamResult.objects.filter(
            team=self, discipline__edition=self.edition, is_active=True
        )

        for team_result in team_results:
            points += team_result.global_points

        return points

    @property
    def ranking(self) -> int:
        """
        Get the ranking of the team in the edition.

        @return: ranking of the team in the edition
        """
        ranking = 1
        teams = Team.objects.filter(edition=self.edition, is_active=True)
        for team in teams:
            if team.total_points > self.total_points:
                ranking += 1

        return ranking
