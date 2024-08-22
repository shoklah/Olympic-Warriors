"""
Logic for the Olympic Warriors app endpoints.
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .serializer import (
    PlayerSerializer,
    EditionSerializer,
    TeamSerializer,
    DisciplineSerializer,
    PlayerRatingSerializer,
)
from .models import Player, Edition, Team, Discipline, PlayerRating


# Players


@extend_schema(
    responses={
        200: PlayerSerializer,
        404: OpenApiResponse(description="Player not found"),
        500: OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getPlayer(request, player_id):
    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        return Response({"error": "Player not found"}, status=404)
    serializer = PlayerSerializer(player)
    return Response(serializer.data)


@extend_schema(
    responses={
        "200": PlayerSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getPlayers(request):
    """
    Get all players.
    """
    players = Player.objects.filter(is_active=True)
    serializer = PlayerSerializer(players, many=True)
    return Response(serializer.data)


@extend_schema(
    responses={
        "200": PlayerSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getPlayersByEdition(request, edition_id):
    players = Player.objects.filter(edition=edition_id, is_active=True)
    serializer = PlayerSerializer(players, many=True)
    return Response(serializer.data)


@extend_schema(
    responses={
        "200": PlayerSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getPlayersByTeam(request, team_id):
    players = Player.objects.filter(team=team_id, is_active=True)
    serializer = PlayerSerializer(players, many=True)
    return Response(serializer.data)


# Editions


@extend_schema(responses=EditionSerializer)
@api_view(["GET"])
def getEdition(request, edition_id):
    try:
        edition = Edition.objects.get(id=edition_id)
    except Edition.DoesNotExist:
        return Response({"error": "Edition not found"}, status=404)
    serializer = EditionSerializer(edition)
    return Response(serializer.data)


@extend_schema(
    responses={
        "200": EditionSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getEditions(request):
    editions = Edition.objects.filter(is_active=True)
    serializer = EditionSerializer(editions, many=True)
    return Response(serializer.data)


# Teams


@extend_schema(
    responses={
        200: TeamSerializer,
        404: OpenApiResponse(description="Team not found"),
        500: OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getTeam(request, team_id):
    try:
        team = Team.objects.get(id=team_id)
    except Team.DoesNotExist:
        return Response({"error": "Team not found"}, status=404)
    serializer = TeamSerializer(team)
    return Response(serializer.data)


@extend_schema(
    responses={
        "200": TeamSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getTeams(request):
    teams = Team.objects.filter(is_active=True)
    serializer = TeamSerializer(teams, many=True)
    return Response(serializer.data)


# Disciplines


@extend_schema(
    responses={
        "200": DisciplineSerializer,
        "404": OpenApiResponse(description="Discipline not found"),
        "500": OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getDiscipline(request, discipline_id):
    try:
        discipline = Discipline.objects.get(id=discipline_id)
    except Discipline.DoesNotExist:
        return Response({"error": "Discipline not found"}, status=404)
    serializer = DisciplineSerializer(discipline)
    return Response(serializer.data)


@extend_schema(
    responses={
        "200": DisciplineSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getDisciplines(request):
    disciplines = Discipline.objects.filter(is_active=True)
    serializer = DisciplineSerializer(disciplines, many=True)
    return Response(serializer.data)


@extend_schema(
    responses={
        "200": DisciplineSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getDisciplinesByEdition(request, edition_id):
    disciplines = Discipline.objects.filter(edition=edition_id, is_active=True)
    serializer = DisciplineSerializer(disciplines, many=True)
    return Response(serializer.data)


# Player Ratings


@extend_schema(
    responses={
        200: PlayerRatingSerializer,
        404: OpenApiResponse(description="Player rating not found"),
        500: OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getPlayerRating(request, rating_id):
    try:
        player_rating = PlayerRating.objects.get(id=rating_id)
    except PlayerRating.DoesNotExist:
        return Response({"error": "Player rating not found"}, status=404)
    serializer = PlayerRatingSerializer(player_rating)
    return Response(serializer.data)


@extend_schema(
    responses={
        "200": PlayerRatingSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getPlayerRatings(request):
    player_ratings = PlayerRating.objects.filter(is_active=True)
    serializer = PlayerRatingSerializer(player_ratings, many=True)
    return Response(serializer.data)


@extend_schema(
    responses={
        "200": PlayerRatingSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getPlayerRatingsByPlayer(request, player_id):
    player_ratings = PlayerRating.objects.filter(player=player_id, is_active=True)
    serializer = PlayerRatingSerializer(player_ratings, many=True)
    return Response(serializer.data)
