from .Discipline import Discipline
from .ResultTypes import ResultTypes


class GeographyQuizz(Discipline):
    """
    Geography Quizz is a discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to geography quizz and initialize team results.
        """
        # Check if the object is already in the database
        if self.pk is None:
            self.name = 'Geography Quizz'
            self.result_type = ResultTypes.POINTS

        super().save(*args, **kwargs)
