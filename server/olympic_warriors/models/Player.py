from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Player(models.Model):
    """
    A player is a user that has a rating and is part of a team.
    """

    edition = models.ForeignKey("Edition", on_delete=models.CASCADE)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    team = models.ForeignKey("Team", on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)


class PlayerRating(models.Model):
    """
    A player rating on a specific area, with its name and identifier.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    identifier = models.CharField(max_length=4)
    rating = models.FloatField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    is_active = models.BooleanField(default=True)
