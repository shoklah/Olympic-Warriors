from .Discipline import Discipline
from .ResultTypes import ResultTypes


class Geoguessr(Discipline):
    """
    Geoguessr is a discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to geoguessr and initialize team results.
        """
        # Check if the object is already in the database
        if self.pk is None:
            self.name = 'Geoguessr'
            self.result_type = ResultTypes.POINTS

        super().save(*args, **kwargs)
