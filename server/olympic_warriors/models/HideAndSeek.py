from .Discipline import Discipline


class HideAndSeek(Discipline):
    """
    Hide and seek is a Discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to hide and seek
        """
        self.name = 'Hide and Seek'
        super().save(*args, **kwargs)
