from .Discipline import Discipline
from .ResultTypes import ResultTypes


class Orienteering(Discipline):
    """
    Orienteering is a event that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to Orienteering
        """

        # Check if the object is already in the database
        if self.pk is None:
            self.name = 'Orienteering'
            self.result_type = ResultTypes.TIME

        super().save(*args, **kwargs)
