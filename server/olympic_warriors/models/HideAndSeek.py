from .Discipline import Discipline
from .Team import Team, TeamResult


class HideAndSeek(Discipline):
    """
    Hide and seek is a Discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to hide and seek
        """

        # Check if the object is already in the database
        if self.pk is None:
            self.name = 'Hide and Seek'
            super().save(*args, **kwargs)
            teams = Team.objects.filter(edition=self.edition, is_active=True)
            for team in teams:
                TeamResult.objects.create(
                    team=team,
                    discipline=self,
                    result_type=TeamResult.TeamResultTypes.POINTS,
                    points=0,
                )
        else:
            super().save(*args, **kwargs)
