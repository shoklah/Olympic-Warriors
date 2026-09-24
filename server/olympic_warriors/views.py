"""
Logic for the Olympic Warriors app endpoints.
"""

from datetime import time as time_of_day

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.views.decorators.debug import sensitive_variables
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth.models import User
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    parser_classes,
    throttle_classes,
)
from rest_framework import serializers
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse

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
    LeaderboardRowSerializer,
    ProfileSerializer,
    MeSerializer,
    PhotoSerializer,
    ShowcaseSerializer,
    DisciplineAllTimeSerializer,
    HeldDisciplineSerializer,
)
from .avatars import MAX_BYTES, PhotoError, photo_urls, remove_photo, store_photo
from .badges import badge_stats, badges_by_user, profile_badges, showcase, valid_pins
from .claims import check_claim, complete_claim
from .profiles import (
    discipline_table,
    held_disciplines,
    is_person,
    leaderboard,
    person_ids,
    person_players,
    profile_record,
)
from .permissions import IsOrganiser
from .throttling import ClaimRateThrottle, LoginRateThrottle, PhotoRateThrottle
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
    UserProfile,
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


# The one answer to every link that does not hold, whatever the reason (claims.check_claim).
INVALID_LINK = {"error": "invalid_link"}


@extend_schema(
    methods=["GET"],
    summary="Who a claim link is for",
    responses={
        "200": inline_serializer(
            "ClaimIdentity",
            {"first_name": serializers.CharField(), "username": serializers.CharField()},
        ),
        "404": OpenApiResponse(description="Invalid or expired link, the same for every reason"),
    },
)
@extend_schema(
    methods=["POST"],
    summary="Choose a password through a claim link, ending every older session",
    request=inline_serializer("ClaimPassword", {"password": serializers.CharField()}),
    responses={
        "200": inline_serializer(
            "ClaimToken",
            {"token": serializers.CharField(), "user_id": serializers.IntegerField()},
        ),
        "400": OpenApiResponse(
            description='{"errors": [codes]}: the password validators\' codes, or '
            "password_missing"
        ),
        "404": OpenApiResponse(description="Invalid or expired link, the same for every reason"),
        "429": OpenApiResponse(description="Too many login attempts from this address"),
    },
)
@api_view(["GET", "POST"])
@authentication_classes([])  # the link is the credential: a stale token must not 401 it
@permission_classes([AllowAny])
@throttle_classes([ClaimRateThrottle])  # the POST only, in the login bucket
@parser_classes([JSONParser])
@sensitive_variables("password")  # never in an error report
def claimAccount(request, uidb64, token):
    """
    A claim link (claims.py): GET says who it is for, POST {password} sets the password and
    answers the user's new token, the old one deleted. The link is checked before the
    password, so a dead link is a 404 whatever the password; then a missing or blank
    password is `password_missing`, and the validators give their own codes.
    """
    user = check_claim(uidb64, token)
    if user is None:
        return Response(INVALID_LINK, status=404)
    if request.method == "GET":
        return Response({"first_name": user.first_name, "username": user.username})

    password = request.data.get("password") if isinstance(request.data, dict) else None
    if not isinstance(password, str) or not password.strip():
        return Response({"errors": ["password_missing"]}, status=400)
    try:
        key = complete_claim(user, token, password)
    except ValidationError as error:
        return Response({"errors": [e.code for e in error.error_list]}, status=400)
    if key is None:  # used or made unclaimable since check_claim()
        return Response(INVALID_LINK, status=404)
    return Response({"token": key, "user_id": user.pk})


# The caller's own account: open to any token (IsAuthenticated), a player's included. The
# photo and the showcase belong to a person's profile, so they answer 404 to anyone else,
# before reading the body or writing anything.

NOT_A_PERSON = {"error": "not_a_person"}
INVALID_SHOWCASE = {"error": "invalid_showcase"}

