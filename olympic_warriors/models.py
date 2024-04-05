from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Player(models.Model):
    """
    A player is a user that has a rating and is part of a team.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    team = models.ForeignKey("Team", on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)


class Edition(models.Model):
    """
    An edition is a year in which the Olympic Warriors take place..
    """

    year = models.IntegerField(validators=[MinValueValidator(2020), MaxValueValidator(2030)])
    host = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)


class Team(models.Model):
    """
    A team is a group of players that participate in an edition of the Olympic Warriors.
    """

    captain = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="captain")
    name = models.CharField(max_length=100)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)


class Registration(models.Model):
    """
    A registration is a link between a Player and an Edition. It is used to keep track of
    the teams that participate in an edition.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    confirmed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)


class Game(models.Model):
    """
    A game is a competition between two teams that takes place in an edition of the Olympic Warriors.
    """

    team1 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team1")
    team2 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team2")
    referees = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="referees")
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    date = models.DateField()
    is_active = models.BooleanField(default=True)


class Event(models.Model):
    """
    An event is a competition that takes place in an edition of the Olympic Warriors.
    """

    name = models.CharField(max_length=100)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)


class Rugby(Event):
    """
    Rugby is a type of event that takes place in an edition of the Olympic Warriors.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    score = models.IntegerField(validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
