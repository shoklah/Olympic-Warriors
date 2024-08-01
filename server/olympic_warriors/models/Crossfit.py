from .Discipline import Discipline


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
