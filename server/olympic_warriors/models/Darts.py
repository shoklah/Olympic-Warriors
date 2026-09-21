from .Discipline import Discipline
from .ResultTypes import ResultTypes


class Darts(Discipline):
    """
    Darts is a discipline that takes place in an edition of the Olympic Warriors.
    Games are scheduled by the base Discipline according to the pairing system
    chosen in the admin.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to darts, schedule games and initialize team results.
        """
        # Check if the object is already in the database
        if self.pk is None:
            self.name = 'Darts'
            self.result_type = ResultTypes.POINTS

        super().save(*args, **kwargs)