# What a photo upload's body may carry on top of the photo itself. The multipart envelope
# (the boundary lines, the part's headers with its file name and type) takes a few hundred
# bytes, and 64 KiB leaves room for a long file name or a stray field. A larger body is
# refused from its Content-Length before a byte of it is read, so nobody makes the server
# parse and buffer megabytes only to refuse them; below it, store_photo() checks the file's
# own size. MAX_BYTES plus this stays under FILE_UPLOAD_MAX_MEMORY_SIZE (2.5 MB), so an
# upload is never spooled to a temporary file either.
MULTIPART_ALLOWANCE = 64 * 1024


def _content_length(request):
    """The body's declared length. Django reads nothing of a body without a valid one, so
    counting it as 0 lets nothing through unchecked."""
    try:
        return int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return 0


@extend_schema(
    summary="The caller's own account: names, login name, person flag, photo and stored pins",
    responses={
        "200": MeSerializer,
        "401": OpenApiResponse(description="No token"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])  # anyone logged in: it describes only the caller
def getMe(request):
    """
    Any logged-in user, a person or not (an organiser who never played is `is_person`
    false). The front calls it on every page, so it computes no badge, standing or
    leaderboard: one query besides the token's reads the profile row and the person flag,
    and a missing row, never created here, reads as no photo, unlocked, no pins.
    `showcase` is the stored pins as the person left them (`auto` when there is none);
    the badges shown are computed on the profile, where a pin no longer earned drops out.
    """
    user = (
        User.objects.select_related("profile")
        .annotate(is_person=Exists(person_players().filter(user=OuterRef("pk"))))
        .get(pk=request.user.pk)
    )
    profile = getattr(user, "profile", None)  # select_related: no query for a missing row
    pins = list(profile.showcase) if profile is not None else []
    return Response(
        MeSerializer(
            {
                "id": user.pk,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "is_staff": user.is_staff,
                "is_person": user.is_person,
                "photo": photo_urls(profile),
                "photo_locked": profile is not None and profile.photo_locked,
                "showcase": {"auto": not pins, "codes": pins},
            }
        ).data
    )


@extend_schema(
    methods=["PUT"],
    summary="Upload the caller's photo, replacing any previous one",
    request={
        "multipart/form-data": inline_serializer(
            "PhotoUpload", {"photo": serializers.FileField(help_text="JPEG, PNG or WebP")}
        )
    },
    responses={
        "200": inline_serializer("PhotoStored", {"photo": PhotoSerializer()}),
        "400": OpenApiResponse(
            description='{"error": code}: missing, too_large, bad_format or too_many_pixels'
        ),
        "403": OpenApiResponse(description='{"error": "photo_locked"}: locked by an organiser'),
        "404": OpenApiResponse(description="Not a person"),
        "429": OpenApiResponse(description="Too many uploads (PHOTO_THROTTLE_RATE, per user)"),
    },
)
@extend_schema(
    methods=["DELETE"],
    summary="Take the caller's photo down, locked or not",
    responses={
        "204": OpenApiResponse(description="No photo any more (or there was none)"),
        "404": OpenApiResponse(description="Not a person"),
    },
)
@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])  # the caller's own photo, 404 unless a person
@throttle_classes([PhotoRateThrottle])  # the PUT only, per user
@parser_classes([MultiPartParser])
def myPhoto(request):
    """
    PUT stores the multipart `photo` through avatars.store_photo(), creating the profile
    row with the first photo it stores (a refused upload leaves none), and answers the new
    URLs. A locked profile is refused first, then a body over MAX_BYTES +
    MULTIPART_ALLOWANCE from its Content-Length alone, both before the body is read.
    DELETE takes the photo down through avatars.remove_photo() even when uploads are
    locked: a person can always take their own face down. It creates no row.
    """
    if not is_person(request.user):
        return Response(NOT_A_PERSON, status=404)
    if request.method == "DELETE":
        profile = UserProfile.objects.filter(user=request.user).first()
        if profile is not None:
            remove_photo(profile)
        return Response(status=204)

    profile = UserProfile.objects.filter(user=request.user).first()
    if profile is not None and profile.photo_locked:
        return Response({"error": "photo_locked"}, status=403)
    if _content_length(request) > MAX_BYTES + MULTIPART_ALLOWANCE:
        return Response({"error": "too_large"}, status=400)
    upload = request.FILES.get("photo")
    try:
        # store_photo() needs a saved row, and refuses a bad upload only once it has one:
        # a row created here rolls back with the refusal, so only a stored photo leaves one.
        with transaction.atomic():
            if profile is None:  # get_or_create: a claim or a showcase may have made it since
                profile, _ = UserProfile.objects.get_or_create(user=request.user)
            store_photo(profile, upload)
    except PhotoError as error:  # photo_locked here: locked since the row was read
        status = 403 if error.code == "photo_locked" else 400
        return Response({"error": error.code}, status=status)
    return Response({"photo": photo_urls(profile)})


