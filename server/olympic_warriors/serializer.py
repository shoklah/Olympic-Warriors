"""
Serializers for the Olympic Warriors app
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema_field
from olympic_warriors.models import (
    Player,
    Edition,
    Team,
    Discipline,
    PlayerRating,
    Game,
    GameEvent,
    TeamSportRound,
    TeamResult,
    BlindtestRound,
    BlindtestGuess,
    ResultTypes,
)
from .standings import compute_standings


class UserSerializer(serializers.ModelSerializer):
    """
    User serializer
    """

    class Meta:
        """
        Meta class
        """

        model = User
        fields = ("id", "username", "first_name", "last_name", "email", "is_staff")
        read_only_fields = ("is_staff",)
        
class PlayerSerializer(serializers.ModelSerializer):
    """
    Player serializer
    """

    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")

    class Meta:
        """
        Meta class
        """

        model = Player
        fields = (
            "id",
            "edition",
            "rating",
            "first_name",
            "last_name",
            "team",
            "is_active",
        )


class EditionSerializer(serializers.ModelSerializer):
    """
    Edition serializer
    """

    class Meta:
        """
        Meta class
        """

        model = Edition
        fields = "__all__"


class TeamSerializer(serializers.ModelSerializer):
    """
    Team serializer
    """

    total_points = serializers.ReadOnlyField()
    ranking = serializers.ReadOnlyField()
    players = serializers.SerializerMethodField()

    class Meta:
        """
        Meta class
        """

        model = Team
        fields = "__all__"

    @extend_schema_field(PlayerSerializer(many=True))
    def get_players(self, obj):
        """
        Get players for a team
        """
        players = Player.objects.filter(team=obj)
        return PlayerSerializer(players, many=True).data


class DisciplineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discipline
        fields = "__all__"


class PlayerRatingSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="player.user.first_name")
    last_name = serializers.CharField(source="player.user.last_name")

    class Meta:
        model = PlayerRating
        fields = "__all__"


class GameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = "__all__"


class GameEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameEvent
        fields = "__all__"


class TeamSportRoundSerializer(serializers.ModelSerializer):
    games = serializers.SerializerMethodField()

    class Meta:
        model = TeamSportRound
        fields = "__all__"

    @extend_schema_field(GameSerializer(many=True))
    def get_games(self, obj):
        games = Game.objects.filter(round=obj)
        return GameSerializer(games, many=True).data


class BlindtestGuessSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlindtestGuess
        fields = "__all__"


class BlindtestGuessUpdateSerializer(serializers.Serializer):
    artist = serializers.CharField(max_length=255, required=True, allow_blank=True)
    song = serializers.CharField(max_length=255, required=True, allow_blank=True)


class BlindtestRoundSerializer(serializers.ModelSerializer):
    guesses = serializers.SerializerMethodField()

    class Meta:
        model = BlindtestRound
        fields = "__all__"

    @extend_schema_field(BlindtestGuessSerializer(many=True))
    def get_guesses(self, obj):
        guesses = BlindtestGuess.objects.filter(blindtest_round=obj)
        return BlindtestGuessSerializer(guesses, many=True).data


class TeamResultSerializer(serializers.ModelSerializer):
    ranking = serializers.ReadOnlyField()
    global_points = serializers.ReadOnlyField()
    points_difference = serializers.ReadOnlyField()
    result_type = serializers.ReadOnlyField()
    team_name = serializers.CharField(source="team.name")

    class Meta:
        model = TeamResult
        fields = "__all__"


# Edition summary: everything the public front needs for one edition in one payload.


class SummaryEditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Edition
        fields = ("id", "year", "host", "start_date", "end_date", "photos_url")


class SummaryDisciplineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discipline
        fields = ("id", "name", "result_type", "reveal_score", "pairing_system")


class SummaryPlayerSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")

    class Meta:
        model = Player
        fields = ("id", "first_name", "last_name")


class SummaryTeamSerializer(serializers.ModelSerializer):
    """
    A team's summary row. `ranking` and `total_points` come from the edition standings
    computed once by EditionSummarySerializer and handed in through context["standings"],
    instead of each team recomputing them. Both are null in a manual edition without a
    rank for this team (ranking) or for every team (total_points).
    """

    ranking = serializers.SerializerMethodField()
    total_points = serializers.SerializerMethodField()
    players = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ("id", "name", "ranking", "total_points", "players")

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_ranking(self, obj):
        return self.context["standings"].team(obj.id).ranking

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_total_points(self, obj):
        return self.context["standings"].team(obj.id).total_points

    @extend_schema_field(SummaryPlayerSerializer(many=True))
    def get_players(self, obj):
        return SummaryPlayerSerializer(obj.active_players, many=True).data


class SummaryResultSerializer(serializers.ModelSerializer):
    """
    A team's result in a discipline, its standing read from context["standings"] (see
    _standing). The ranking fields are null while the discipline's reveal_score is off,
    or while the result itself has no score yet for its type: the summary is public and
    must not leak a standing early, nor 500 on a NULL score. With context["staff"] the
    stored points and time stay visible so an organiser can check and edit them; the
    ranking stays hidden for staff too until the discipline is revealed.
    """

    HIDDEN_FIELDS = ("ranking", "points", "time", "points_difference", "global_points")

    result_type = serializers.ReadOnlyField()
    ranking = serializers.SerializerMethodField()
    points_difference = serializers.SerializerMethodField()
    global_points = serializers.SerializerMethodField()

    def _standing(self, obj):
        """
        The result's standing: from context["standings"] inside the summary; computed
        once per edition and memoised on this serializer otherwise (the organiser score
        endpoints serialise a single row without context).
        """
        standings = self.context.get("standings")
        if standings is None:
            cache = self.__dict__.setdefault("_standings_cache", {})
            edition_id = obj.discipline.edition_id
            if edition_id not in cache:
                cache[edition_id] = compute_standings(obj.discipline.edition)
            standings = cache[edition_id]
        return standings.result(obj.id)

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_ranking(self, obj):
        return self._standing(obj).ranking

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_points_difference(self, obj):
        return self._standing(obj).points_difference

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_global_points(self, obj):
        return self._standing(obj).global_points

    class Meta:
        model = TeamResult
        fields = (
            "id",
            "team",
            "discipline",
            "result_type",
            "ranking",
            "points",
            "time",
            "points_difference",
            "global_points",
        )

    def to_representation(self, instance):
        missing_score = (
            (instance.result_type == ResultTypes.POINTS and instance.points is None)
            or (instance.result_type == ResultTypes.TIME and instance.time is None)
            or instance.result_type == ResultTypes.NONE
            or not instance.result_type
        )
        if instance.discipline.reveal_score and not missing_score:
            return super().to_representation(instance)
        hidden = {
            "id": instance.id,
            "team": instance.team_id,
            "discipline": instance.discipline_id,
            "result_type": instance.result_type,
        }
        hidden.update({field: None for field in self.HIDDEN_FIELDS})
        if self.context.get("staff"):
            hidden["points"] = instance.points
            hidden["time"] = (
                self.fields["time"].to_representation(instance.time)
                if instance.time is not None
                else None
            )
        return hidden


class SummaryRoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamSportRound
        fields = ("id", "discipline", "order", "is_over")


class SummaryGameSerializer(serializers.ModelSerializer):
    """
    A scheduled game. Pairings, referee and the played flag are always visible;
    the scores are null while the discipline's reveal_score is off, unless
    context["staff"] is set.
    """

    score1 = serializers.IntegerField(read_only=True, allow_null=True)
    score2 = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Game
        fields = (
            "id",
            "discipline",
            "round",
            "team1",
            "team2",
            "referees",
            "is_played",
            "score1",
            "score2",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not instance.discipline.reveal_score and not self.context.get("staff"):
            data["score1"] = None
            data["score2"] = None
        return data


class EditionSummarySerializer(serializers.Serializer):
    """
    Serialize an Edition into {edition, disciplines, teams, results, rounds, games},
    active rows only.
    """

    edition = SummaryEditionSerializer()
    disciplines = SummaryDisciplineSerializer(many=True)
    teams = SummaryTeamSerializer(many=True)
    results = SummaryResultSerializer(many=True)
    rounds = SummaryRoundSerializer(many=True)
    games = SummaryGameSerializer(many=True)

    def to_representation(self, instance):
        disciplines = Discipline.objects.filter(edition=instance, is_active=True).order_by("id")
        teams = list(
            Team.objects.filter(edition=instance, is_active=True)
            .order_by("name")
            .prefetch_related(
                Prefetch(
                    "player_set",
                    queryset=Player.objects.filter(is_active=True, edition=instance)
                    .select_related("user")
                    .order_by("user__last_name", "user__first_name"),
                    to_attr="active_players",
                )
            )
        )
        standings = compute_standings(instance)
        results = (
            TeamResult.objects.filter(
                discipline__edition=instance,
                discipline__is_active=True,
                team__is_active=True,
                is_active=True,
            )
            .select_related("discipline", "team")
            .order_by("id")
        )
        rounds = TeamSportRound.objects.filter(
            discipline__edition=instance, discipline__is_active=True, is_active=True
        ).order_by("discipline_id", "order")
        games = (
            Game.objects.filter(
                discipline__edition=instance,
                discipline__is_active=True,
                round__is_active=True,
                is_active=True,
            )
            .select_related("discipline", "round")
            .order_by("discipline_id", "round__order", "id")
        )
        staff_context = {"staff": bool(self.context.get("staff")), "standings": standings}
        return {
            "edition": SummaryEditionSerializer(instance).data,
            "disciplines": SummaryDisciplineSerializer(disciplines, many=True).data,
            "teams": SummaryTeamSerializer(
                teams, many=True, context={"standings": standings}
            ).data,
            "results": SummaryResultSerializer(results, many=True, context=staff_context).data,
            "rounds": SummaryRoundSerializer(rounds, many=True).data,
            "games": SummaryGameSerializer(games, many=True, context=staff_context).data,
        }


class GameScoreSerializer(serializers.Serializer):
    """The organiser sheet: both scores and the played flag, all required."""

    score1 = serializers.IntegerField(min_value=0, max_value=99999)
    score2 = serializers.IntegerField(min_value=0, max_value=99999)
    is_played = serializers.BooleanField()


class ResultValueSerializer(serializers.Serializer):
    """
    One of `points` (integer, 0 or more) or `time` ("mm:ss", minutes may exceed 59); null
    clears the value. The view decides which field the discipline accepts.
    """

    points = serializers.IntegerField(min_value=0, max_value=99999, allow_null=True, required=False)
    time = serializers.RegexField(r"^\d{1,3}:[0-5]\d$", allow_null=True, required=False)


class RevealSerializer(serializers.Serializer):
    reveal_score = serializers.BooleanField()
