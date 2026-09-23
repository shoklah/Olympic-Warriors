from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator


class Player(models.Model):
    """
    A player is a user that has a rating and is part of a team.
    """

    edition = models.ForeignKey("Edition", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    team = models.ForeignKey("Team", on_delete=models.CASCADE, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.user.first_name + " " + self.user.last_name

    def clean(self):
        """
        Refuse a team of another edition, and a second active row for the same person in
        the same edition. Both errors sit on `team`: it is the one field every admin form
        of a player shows (the changelist, the team inline, the change form), and an
        error on a field the form lacks makes Django raise ValueError instead of showing
        it. Imports insert without clean(), so they are not affected.
        """
        super().clean()
        if self.team_id is not None and self.edition_id is not None:
            if self.team.edition_id != self.edition_id:
                raise ValidationError({"team": "This team belongs to another edition."})
        if self.is_active and self.user_id is not None and self.edition_id is not None:
            duplicates = Player.objects.filter(
                user_id=self.user_id, edition_id=self.edition_id, is_active=True
            ).exclude(pk=self.pk)
            if duplicates.exists():
                raise ValidationError(
                    {"team": "This person already has an active player in this edition."}
                )


class PlayerRating(models.Model):
    """
    A player rating on a specific area, with its name and identifier.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    identifier = models.CharField(max_length=4)
    rating = models.FloatField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    is_active = models.BooleanField(default=True)
