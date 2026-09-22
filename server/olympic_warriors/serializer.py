"""
Serializers for the Olympic Warriors app
"""

from rest_framework import serializers
from django.contrib.auth.models import User
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
)


class UserSerializer(serializers.ModelSerializer):
    """
    User serializer
    """

    class Meta:
        """
        Meta class
        """

        model = User
        fields = ("id", "username", "first_name", "last_name", "email")
        
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
    artist = serializers.CharField(max_length=255, required=True)
    song = serializers.CharField(max_length=255, required=True)


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
        fields = ("id", "name", "result_type", "reveal_score")


class SummaryPlayerSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")

    class Meta:
        model = Player
        fields = ("id", "first_name", "last_name")


class SummaryTeamSerializer(serializers.ModelSerializer):
    ranking = serializers.ReadOnlyField()
    total_points = serializers.ReadOnlyField()
    players = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ("id", "name", "ranking", "total_points", "players")

    @extend_schema_field(SummaryPlayerSerializer(many=True))
    def get_players(self, obj):
        players = (
            Player.objects.filter(team=obj, is_active=True)
            .select_related("user")
            .order_by("user__last_name", "user__first_name")
        )
        return SummaryPlayerSerializer(players, many=True).data


class SummaryResultSerializer(serializers.ModelSerializer):
    """
    A team's result in a discipline. Score fields are null while the discipline's
    reveal_score is off: the summary is public and must not leak a score early.
    """

    HIDDEN_FIELDS = ("ranking", "points", "time", "points_difference", "global_points")

    result_type = serializers.ReadOnlyField()
    ranking = serializers.ReadOnlyField()
    points_difference = serializers.ReadOnlyField()
    global_points = serializers.ReadOnlyField()

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
        if instance.discipline.reveal_score:
            return super().to_representation(instance)
        hidden = {
            "id": instance.id,
            "team": instance.team_id,
            "discipline": instance.discipline_id,
            "result_type": instance.result_type,
        }
        hidden.update({field: None for field in self.HIDDEN_FIELDS})
        return hidden


class EditionSummarySerializer(serializers.Serializer):
    """
    Serialize an Edition into {edition, disciplines, teams, results}, active rows only.
    """

    edition = SummaryEditionSerializer()
    disciplines = SummaryDisciplineSerializer(many=True)
    teams = SummaryTeamSerializer(many=True)
    results = SummaryResultSerializer(many=True)

    def to_representation(self, instance):
        disciplines = Discipline.objects.filter(edition=instance, is_active=True).order_by("id")
        teams = Team.objects.filter(edition=instance, is_active=True).order_by("name")
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
        return {
            "edition": SummaryEditionSerializer(instance).data,
            "disciplines": SummaryDisciplineSerializer(disciplines, many=True).data,
            "teams": SummaryTeamSerializer(teams, many=True).data,
            "results": SummaryResultSerializer(results, many=True).data,
        }
