from .Discipline import Discipline
from .Team import Team
from .ResultTypes import ResultTypes


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
            self.result_type = ResultTypes.POINTS

        super().save(*args, **kwargs)
