from django.db import models

class ResultTypes(models.TextChoices):
    """
    Enum for Team Result Types
    """

    POINTS = 'PTS', 'Points'
    TIME = 'TIM', 'Time'
    NONE = 'NON', 'None'
