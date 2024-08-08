"""
Serializers for the Olympic Warriors app
"""

from rest_framework import serializers
from olympic_warriors.models import Player, Edition, Team


class PlayerSerializer(serializers.ModelSerializer):
    """
    Player serializer
    """

    class Meta:
        """
        Meta class
        """

        model = Player
        fields = "__all__"


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

    class Meta:
        """
        Meta class
        """

        model = Team
        fields = "__all__"
