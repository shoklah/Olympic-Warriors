from django.db import models
from .Edition import Edition
from .ResultTypes import ResultTypes


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

    @property
    def ranking(self) -> int:
        """
        Get the ranking of the team in the discipline.

        @return: ranking of the team in the discipline
        """
        if self.discipline.reveal_score is False:
            return 0

        if self.discipline.result_type == ResultTypes.TIME:
            return (
                TeamResult.objects.filter(
                    discipline=self.discipline, time__lt=self.time, is_active=True
                ).count()
                + 1
            )
        elif self.discipline.result_type == ResultTypes.POINTS:
            return (
                TeamResult.objects.filter(
                    discipline=self.discipline, points__gt=self.points, is_active=True
                ).count()
                + 1
            )
        else:
            return 0

    @property
    def global_points(self) -> int:
        """
        Get points of the team from ranking to process global ranking.

        @return: points of the team from ranking
        """
        if self.discipline.reveal_score is False:
            return 0

        registered_teams_count = TeamResult.objects.filter(
            discipline=self.discipline, is_active=True
        ).count()
        points = registered_teams_count - self.ranking + 1
        if self.ranking == 1:
            points += 2
        elif self.ranking <= 3:
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
