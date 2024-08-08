from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST

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

import logging

logger = logging.getLogger(__name__)


@require_GET
@login_required
def home(request):
    return render(request, "olympic_warriors/home.html")


@require_GET
@login_required
def profile(request):
    return render(request, "olympic_warriors/profile.html")


# Players


@api_view(["GET"])
def getPlayers(request):
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
def getEditions(request):
    editions = Edition.objects.filter(is_active=True)
    serializer = EditionSerializer(editions, many=True)
    return Response(serializer.data)


# Teams


@api_view(["GET"])
def getTeams(request):
    teams = Team.objects.filter(is_active=True)
    serializer = TeamSerializer(teams, many=True)
    return Response(serializer.data)


# Disciplines


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
def getPlayerRatings(request):
    player_ratings = PlayerRating.objects.filter(is_active=True)
    serializer = PlayerRatingSerializer(player_ratings, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def getPlayerRatingsByPlayer(request, player_id):
    player_ratings = PlayerRating.objects.filter(player=player_id, is_active=True)
    serializer = PlayerRatingSerializer(player_ratings, many=True)
    return Response(serializer.data)
