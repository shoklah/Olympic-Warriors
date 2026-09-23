"""
Logic for the Olympic Warriors app endpoints.
"""

from datetime import time as time_of_day

from django.db import transaction
from django.db.models import Q
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .serializer import (
    UserSerializer,
    PlayerSerializer,
    EditionSerializer,
    TeamSerializer,
    DisciplineSerializer,
    PlayerRatingSerializer,
    GameSerializer,
    GameEventSerializer,
    TeamSportRoundSerializer,
    TeamResultSerializer,
    BlindtestGuessSerializer,
    BlindtestGuessUpdateSerializer,
    BlindtestRoundSerializer,
    EditionSummarySerializer,
    GameScoreSerializer,
    ResultValueSerializer,
    RevealSerializer,
    SummaryGameSerializer,
    SummaryResultSerializer,
    SummaryDisciplineSerializer,
    SummaryRoundSerializer,
)
from .permissions import IsOrganiser
from .throttling import LoginRateThrottle
from .models import (
    Player,
    Edition,
    Team,
    Discipline,
    PlayerRating,
    Game,
    GameEvent,
    TeamSportRound,
    TeamResult,
    BlindtestGuess,
    BlindtestRound,
    latest_edition,
)

# Authentication

class ThrottledObtainAuthToken(ObtainAuthToken):
    """
    Exchange a username and password for the user's token ({"token": ...}). Limited per
    client IP (LoginRateThrottle, LOGIN_THROTTLE_RATE): past the limit every attempt, even
    with the right password, gets a 429 with Retry-After. DRF's stock view has no throttle.
    """

    throttle_classes = [LoginRateThrottle]


# Users

