from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Player(models.Model):
    """
    A player is a user that has a rating and is part of a team.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    team = models.ForeignKey("Team", on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)


class Team(models.Model):
    """
    A team is a group of players that participate in an edition of the Olympic Warriors.
    """

    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)


class Edition(models.Model):
    """
    An edition is a year in which the Olympic Warriors take place.
    It has a host, a start date, an end date and a list of teams that participate in it.
    """

    year = models.IntegerField(validators=[MinValueValidator(2020), MaxValueValidator(2030)])
    host = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    teams = models.ManyToManyField(Team, through="Registration")
    is_active = models.BooleanField(default=True)


class Registration(models.Model):
    """
    A registration is a link between a team and an edition. It is used to keep track of
    the teams that participate in an edition.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    confirmed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
