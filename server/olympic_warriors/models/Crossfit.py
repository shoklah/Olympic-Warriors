"""
Model for Crossfit discipline.
"""

from .Discipline import Discipline, TeamResult
from .Team import Team


class Crossfit(Discipline):
    """
    Crossfit is a discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to crossfit
        """
        self.name = 'Crossfit'
        super().save(*args, **kwargs)
        teams = Team.objects.filter(edition=self.edition, is_active=True)
        for team in teams:
            TeamResult.objects.create(
                team=team,
                discipline=self,
                result_type=TeamResult.TeamResultTypes.TIME,
                time="00:00:00",
            )
