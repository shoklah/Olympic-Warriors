from .Discipline import Discipline
from .ResultTypes import ResultTypes


class ObstacleCourse(Discipline):
    """
    Obstacle Course is a discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to obstacle course and initialize team results.
        """
        # Check if the object is already in the database
        if self.pk is None:
            self.name = 'Obstacle Course'
            self.result_type = ResultTypes.TIME

        super().save(*args, **kwargs)
