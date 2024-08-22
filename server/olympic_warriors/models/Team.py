from django.db import models
from .Edition import Edition


class TeamResult(models.Model):
    """
    Team's score for an Discipline.
    """

    class TeamResultTypes(models.TextChoices):
        """
        Enum for Team Result Types
        """

        POINTS = 'PTS', 'Points'
        TIME = 'TIM', 'Time'

    team = models.ForeignKey("Team", on_delete=models.CASCADE, related_name='registered_team')
    discipline = models.ForeignKey(
        "Discipline", on_delete=models.CASCADE, related_name='registered_to'
    )
    points = models.IntegerField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    result_type = models.CharField(max_length=3, choices=TeamResultTypes.choices)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return (
            self.team.name + " - " + self.discipline.name + ' ' + str(self.discipline.edition.year)
        )

    @property
    def ranking(self) -> int:
        """
        Get the ranking of the team in the discipline.

        @return: ranking of the team in the discipline
        """
        if self.result_type == TeamResult.TeamResultTypes.TIME:
            return (
                TeamResult.objects.filter(discipline=self.discipline, time__lt=self.time).count()
                + 1
            )
        elif self.result_type == TeamResult.TeamResultTypes.POINTS:
            return (
                TeamResult.objects.filter(
                    discipline=self.discipline, points__gt=self.points
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
        registered_teams_count = TeamResult.objects.filter(
            discipline=self.discipline, is_active=True
        ).count()
        points = registered_teams_count - self.ranking
        if self.ranking == 1:
            points += 3
        elif self.ranking <= 3:
            points += 2

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
        return self.name

    @property
    def total_points(self) -> int:
        """
        Get the total global points of the team
        """
        points = 0
        team_results = TeamResult.objects.filter(team=self, discipline__edition=self.edition)

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
