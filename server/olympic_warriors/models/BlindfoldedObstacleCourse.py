from .Discipline import Discipline
from .ResultTypes import ResultTypes


class BlindfoldedObstacleCourse(Discipline):
    """
    Blindfolded Obstacle Course is a discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to blindfolded obstacle course and initialize team results.
        """
        # Check if the object is already in the database
        if self.pk is None:
            self.name = 'Blindfolded Obstacle Course'
            self.result_type = ResultTypes.TIME

        super().save(*args, **kwargs)
