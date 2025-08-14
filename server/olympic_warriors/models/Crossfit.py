"""
Model for Crossfit discipline.
"""

from .Discipline import Discipline
from .ResultTypes import ResultTypes

class Crossfit(Discipline):
    """
    Crossfit is a discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to crossfit
        """

        # Check if the object is already in the database
        if self.pk is None:
            self.name = 'Crossfit'
            self.result_type = ResultTypes.TIME

        super().save(*args, **kwargs)
