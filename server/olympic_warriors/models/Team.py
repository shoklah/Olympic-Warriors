from django.db import models

from .Edition import Edition


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

    def _standing(self):
        """
        This result's row of the edition standings (see olympic_warriors.standings).
        Each access recomputes the edition: callers that need many rows should call
        compute_standings once and read from it.
        """
        from ..standings import ResultStanding, compute_standings

        if self.pk is None:
            return ResultStanding()
        return compute_standings(self.discipline.edition).result(self.pk)

    @property
    def points_difference(self) -> int:
        """
        Sum of the team's score minus its opponent's score over the active, played games
        of the discipline. 0 when the team has no game.
        """
        return self._standing().points_difference

    @property
    def ranking(self) -> int:
        """
        Ranking of the team in the discipline, 0 while the score is hidden or missing.
        Points disciplines break ties on points difference; teams still tied share a rank.
        """
        return self._standing().ranking

    @property
    def global_points(self) -> int:
        """
        Points the team earns towards the edition ranking from its rank in the discipline.
        """
        return self._standing().global_points


class Team(models.Model):
    """
    A team is a group of players that participate in an edition of the Olympic Warriors.
    """

    name = models.CharField(max_length=100)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    # Finishing order recorded by hand for an edition without result data. As soon as
    # one active team of an edition has one, the edition ranking is this order and the
    # totals are null (see olympic_warriors.standings).
    final_rank = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        """
        String representation of the object
        """
        return str(self.name)

    def _standing(self):
        """
        This team's row of the edition standings (see olympic_warriors.standings).
        """
        from ..standings import TeamStanding, compute_standings

        if self.pk is None:
            return TeamStanding()
        return compute_standings(self.edition).team(self.pk)

    @property
    def total_points(self):
        """
        Total global points of the team, None in a manual edition.
        """
        return self._standing().total_points

    @property
    def ranking(self):
        """
        Ranking of the team in the edition: computed from the totals, or the stored
        final_rank in a manual edition (None for a team without one).
        """
        return self._standing().ranking