@extend_schema(
    summary="Pin up to three of the caller's badges on their profile ([] for automatic)",
    request=inline_serializer(
        "ShowcasePins",
        {
            "codes": serializers.ListField(
                child=serializers.CharField(), max_length=3,
                help_text="Distinct badge codes the caller has earned, in the order shown",
            )
        },
    ),
    responses={
        "200": ShowcaseSerializer,
        "400": OpenApiResponse(
            description='{"error": "invalid_showcase"}: not a list, more than 3, a duplicate, '
            "or a code the caller has not earned"
        ),
        "404": OpenApiResponse(description="Not a person"),
    },
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])  # the caller's own showcase, 404 unless a person
@parser_classes([JSONParser])
def setMyShowcase(request):
    """
    Store {codes} as the caller's pins (badges.valid_pins: at most 3 distinct codes, each
    earned now) and answer the showcase the profile now shows. An unreadable body is the
    same 400 as a bad list. The rarity counts of the automatic showcase are over the
    leaderboard's people, as on the profile (person_ids(), without computing the
    leaderboard).
    """
    if not is_person(request.user):
        return Response(NOT_A_PERSON, status=404)
    try:
        data = request.data
    except ParseError:
        return Response(INVALID_SHOWCASE, status=400)
    codes = data.get("codes") if isinstance(data, dict) else None
    entries = profile_badges(request.user.pk)
    if not valid_pins(codes, entries):
        return Response(INVALID_SHOWCASE, status=400)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.showcase = codes
    profile.save(update_fields=["showcase", "updated_at"])  # never the photo fields
    holders = badge_stats(person_ids())["holders"]
    return Response(ShowcaseSerializer(showcase(entries, codes, holders)).data)


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


# Profiles


