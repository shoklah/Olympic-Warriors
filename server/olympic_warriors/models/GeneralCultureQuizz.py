from .Discipline import Discipline
from .ResultTypes import ResultTypes


class GeneralCultureQuizz(Discipline):
    """
    General Culture Quizz is a discipline that takes place in an edition of the Olympic Warriors.
    Live scoring happens on an external quiz platform; only final points are stored here.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to general culture quizz and initialize team results.
        """
        # Check if the object is already in the database
        if self.pk is None:
            self.name = 'General Culture Quizz'
            self.result_type = ResultTypes.POINTS

        super().save(*args, **kwargs)
