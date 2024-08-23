"""
Logic for the Olympic Warriors app endpoints.
"""

from django.db.models import Q
from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .serializer import (
    PlayerSerializer,
    EditionSerializer,
    TeamSerializer,
    DisciplineSerializer,
    PlayerRatingSerializer,
    GameSerializer,
)
from .models import Player, Edition, Team, Discipline, PlayerRating, Game


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


# Games


@extend_schema(
    summary="Get a game by ID",
    responses={
        200: GameSerializer,
        404: OpenApiResponse(description="Game not found"),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGame(request, game_id):
    try:
        game = Game.objects.get(id=game_id)
    except Game.DoesNotExist:
        return Response({"error": "Game not found"}, status=404)
    serializer = GameSerializer(game)
    return Response(serializer.data)


@extend_schema(
    summary="Get all games",
    responses={
        200: GameSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGames(request):
    games = Game.objects.filter(is_active=True)
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get games by discipline",
    responses={
        200: GameSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGamesByDiscipline(request, discipline_id):
    games = Game.objects.filter(discipline=discipline_id, is_active=True)
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get games by team",
    responses={
        200: GameSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGamesByTeam(request, team_id):
    games = Game.objects.filter(
        (Q(team1=team_id) | Q(team2=team_id) | Q(referees=team_id)), is_active=True
    )
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get games played by a team",
    responses={
        200: GameSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
def getPlayedGamesByTeam(request, team_id):
    games = Game.objects.filter((Q(team1=team_id) | Q(team2=team_id)), is_active=True)
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get games refereed by a team",
    responses={
        200: GameSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
def getRefereedGamesByTeam(request, team_id):
    games = Game.objects.filter(referees=team_id, is_active=True)
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get games by edition",
    responses={
        200: GameSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGamesByEdition(request, edition_id):
    games = Game.objects.filter(discipline__edition=edition_id, is_active=True)
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get games by discipline and team",
    responses={
        200: GameSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGamesByDisciplineAndTeam(request, discipline_id, team_id):
    games = Game.objects.filter(
        (Q(team1=team_id) | Q(team2=team_id) | Q(referees=team_id)),
        discipline=discipline_id,
        is_active=True,
    )
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get games played by a team for a discipline",
    responses={
        200: GameSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getPlayedGamesByDisciplineAndTeam(request, team_id, discipline_id):
    games = Game.objects.filter(
        (Q(team1=team_id) | Q(team2=team_id)),
        discipline=discipline_id,
        is_active=True,
    )
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get games refereed by a team for a discipline",
    responses={
        200: GameSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getRefereedGamesByDisciplineAndTeam(request, team_id, discipline_id):
    games = Game.objects.filter(
        referees=team_id,
        discipline=discipline_id,
        is_active=True,
    )
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get games by round ID",
    responses={
        200: GameSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGamesByRound(request, round_id):
    games = Game.objects.filter(round=round_id, is_active=True)
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)
