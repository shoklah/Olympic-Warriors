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
    team_name = serializers.CharField(source="team.name")

    class Meta:
        model = TeamResult
        fields = "__all__"
