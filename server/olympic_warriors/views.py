"""
Logic for the Olympic Warriors app endpoints.
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializer import (
    PlayerSerializer,
    EditionSerializer,
    TeamSerializer,
    DisciplineSerializer,
    PlayerRatingSerializer,
)
from .models import Player, Edition, Team, Discipline, PlayerRating


# Players


@api_view(["GET"])
def getPlayer(request, player_id):
    player = Player.objects.get(id=player_id)
    serializer = PlayerSerializer(player)
    return Response(serializer.data)


@api_view(["GET"])
def getPlayers(request):
    """
    Get all players.
    """
    players = Player.objects.filter(is_active=True)
    serializer = PlayerSerializer(players, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def getPlayersByEdition(request, edition_id):
    players = Player.objects.filter(edition=edition_id, is_active=True)
    serializer = PlayerSerializer(players, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def getPlayersByTeam(request, team_id):
    players = Player.objects.filter(team=team_id, is_active=True)
    serializer = PlayerSerializer(players, many=True)
    return Response(serializer.data)


# Editions


@api_view(["GET"])
def getEdition(request, edition_id):
    edition = Edition.objects.get(id=edition_id)
    serializer = EditionSerializer(edition)
    return Response(serializer.data)


@api_view(["GET"])
def getEditions(request):
    editions = Edition.objects.filter(is_active=True)
    serializer = EditionSerializer(editions, many=True)
    return Response(serializer.data)


# Teams


@api_view(["GET"])
def getTeam(request, team_id):
    team = Team.objects.get(id=team_id)
    serializer = TeamSerializer(team)
    return Response(serializer.data)


@api_view(["GET"])
def getTeams(request):
    teams = Team.objects.filter(is_active=True)
    serializer = TeamSerializer(teams, many=True)
    return Response(serializer.data)


# Disciplines


@api_view(["GET"])
def getDiscipline(request, discipline_id):
    discipline = Discipline.objects.get(id=discipline_id)
    serializer = DisciplineSerializer(discipline)
    return Response(serializer.data)


@api_view(["GET"])
def getDisciplines(request):
    disciplines = Discipline.objects.filter(is_active=True)
    serializer = DisciplineSerializer(disciplines, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def getDisciplinesByEdition(request, edition_id):
    disciplines = Discipline.objects.filter(edition=edition_id, is_active=True)
    serializer = DisciplineSerializer(disciplines, many=True)
    return Response(serializer.data)


# Player Ratings


@api_view(["GET"])
def getPlayerRating(request, rating_id):
    player_rating = PlayerRating.objects.get(id=rating_id)
    serializer = PlayerRatingSerializer(player_rating)
    return Response(serializer.data)


@api_view(["GET"])
def getPlayerRatings(request):
    player_ratings = PlayerRating.objects.filter(is_active=True)
    serializer = PlayerRatingSerializer(player_ratings, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def getPlayerRatingsByPlayer(request, player_id):
    player_ratings = PlayerRating.objects.filter(player=player_id, is_active=True)
    serializer = PlayerRatingSerializer(player_ratings, many=True)
    return Response(serializer.data)
