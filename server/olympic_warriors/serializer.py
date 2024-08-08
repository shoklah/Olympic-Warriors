from rest_framework import serializers
from olympic_warriors.models import Player, Edition, Team, Discipline, PlayerRating


class PlayerSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")

    class Meta:
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
    class Meta:
        model = Edition
        fields = "__all__"


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = "__all__"


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