@extend_schema(
    summary="Get a user by ID",
    responses={
        200: UserSerializer,
        404: OpenApiResponse(description="User not found"),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getUser(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)
    serializer = UserSerializer(user)
    return Response(serializer.data)

@extend_schema(
    summary="Get all users",
    responses={
        200: UserSerializer(many=True),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getUsers(request):
    users = User.objects.all()
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)

@extend_schema(
    summary="Get current user",
    responses={
        200: UserSerializer,
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getCurrentUser(request):
    user = request.user
    serializer = UserSerializer(user)
    return Response(serializer.data)


# Players


@extend_schema(
    summary="Get a player by ID",
    responses={
        "200": PlayerSerializer,
        "401": OpenApiResponse(description="Unauthorized"),
        "404": OpenApiResponse(description="Player not found"),
        "500": OpenApiResponse(description="Internal server error"),
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
        "401": OpenApiResponse(description="Unauthorized"),
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
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getPlayersByEdition(request, edition_id):
    players = Player.objects.filter(edition=edition_id, is_active=True)
    serializer = PlayerSerializer(players, many=True)
    return Response(serializer.data)

@extend_schema(
    summary="Get a player by user and edition",
    responses={
        200: PlayerSerializer,
        404: OpenApiResponse(description="Player not found"),
        500: OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getPlayerByUserAndEdition(request, user_id, edition_id):
    try:
        player = Player.objects.get(user=user_id, edition=edition_id)
    except Player.DoesNotExist:
        return Response({"error": "Player not found"}, status=404)
    serializer = PlayerSerializer(player)
    return Response(serializer.data)

@extend_schema(
    summary="Get all active players for a team",
    responses={
        "200": PlayerSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
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
        "200": EditionSerializer,
        "404": OpenApiResponse(description="Edition not found"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
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
@permission_classes([AllowAny])
def getEditions(request):
    editions = Edition.objects.filter(is_active=True)
    serializer = EditionSerializer(editions, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Everything the public front needs for one edition, by year",
    description=(
        "Public and player tokens get the revealed rankings only; a staff token also "
        "returns every hidden game's score and every result's stored points or time."
    ),
    responses={
        "200": EditionSummarySerializer,
        "404": OpenApiResponse(description="Edition not found"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def getEditionSummary(request, year):
    try:
        edition = Edition.objects.get(year=year, is_active=True)
    except Edition.DoesNotExist:
        return Response({"error": "Edition not found"}, status=404)
    # Staff see game scores and stored results before the reveal; the ranking stays hidden.
    serializer = EditionSummarySerializer(edition, context={"staff": request.user.is_staff})
    return Response(serializer.data)


# Teams


@extend_schema(
    summary="Get a team by ID",
    responses={
        "200": TeamSerializer,
        "401": OpenApiResponse(description="Unauthorized"),
        "404": OpenApiResponse(description="Team not found"),
        "500": OpenApiResponse(description="Internal server error"),
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
        "401": OpenApiResponse(description="Unauthorized"),
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
@permission_classes([AllowAny])
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
@permission_classes([AllowAny])
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
@permission_classes([AllowAny])
def getDisciplinesByEdition(request, edition_id):
    disciplines = Discipline.objects.filter(edition=edition_id, is_active=True)
    serializer = DisciplineSerializer(disciplines, many=True)
    return Response(serializer.data)


# Player Ratings


@extend_schema(
    summary="Get a player rating by ID",
    responses={
        "200": PlayerRatingSerializer,
        "401": OpenApiResponse(description="Unauthorized"),
        "404": OpenApiResponse(description="Player rating not found"),
        "500": OpenApiResponse(description="Internal server error"),
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
        "401": OpenApiResponse(description="Unauthorized"),
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
        "401": OpenApiResponse(description="Unauthorized"),
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
        "200": GameSerializer,
        "401": OpenApiResponse(description="Unauthorized"),
        "404": OpenApiResponse(description="Game not found"),
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
        "200": GameSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGames(request):
    games = Game.objects.filter(is_active=True)
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get games by team",
    responses={
        "200": GameSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
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
        "200": GameSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
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
        "200": GameSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getPlayedGamesByTeam(request, team_id):
    games = Game.objects.filter((Q(team1=team_id) | Q(team2=team_id)), is_active=True)
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get games refereed by a team",
    responses={
        "200": GameSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getRefereedGamesByTeam(request, team_id):
    games = Game.objects.filter(referees=team_id, is_active=True)
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get games by edition",
    responses={
        "200": GameSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
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
        "200": GameSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
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
        "200": GameSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
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
        "200": GameSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
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
        "200": GameSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGamesByRound(request, round_id):
    games = Game.objects.filter(round=round_id, is_active=True)
    serializer = GameSerializer(games, many=True)
    return Response(serializer.data)


# Game Events


@extend_schema(
    summary="Get a game event by ID",
    responses={
        "200": GameEventSerializer,
        "401": OpenApiResponse(description="Unauthorized"),
        "404": OpenApiResponse(description="Game event not found"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGameEvent(request, event_id):
    try:
        event = GameEvent.objects.get(id=event_id)
    except GameEvent.DoesNotExist:
        return Response({"error": "Game event not found"}, status=404)
    serializer = GameEventSerializer(event)
    return Response(serializer.data)


@extend_schema(
    summary="Get all game events",
    responses={
        "200": GameEventSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGameEvents(request):
    events = GameEvent.objects.filter(is_active=True)
    serializer = GameEventSerializer(events, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all game events for a game",
    responses={
        "200": GameEventSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGameEventsByGame(request, game_id):
    events = GameEvent.objects.filter(game=game_id, is_active=True)
    serializer = GameEventSerializer(events, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all game events for a player",
    responses={
        "200": GameEventSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGameEventsByPlayer(request, player_id):
    events = GameEvent.objects.filter(Q(player1=player_id) | Q(player2=player_id), is_active=True)
    serializer = GameEventSerializer(events, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all game events for a team",
    responses={
        "200": GameEventSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getGameEventsByTeam(request, team_id):
    events = GameEvent.objects.filter(
        Q(player1__team=team_id) | Q(player2__team=team_id), is_active=True
    )
    serializer = GameEventSerializer(events, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Create a game event",
    responses={
        "200": GameEventSerializer,
        "400": OpenApiResponse(description="Bad request"),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["POST"])
def createGameEvent(request):
    serializer = GameEventSerializer(data=request.data)
    try:
        serializer.is_valid(raise_exception=True)
    except Exception as e:
        return Response({"error": "Bad request", "details": str(e)}, status=400)

    serializer.save()
    return Response(serializer.data)


@extend_schema(
    summary="Delete a game event",
    responses={
        "200": GameEventSerializer,
        "401": OpenApiResponse(description="Unauthorized"),
        "404": OpenApiResponse(description="Game event not found"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["DELETE"])
def deleteGameEvent(request, event_id):
    try:
        event = GameEvent.objects.get(id=event_id)
    except GameEvent.DoesNotExist:
        return Response({"error": "Game event not found"}, status=404)

    event.is_active = False
    event.save()
    serializer = GameEventSerializer(event)
    return Response(serializer.data)


# Rounds


@extend_schema(
    summary="Get round by ID",
    responses={
        "200": TeamSportRoundSerializer,
        "401": OpenApiResponse(description="Unauthorized"),
        "404": OpenApiResponse(description="Round not found"),
        "500": OpenApiResponse(description="Internal server error"),
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
        "200": TeamSportRoundSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
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
        "200": TeamSportRoundSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getRoundsByDiscipline(request, discipline_id):
    rounds = TeamSportRound.objects.filter(discipline=discipline_id, is_active=True)
    serializer = TeamSportRoundSerializer(rounds, many=True)
    return Response(serializer.data)


# Team Results


@extend_schema(
    summary="Get team results by ID",
    responses={
        "200": TeamResultSerializer,
        "401": OpenApiResponse(description="Unauthorized"),
        "404": OpenApiResponse(description="Team result not found"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getTeamResult(request, team_result_id):
    try:
        team_result = TeamResult.objects.get(id=team_result_id)
    except TeamResult.DoesNotExist:
        return Response({"error": "Team result not found"}, status=404)
    serializer = TeamResultSerializer(team_result)
    return Response(serializer.data)


@extend_schema(
    summary="Get all team results",
    responses={
        "200": TeamResultSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getTeamResults(request):
    team_results = TeamResult.objects.filter(is_active=True)
    serializer = TeamResultSerializer(team_results, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get team results by team ID",
    responses={
        "200": TeamResultSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
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
        "200": TeamResultSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getTeamResultsByEdition(request, edition_id):
    team_results = TeamResult.objects.filter(
        discipline__edition=edition_id, is_active=True
    ).select_related("team", "discipline")
    serializer = TeamResultSerializer(team_results, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get team results by discipline ID",
    responses={
        "200": TeamResultSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getTeamResultsByDiscipline(request, discipline_id):
    team_results = TeamResult.objects.filter(discipline=discipline_id, is_active=True)
    serializer = TeamResultSerializer(team_results, many=True)
    return Response(serializer.data)


# Blindtest


@extend_schema(
    summary="Get a blindtest guess by ID",
    responses={
        "200": BlindtestGuessSerializer,
        "401": OpenApiResponse(description="Unauthorized"),
        "404": OpenApiResponse(description="Blindtest guess not found"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getBlindtestGuess(request, guess_id):
    try:
        guess = BlindtestGuess.objects.get(id=guess_id)
    except BlindtestGuess.DoesNotExist:
        return Response({"error": "Blindtest guess not found"}, status=404)
    serializer = BlindtestGuessSerializer(guess)
    return Response(serializer.data)


@extend_schema(
    summary="Get all blindtest guesses",
    responses={
        "200": BlindtestGuessSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getBlindtestGuesses(request):
    guesses = BlindtestGuess.objects.filter(is_active=True)
    serializer = BlindtestGuessSerializer(guesses, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all blindtest guesses for a team",
    responses={
        "200": BlindtestGuessSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getBlindtestGuessesByTeam(request, team_id):
    guesses = BlindtestGuess.objects.filter(team=team_id, is_active=True)
    serializer = BlindtestGuessSerializer(guesses, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all blindtest guesses for a blindtest",
    responses={
        "200": BlindtestGuessSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getBlindtestGuessesByBlindtest(request, blindtest_id):
    guesses = BlindtestGuess.objects.filter(
        blindtest_round__blindtest=blindtest_id, is_active=True
    )
    serializer = BlindtestGuessSerializer(guesses, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all blindtest guesses for a team and blindtest",
    responses={
        "200": BlindtestGuessSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getBlindtestGuessesByTeamAndBlindtest(request, team_id, blindtest_id):
    guesses = BlindtestGuess.objects.filter(
        team=team_id, blindtest_round__blindtest=blindtest_id, is_active=True
    )
    serializer = BlindtestGuessSerializer(guesses, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all blindtest guesses with correct artist and song",
    responses={
        "200": BlindtestGuessSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getCorrectBlindtestGuesses(request):
    guesses = BlindtestGuess.objects.filter(
        is_artist_correct=True, is_song_correct=True, is_active=True
    )
    serializer = BlindtestGuessSerializer(guesses, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all blindtest guesses with correct artist",
    responses={
        "200": BlindtestGuessSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getCorrectArtistBlindtestGuesses(request):
    guesses = BlindtestGuess.objects.filter(is_artist_correct=True, is_active=True)
    serializer = BlindtestGuessSerializer(guesses, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all blindtest guesses with correct song",
    responses={
        "200": BlindtestGuessSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getCorrectSongBlindtestGuesses(request):
    guesses = BlindtestGuess.objects.filter(is_song_correct=True, is_active=True)
    serializer = BlindtestGuessSerializer(guesses, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get a blindtest round by ID",
    responses={
        "200": BlindtestRoundSerializer,
        "401": OpenApiResponse(description="Unauthorized"),
        "404": OpenApiResponse(description="Blindtest round not found"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getBlindtestRound(request, round_id):
    try:
        round = BlindtestRound.objects.get(id=round_id)
    except BlindtestRound.DoesNotExist:
        return Response({"error": "Blindtest round not found"}, status=404)
    serializer = BlindtestRoundSerializer(round)
    return Response(serializer.data)


@extend_schema(
    summary="Get all blindtest rounds",
    responses={
        "200": BlindtestRoundSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getBlindtestRounds(request):
    rounds = BlindtestRound.objects.filter(is_active=True)
    serializer = BlindtestRoundSerializer(rounds, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all blindtest rounds for a blindtest",
    responses={
        "200": BlindtestRoundSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getBlindtestRoundsByBlindtest(request, blindtest_id):
    rounds = BlindtestRound.objects.filter(blindtest=blindtest_id, is_active=True)
    serializer = BlindtestRoundSerializer(rounds, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get all blindtest rounds for an edition",
    responses={
        "200": BlindtestRoundSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
def getBlindtestRoundsByEdition(request, edition_id):
    rounds = BlindtestRound.objects.filter(blindtest__edition=edition_id, is_active=True)
    serializer = BlindtestRoundSerializer(rounds, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Set the artist and song for a blindtest guess",
    request=BlindtestGuessUpdateSerializer,
    responses={
        "200": BlindtestGuessSerializer,
        "400": OpenApiResponse(description="Bad request"),
        "404": OpenApiResponse(description="Blindtest guess not found"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["PATCH"])
def setBlindtestGuessAnswer(request, guess_id):
    try:
        guess = BlindtestGuess.objects.get(id=guess_id)
    except BlindtestGuess.DoesNotExist:
        return Response({"error": "Blindtest guess not found"}, status=404)

    serializer = BlindtestGuessUpdateSerializer(data=request.data)
    try:
        serializer.is_valid(raise_exception=True)
    except Exception as e:
        return Response({"error": "Bad request", "details": str(e)}, status=400)

    guess.artist = serializer.validated_data["artist"]
    guess.song = serializer.validated_data["song"]
    guess.save()

    serializer = BlindtestGuessSerializer(guess)
    return Response(serializer.data)

# Organiser


LATEST_ONLY = {"error": "Only the latest edition can be edited"}


def _editable(edition):
    """Only the active edition with the highest year can be edited from the site."""
    latest = latest_edition()
    return latest is not None and edition.id == latest.id


def _minutes_seconds(text):
    """"mm:ss" (minutes may exceed 59) to a time of day; None stays None."""
    if text is None:
        return None
    minutes, seconds = (int(part) for part in text.split(":"))
    return time_of_day(minutes // 60, minutes % 60, seconds)


@extend_schema(
    summary="Set a game's score and played flag (organisers, latest edition)",
    request=GameScoreSerializer,
    responses={
        "200": SummaryGameSerializer,
        "400": OpenApiResponse(description="Missing field or negative score"),
        "401": OpenApiResponse(description="Unauthorized"),
        "403": OpenApiResponse(description="Not an organiser"),
        "404": OpenApiResponse(description="Game not found"),
        "409": OpenApiResponse(description="Not the latest edition"),
    },
)
@api_view(["PATCH"])
@permission_classes([IsOrganiser])
@parser_classes([JSONParser])  # a form-encoded body would read a missing boolean as False
def setGameScore(request, game_id):
    try:
        game = Game.objects.select_related("discipline__edition").get(
            id=game_id, is_active=True, discipline__is_active=True, round__is_active=True
        )
    except Game.DoesNotExist:
        return Response({"error": "Game not found"}, status=404)
    if not _editable(game.discipline.edition):
        return Response(LATEST_ONLY, status=409)

    serializer = GameScoreSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "Bad request", "details": serializer.errors}, status=400)

    for field, value in serializer.validated_data.items():
        setattr(game, field, value)
    game.save()  # recomputes the league points of both teams
    return Response(SummaryGameSerializer(game, context={"staff": True}).data)


@extend_schema(
    summary="Set a team's points or time in a discipline without games (organisers, latest edition)",
    request=ResultValueSerializer,
    responses={
        "200": SummaryResultSerializer,
        "400": OpenApiResponse(description="Wrong field for the result type, bad value, or a discipline with games"),
        "401": OpenApiResponse(description="Unauthorized"),
        "403": OpenApiResponse(description="Not an organiser"),
        "404": OpenApiResponse(description="Result not found"),
        "409": OpenApiResponse(description="Not the latest edition"),
    },
)
@api_view(["PATCH"])
@permission_classes([IsOrganiser])
@parser_classes([JSONParser])  # JSON only, like the other organiser writes
def setTeamResult(request, result_id):
    try:
        result = TeamResult.objects.select_related("discipline__edition").get(
            id=result_id, is_active=True, discipline__is_active=True, team__is_active=True
        )
    except TeamResult.DoesNotExist:
        return Response({"error": "Result not found"}, status=404)
    if not _editable(result.discipline.edition):
        return Response(LATEST_ONLY, status=409)
    if TeamSportRound.objects.filter(discipline=result.discipline, is_active=True).exists():
        return Response({"error": "Points of a discipline with games are computed"}, status=400)

    if not isinstance(request.data, dict):
        return Response({"error": "Bad request"}, status=400)

    result_type = result.discipline.result_type
    field = {"PTS": "points", "TIM": "time"}.get(result_type)
    if field is None:
        return Response({"error": "This discipline takes no result"}, status=400)
    if field not in request.data or len(request.data) != 1:
        return Response({"error": f"Expected exactly the field '{field}'"}, status=400)

    serializer = ResultValueSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "Bad request", "details": serializer.errors}, status=400)

    value = serializer.validated_data[field]
    setattr(result, field, _minutes_seconds(value) if field == "time" else value)
    result.save()
    return Response(SummaryResultSerializer(result, context={"staff": True}).data)


@extend_schema(
    summary="Reveal or hide a discipline's results (organisers, latest edition)",
    request=RevealSerializer,
    responses={
        "200": SummaryDisciplineSerializer,
        "400": OpenApiResponse(description="Missing flag"),
        "401": OpenApiResponse(description="Unauthorized"),
        "403": OpenApiResponse(description="Not an organiser"),
        "404": OpenApiResponse(description="Discipline not found"),
        "409": OpenApiResponse(description="Not the latest edition"),
    },
)
@api_view(["PATCH"])
@permission_classes([IsOrganiser])
@parser_classes([JSONParser])  # a form-encoded body would read a missing boolean as False
def setDisciplineReveal(request, discipline_id):
    try:
        discipline = Discipline.objects.select_related("edition").get(
            id=discipline_id, is_active=True
        )
    except Discipline.DoesNotExist:
        return Response({"error": "Discipline not found"}, status=404)
    if not _editable(discipline.edition):
        return Response(LATEST_ONLY, status=409)

    serializer = RevealSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "Bad request", "details": serializer.errors}, status=400)

    discipline.reveal_score = serializer.validated_data["reveal_score"]
    discipline.save(update_fields=["reveal_score"])
    return Response(SummaryDisciplineSerializer(discipline).data)


@extend_schema(
    summary="Close a round once every game is played (organisers, latest edition)",
    request=None,
    responses={
        "200": SummaryRoundSerializer,
        "401": OpenApiResponse(description="Unauthorized"),
        "403": OpenApiResponse(description="Not an organiser"),
        "404": OpenApiResponse(description="Round not found"),
        "409": OpenApiResponse(description="Not the latest edition, already over, or games unplayed"),
    },
)
@api_view(["PATCH"])
@permission_classes([IsOrganiser])
@parser_classes([JSONParser])  # JSON only, like the other organiser writes
def closeRound(request, round_id):
    with transaction.atomic():
        try:
            round_ = (
                TeamSportRound.objects.select_for_update(of=("self",))
                .select_related("discipline__edition")
                .get(id=round_id, is_active=True, discipline__is_active=True)
            )
        except TeamSportRound.DoesNotExist:
            return Response({"error": "Round not found"}, status=404)
        if not _editable(round_.discipline.edition):
            return Response(LATEST_ONLY, status=409)
        if round_.is_over:
            return Response({"error": "Round already over"}, status=409)
        if Game.objects.filter(
            round=round_, is_active=True, is_played=False,
            discipline__is_active=True, round__is_active=True,
        ).exists():
            return Response({"error": "Some games are not played yet"}, status=409)

        round_.is_over = True
        try:
            round_.save()  # schedules the next Swiss round when the discipline is Swiss
        except ValueError:
            return Response({"error": "Not enough teams to schedule the next round"}, status=409)
    return Response(SummaryRoundSerializer(round_).data)
