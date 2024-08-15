from .Discipline import Discipline, TeamResult
from .Team import Team


class Orienteering(Discipline):
    """
    Orienteering is a event that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to Orienteering
        """
        self.name = 'Orienteering'
        super().save(*args, **kwargs)
        teams = Team.objects.filter(edition=self.edition, is_active=True)
        for team in teams:
            TeamResult.objects.create(
                team=team,
                discipline=self,
                result_type=TeamResult.TeamResultTypes.TIME,
                time="00:00:00",
            )
