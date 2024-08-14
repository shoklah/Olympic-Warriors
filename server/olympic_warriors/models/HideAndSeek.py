from .Discipline import Discipline, TeamResult
from .Team import Team


class HideAndSeek(Discipline):
    """
    Hide and seek is a Discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to hide and seek
        """
        self.name = 'Hide and Seek'
        super().save(*args, **kwargs)
        teams = Team.objects.filter(edition=self.edition, is_active=True)
        for team in teams:
            TeamResult.objects.create(
                team=team, discipline=self, result_type=TeamResult.TeamResultTypes.POINTS, points=0
            )
