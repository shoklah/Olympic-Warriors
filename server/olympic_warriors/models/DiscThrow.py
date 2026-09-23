from .Discipline import Discipline
from .ResultTypes import ResultTypes


class DiscThrow(Discipline):
    """
    Disc Throw is a discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to disc throw and initialize team results.
        """
        # Check if the object is already in the database
        if self.pk is None:
            self.name = 'Disc Throw'
            self.result_type = ResultTypes.POINTS

        super().save(*args, **kwargs)
