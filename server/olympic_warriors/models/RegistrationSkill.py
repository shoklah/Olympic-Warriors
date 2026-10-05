from django.core.validators import MinValueValidator
from django.db import models


class RegistrationSkill(models.Model):
    """
    One self-rated skill of an edition's registration questionnaire. Its weight feeds the
    player's rating (registration.rate); its identifier is the PlayerRating identifier.
    """

    edition = models.ForeignKey("Edition", on_delete=models.CASCADE)
    name_fr = models.CharField(max_length=100)
    # Also what PlayerRating.name stores, as the CSV import does.
    name_en = models.CharField(max_length=100)
    identifier = models.CharField(max_length=4)
    weight = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "identifier"], name="registration_skill_unique_identifier"
            )
        ]

    def __str__(self) -> str:
        return f"{self.identifier} ({self.edition.year})"
