from .Discipline import Discipline


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
