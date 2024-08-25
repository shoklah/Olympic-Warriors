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
    TeamSportRoundSerializer,
    TeamResultSerializer,
)
from .models import Player, Edition, Team, Discipline, PlayerRating, Game, TeamSportRound, TeamResult


# Players


@extend_schema(
    summary="Get a player by ID",
    responses={
        200: PlayerSerializer,
        404: OpenApiResponse(description="Player not found"),
        500: OpenApiResponse(description="Internal server error"),
    },
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
    summary="Get all active players",
    responses={
        "200": PlayerSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    },
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
    summary="Get all active players for an edition",
    responses={
        "200": PlayerSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getPlayersByEdition(request, edition_id):
    players = Player.objects.filter(edition=edition_id, is_active=True)
    serializer = PlayerSerializer(players, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all active players for a team",
    responses={
        "200": PlayerSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getPlayersByTeam(request, team_id):
    players = Player.objects.filter(team=team_id, is_active=True)
    serializer = PlayerSerializer(players, many=True)
    return Response(serializer.data)


# Editions


@extend_schema(
    summary="Get an edition by ID",
    responses={
        200: EditionSerializer,
        404: OpenApiResponse(description="Edition not found"),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getEdition(request, edition_id):
    try:
        edition = Edition.objects.get(id=edition_id)
    except Edition.DoesNotExist:
        return Response({"error": "Edition not found"}, status=404)
    serializer = EditionSerializer(edition)
    return Response(serializer.data)


@extend_schema(
    summary="Get all active editions",
    responses={
        "200": EditionSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getEditions(request):
    editions = Edition.objects.filter(is_active=True)
    serializer = EditionSerializer(editions, many=True)
    return Response(serializer.data)


# Teams


@extend_schema(
    summary="Get a team by ID",
    responses={
        200: TeamSerializer,
        404: OpenApiResponse(description="Team not found"),
        500: OpenApiResponse(description="Internal server error"),
    },
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
    summary="Get all active teams",
    responses={
        "200": TeamSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getTeams(request):
    teams = Team.objects.filter(is_active=True)
    serializer = TeamSerializer(teams, many=True)
    return Response(serializer.data)


# Disciplines


@extend_schema(
    summary="Get a discipline by ID",
    responses={
        "200": DisciplineSerializer,
        "404": OpenApiResponse(description="Discipline not found"),
        "500": OpenApiResponse(description="Internal server error"),
    },
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
    summary="Get all active disciplines",
    responses={
        "200": DisciplineSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getDisciplines(request):
    disciplines = Discipline.objects.filter(is_active=True)
    serializer = DisciplineSerializer(disciplines, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all active disciplines for an edition",
    responses={
        "200": DisciplineSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getDisciplinesByEdition(request, edition_id):
    disciplines = Discipline.objects.filter(edition=edition_id, is_active=True)
    serializer = DisciplineSerializer(disciplines, many=True)
    return Response(serializer.data)


# Player Ratings


@extend_schema(
    summary="Get a player rating by ID",
    responses={
        200: PlayerRatingSerializer,
        404: OpenApiResponse(description="Player rating not found"),
        500: OpenApiResponse(description="Internal server error"),
    },
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
    summary="Get all active player ratings",
    responses={
        "200": PlayerRatingSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getPlayerRatings(request):
    player_ratings = PlayerRating.objects.filter(is_active=True)
    serializer = PlayerRatingSerializer(player_ratings, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all active player ratings for a player",
    responses={
        "200": PlayerRatingSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
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
      
    summary="Get all team results",
    responses={
        200: TeamResultSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
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


# Rounds


@extend_schema(
    summary="Get round by ID",
    responses={
        200: GameSerializer,
        404: OpenApiResponse(description="Round not found"),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getRound(request, round_id):
    try:
        round = TeamSportRound.objects.get(id=round_id)
    except TeamSportRound.DoesNotExist:
        return Response({"error": "Round not found"}, status=404)
    serializer = TeamSportRoundSerializer(round)
    return Response(serializer.data)


@extend_schema(
    summary="Get all rounds",
    responses={
        200: GameSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getRounds(request):
    rounds = TeamSportRound.objects.filter(is_active=True)
    serializer = TeamSportRoundSerializer(rounds, many=True)
    return Response(serializer.data)
  
@extend_schema(
    summary="Get rounds by discipline",
    responses={
        200: GameSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getRoundsByDiscipline(request, discipline_id):
    rounds = TeamSportRound.objects.filter(discipline=discipline_id, is_active=True)
    serializer = TeamSportRoundSerializer(rounds, many=True)
    return Response(serializer.data)
    summary="Get team results by discipline ID",
    responses={
        200: TeamResultSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
      
# Team Results

@extend_schema(
    summary="Get team results by ID",
    responses={
        200: TeamResultSerializer,
        404: OpenApiResponse(description="Team result not found"),
        500: OpenApiResponse(description="Internal server error"),
    }
)
@api_view(["GET"])
def getTeamResult(request, team_result_id):
    try:
        team_result = TeamResult.objects.get(id=team_result_id)
    except TeamResult.DoesNotExist:
        return Response({"error": "Team result not found"}, status=404)
    serializer = TeamResultSerializer(team_result)
    return Response(serializer.data)


@api_view(["GET"])
def getTeamResults(request):
    team_results = TeamResult.objects.filter(is_active=True)
    serializer = TeamResultSerializer(team_results, many=True)
    return Response(serializer.data)


  
@extend_schema(
    summary="Get team results by team ID",
    responses={
        200: TeamResultSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getTeamResultsByTeam(request, team_id):
    team_results = TeamResult.objects.filter(team=team_id, is_active=True)
    serializer = TeamResultSerializer(team_results, many=True)
    return Response(serializer.data)


 
@extend_schema(
    summary="Get team results by edition ID",
    responses={
        200: TeamResultSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getTeamResultsByEdition(request, edition_id):
    team_results = TeamResult.objects.filter(edition=edition_id, is_active=True)
    serializer = TeamResultSerializer(team_results, many=True)
    return Response(serializer.data)


@extend_schema(
@api_view(["GET"])
def getTeamResultsByDiscipline(request, discipline_id):
    team_results = TeamResult.objects.filter(discipline=discipline_id, is_active=True)
    serializer = TeamResultSerializer(team_results, many=True)
    return Response(serializer.data)