@extend_schema(
    summary="Every person who played, in all-time leaderboard order",
    description=(
        "Ranked people first, like a medal table on their places (more 1st places, then "
        "more 2nd places, and so on; identical places share a position), then the ones "
        "with no counted edition yet (finished, ranked, at least two teams), by name and "
        "without a position. Each row carries the small photo and the badges its profile's "
        "showcase shows."
    ),
    responses={
        "200": LeaderboardRowSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def getProfiles(request):
    """
    Each row's showcase is the one its profile shows (the same badges, pins and rarity
    counts, see getProfile), for everyone at once: every person's badges in one query and
    the rarity stats in one more, neither run when nobody is listed.
    """
    records = leaderboard()
    user_ids = [record.user_id for record in records]
    by_user = badges_by_user(user_ids)
    holders = badge_stats(user_ids)["holders"]
    showcases = {
        record.user_id: showcase(by_user[record.user_id], record.pins, holders)["badges"]
        for record in records
    }
    return Response(
        LeaderboardRowSerializer(records, many=True, context={"showcases": showcases}).data
    )


@extend_schema(
    summary=(
        "One person's editions, average rank, discipline places, position, badges, "
        "badge rarity stats, photo and showcase"
    ),
    responses={
        "200": ProfileSerializer,
        "404": OpenApiResponse(description="Player not found"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def getProfile(request, user_id):
    # The same leaderboard as /profiles/, so a profile can never disagree on a position; its
    # user ids are also the rarity stats' denominator (everyone on /players). The record's
    # discipline places also count the person's running editions, like the all-time tables.
    # The record carries the photo and the pins, and the showcase reuses the badges and the
    # stats, so neither costs a query.
    records, record = profile_record(user_id)
    if record is None:
        return Response({"error": "Player not found"}, status=404)
    badges = profile_badges(user_id)
    stats = badge_stats([r.user_id for r in records])
    context = {
        "badges": badges,
        "badge_stats": stats,
        "showcase": showcase(badges, record.pins, stats["holders"]),
    }
    return Response(ProfileSerializer(record, context=context).data)


@extend_schema(
    summary="A discipline's all-time table of people",
    description=(
        "Every person whose team has a revealed, scored result in the discipline (matched "
        "by name across active editions, the running one included), ordered like the "
        "leaderboard's medal table on those places; identical places share a position. "
        "The same table for every edition's discipline of that name."
    ),
    responses={
        "200": DisciplineAllTimeSerializer,
        "404": OpenApiResponse(description="Discipline not found"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def getDisciplineAllTime(request, discipline_id):
    name = (
        Discipline.objects.filter(pk=discipline_id, is_active=True, edition__is_active=True)
        .values_list("name", flat=True)
        .first()
    )
    if name is None:
        return Response({"error": "Discipline not found"}, status=404)
    return Response(DisciplineAllTimeSerializer(discipline_table(name)).data)


@extend_schema(
    summary="Every discipline an active edition ever held, with those editions",
    description=(
        "One entry per discipline name, in name order: the untranslated name and, oldest "
        "first, each active edition that held it with the id of its discipline there, whose "
        "page holds the discipline's all-time table. Finished or running editions alike, "
        "revealed results or not."
    ),
    responses={
        "200": HeldDisciplineSerializer(many=True),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def getHeldDisciplines(request):
    return Response(HeldDisciplineSerializer(held_disciplines(), many=True).data)


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

# The game, round and result views show the rows and apply the reveal rule of the edition
# summary: scores stay null until the discipline is revealed, except for staff. That is why
# they, unlike the rest of the token-only API (staff-only by default), stay open to any
# token, a player's included (IsAuthenticated): they carry nothing the public summary does not.


def _reveal_context(request):
    """Serializer context of the reveal rule: staff see the scores before the reveal."""
    return {"staff": request.user.is_staff}


def _games():
    """
    The games the summary lists: active, in an active round of an active discipline of an
    active edition (the summary of an inactive one is a 404).
    """
    return Game.objects.filter(
        is_active=True,
        round__is_active=True,
        discipline__is_active=True,
        discipline__edition__is_active=True,
    ).select_related("discipline")


def _rounds():
    """The rounds the summary lists: active, of an active discipline of an active edition."""
    return TeamSportRound.objects.filter(
        is_active=True, discipline__is_active=True, discipline__edition__is_active=True
    )


def _results():
    """
    The results the summary lists: active, of an active discipline and an active team, in an
    active edition.
    """
    return TeamResult.objects.filter(
        is_active=True,
        discipline__is_active=True,
        team__is_active=True,
        discipline__edition__is_active=True,
    ).select_related("team", "discipline__edition")


@extend_schema(
    summary="Get a game by ID",
    responses={
        "200": GameSerializer,
        "401": OpenApiResponse(description="Unauthorized"),
        "404": OpenApiResponse(description="Game not found"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getGame(request, game_id):
    try:
        game = _games().get(id=game_id)
    except Game.DoesNotExist:
        return Response({"error": "Game not found"}, status=404)

    serializer = GameSerializer(game, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getGames(request):
    games = _games()
    serializer = GameSerializer(games, many=True, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getGamesByTeam(request, team_id):
    games = _games().filter(Q(team1=team_id) | Q(team2=team_id) | Q(referees=team_id))
    serializer = GameSerializer(games, many=True, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getGamesByDiscipline(request, discipline_id):
    games = _games().filter(discipline=discipline_id)
    serializer = GameSerializer(games, many=True, context=_reveal_context(request))
    return Response(serializer.data)


@extend_schema(
    summary="Get the games a team plays in (not refereed ones), played or not",
    responses={
        "200": GameSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getPlayedGamesByTeam(request, team_id):
    games = _games().filter(Q(team1=team_id) | Q(team2=team_id))
    serializer = GameSerializer(games, many=True, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getRefereedGamesByTeam(request, team_id):
    games = _games().filter(referees=team_id)
    serializer = GameSerializer(games, many=True, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getGamesByEdition(request, edition_id):
    games = _games().filter(discipline__edition=edition_id)
    serializer = GameSerializer(games, many=True, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getGamesByDisciplineAndTeam(request, discipline_id, team_id):
    games = _games().filter(
        Q(team1=team_id) | Q(team2=team_id) | Q(referees=team_id), discipline=discipline_id
    )
    serializer = GameSerializer(games, many=True, context=_reveal_context(request))
    return Response(serializer.data)


@extend_schema(
    summary="Get the games a team plays in for a discipline (not refereed ones), played or not",
    responses={
        "200": GameSerializer(many=True),
        "401": OpenApiResponse(description="Unauthorized"),
        "500": OpenApiResponse(description="Internal server error"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getPlayedGamesByDisciplineAndTeam(request, team_id, discipline_id):
    games = _games().filter(Q(team1=team_id) | Q(team2=team_id), discipline=discipline_id)
    serializer = GameSerializer(games, many=True, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getRefereedGamesByDisciplineAndTeam(request, team_id, discipline_id):
    games = _games().filter(referees=team_id, discipline=discipline_id)
    serializer = GameSerializer(games, many=True, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getGamesByRound(request, round_id):
    games = _games().filter(round=round_id)
    serializer = GameSerializer(games, many=True, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getRound(request, round_id):
    try:
        round = _rounds().get(id=round_id)
    except TeamSportRound.DoesNotExist:
        return Response({"error": "Round not found"}, status=404)
    serializer = TeamSportRoundSerializer(round, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getRounds(request):
    rounds = _rounds()
    serializer = TeamSportRoundSerializer(rounds, many=True, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getRoundsByDiscipline(request, discipline_id):
    rounds = _rounds().filter(discipline=discipline_id)
    serializer = TeamSportRoundSerializer(rounds, many=True, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getTeamResult(request, team_result_id):
    try:
        team_result = _results().get(id=team_result_id)
    except TeamResult.DoesNotExist:
        return Response({"error": "Team result not found"}, status=404)
    serializer = TeamResultSerializer(team_result, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getTeamResults(request):
    team_results = _results()
    serializer = TeamResultSerializer(team_results, many=True, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getTeamResultsByTeam(request, team_id):
    team_results = _results().filter(team=team_id)
    serializer = TeamResultSerializer(team_results, many=True, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getTeamResultsByEdition(request, edition_id):
    team_results = _results().filter(discipline__edition=edition_id)
    serializer = TeamResultSerializer(team_results, many=True, context=_reveal_context(request))
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
@permission_classes([IsAuthenticated])  # reveal rule: nothing beyond the public summary
def getTeamResultsByDiscipline(request, discipline_id):
    team_results = _results().filter(discipline=discipline_id)
    serializer = TeamResultSerializer(team_results, many=True, context=_reveal_context(request))
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
