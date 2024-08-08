"""
Logic for the Olympic Warriors app endpoints.
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializer import PlayerSerializer
from .models import Player


@api_view(["GET"])
def getPlayers(request):
    """
    Get all players.
    """
    players = Player.objects.all()
    serializer = PlayerSerializer(players, many=True)
    return Response(serializer.data)
